#!/usr/bin/env python3
"""
Hermes App Backend
==================
Flask REST API serving the Hermes Agent web dashboard.
Port: 6000
"""

import os
import json
import sqlite3
import subprocess
import logging
import threading
import time
import re
import textwrap
from datetime import datetime
from pathlib import Path

# ── Scripts registry ──────────────────────────────────────────────────────────
SCRIPTS_DIR     = Path(__file__).parent / 'scripts'
SCRIPTS_LOG_DIR = Path(__file__).parent / 'logs' / 'scripts'
SCRIPTS_LOG_DIR.mkdir(parents=True, exist_ok=True)

RUNNABLE_SCRIPTS = [
    {
        'id':          'hermes-app-backup',
        'name':        'Hermes App Backup',
        'description': 'Backup ~/hermes-app → ~/Downloads/Backups_Hermes/ (excludes venv, logs, pycache)',
        'script':      'hermes-app-backup.sh',
        'group':       'Backups',
        'icon':        '💾',
    },
]

_running_jobs = {}  # job_id → {pid, log_path, script_id, started_at, status, returncode}

import requests
from flask import Flask, jsonify, request, Response, send_from_directory, send_file

# ── Config ────────────────────────────────────────────────────────────────────

PORT             = 6080
HERMES_DIR       = Path.home() / '.hermes'
STATE_DB         = HERMES_DIR / 'state.db'
GATEWAY_STATE    = HERMES_DIR / 'gateway_state.json'
CONFIG_YAML      = HERMES_DIR / 'config.yaml'
ENV_FILE         = HERMES_DIR / '.env'
FRONTEND_DIR     = Path(__file__).parent / 'frontend'
API_SERVER_URL   = 'http://127.0.0.1:8642'
API_SERVER_KEY   = 'hermes-local-key'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent / 'logs' / 'server.log'),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger('hermes-app')

app = Flask(__name__, static_folder=str(FRONTEND_DIR))

# ── Helpers ───────────────────────────────────────────────────────────────────

def db_conn():
    conn = sqlite3.connect(str(STATE_DB))
    conn.row_factory = sqlite3.Row
    return conn

def run_cmd(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except Exception as e:
        return str(e), -1

def read_gateway_state():
    try:
        with open(GATEWAY_STATE) as f:
            return json.load(f)
    except Exception:
        return {}

def api_headers():
    return {'Authorization': f'Bearer {API_SERVER_KEY}', 'Content-Type': 'application/json'}

def api_server_alive():
    try:
        r = requests.get(f'{API_SERVER_URL}/health', timeout=2)
        return r.status_code == 200
    except Exception:
        return False

# ── Static files ──────────────────────────────────────────────────────────────

@app.route('/')
@app.route('/index.html')
@app.route('/dashboard')
def page_dashboard():
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/chat')
@app.route('/chat.html')
def page_chat():
    return send_from_directory(FRONTEND_DIR, 'chat.html')

@app.route('/sessions')
@app.route('/sessions.html')
def page_sessions():
    return send_from_directory(FRONTEND_DIR, 'sessions.html')

@app.route('/cron')
@app.route('/cron.html')
def page_cron():
    return send_from_directory(FRONTEND_DIR, 'cron.html')

@app.route('/skills')
@app.route('/skills.html')
def page_skills():
    return send_from_directory(FRONTEND_DIR, 'skills.html')

@app.route('/config')
@app.route('/config.html')
def page_config():
    return send_from_directory(FRONTEND_DIR, 'config.html')

@app.route('/scripts')
@app.route('/scripts.html')
def page_scripts():
    return send_from_directory(FRONTEND_DIR, 'scripts.html')

@app.route('/dev')
@app.route('/dev.html')
def dev():
    return send_from_directory(FRONTEND_DIR, 'dev.html')

@app.route('/diary')
@app.route('/diary.html')
def page_diary():
    return send_from_directory(FRONTEND_DIR, 'diary.html')

@app.route('/css/<path:p>')
def static_css(p):
    return send_from_directory(FRONTEND_DIR / 'css', p)

@app.route('/js/<path:p>')
def static_js(p):
    return send_from_directory(FRONTEND_DIR / 'js', p)

# ── API: Status / Dashboard ───────────────────────────────────────────────────

@app.route('/api/status')
def api_status():
    # Hermes version
    version_out, _ = run_cmd('hermes --version 2>/dev/null || echo unknown')
    version = version_out.split('\n')[0] if version_out else 'unknown'

    # Gateway state
    gw = read_gateway_state()
    platforms = gw.get('platforms', {})
    gateway_running = gw.get('gateway_state') == 'running'

    # API server alive
    api_alive = api_server_alive()

    # Session stats from DB
    stats = {'total': 0, 'today': 0, 'total_tokens': 0, 'total_cost': 0.0}
    try:
        with db_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt, "
                "SUM(input_tokens + output_tokens) as tok, "
                "SUM(COALESCE(estimated_cost_usd,0)) as cost FROM sessions"
            ).fetchone()
            stats['total'] = row['cnt'] or 0
            stats['total_tokens'] = row['tok'] or 0
            stats['total_cost'] = round(row['cost'] or 0, 4)

            today_start = datetime.now().replace(hour=0, minute=0, second=0).timestamp()
            row2 = conn.execute(
                "SELECT COUNT(*) as cnt FROM sessions WHERE started_at >= ?", (today_start,)
            ).fetchone()
            stats['today'] = row2['cnt'] or 0
    except Exception as e:
        log.warning(f'DB stats error: {e}')

    # Cron count
    cron_out, _ = run_cmd('hermes cron list --json 2>/dev/null')
    cron_count = 0
    cron_jobs = []
    try:
        cron_data = json.loads(cron_out)
        if isinstance(cron_data, list):
            cron_count = len(cron_data)
            cron_jobs = cron_data[:5]
        elif isinstance(cron_data, dict) and 'jobs' in cron_data:
            cron_count = len(cron_data['jobs'])
            cron_jobs = cron_data['jobs'][:5]
    except Exception:
        pass

    # Recent sessions
    recent = []
    try:
        with db_conn() as conn:
            rows = conn.execute(
                "SELECT id, title, source, model, started_at, message_count, "
                "input_tokens + output_tokens as tokens, estimated_cost_usd as cost "
                "FROM sessions ORDER BY started_at DESC LIMIT 6"
            ).fetchall()
            recent = [dict(r) for r in rows]
    except Exception as e:
        log.warning(f'Recent sessions error: {e}')

    return jsonify({
        'version': version,
        'model': _get_model(),
        'gateway': {
            'running': gateway_running,
            'platforms': platforms,
        },
        'api_server': {
            'alive': api_alive,
            'url': API_SERVER_URL,
        },
        'stats': stats,
        'cron_count': cron_count,
        'cron_jobs': cron_jobs,
        'recent_sessions': recent,
    })

def _get_model():
    try:
        import yaml
        with open(CONFIG_YAML) as f:
            cfg = yaml.safe_load(f)
        m = cfg.get('model', {})
        return f"{m.get('provider','?')} / {m.get('default','?')}"
    except Exception:
        out, _ = run_cmd("grep -A2 'model:' ~/.hermes/config.yaml | head -3")
        return out or 'unknown'

# ── API: Sessions ─────────────────────────────────────────────────────────────

@app.route('/api/sessions')
def api_sessions():
    limit  = int(request.args.get('limit', 200))
    offset = int(request.args.get('offset', 0))
    source = request.args.get('source', '')

    where = 'WHERE source = ?' if source else ''
    params = [source] if source else []

    try:
        with db_conn() as conn:
            rows = conn.execute(
                f"SELECT id, title, source, model, started_at, ended_at, "
                f"message_count, tool_call_count, "
                f"input_tokens, output_tokens, "
                f"input_tokens + output_tokens as tokens, "
                f"estimated_cost_usd as cost, end_reason "
                f"FROM sessions {where} "
                f"ORDER BY started_at DESC LIMIT ? OFFSET ?",
                params + [limit, offset]
            ).fetchall()
            return jsonify([dict(r) for r in rows])
    except Exception as e:
        log.error(f'Sessions error: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/session/<session_id>')
def api_session(session_id):
    try:
        with db_conn() as conn:
            session = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if not session:
                return jsonify({'error': 'not found'}), 404

            messages = conn.execute(
                "SELECT role, content, tool_calls, tool_name, tool_call_id, "
                "timestamp, token_count, finish_reason, reasoning "
                "FROM messages WHERE session_id = ? ORDER BY timestamp ASC",
                (session_id,)
            ).fetchall()

            return jsonify({
                'session': dict(session),
                'messages': [dict(m) for m in messages],
            })
    except Exception as e:
        log.error(f'Session detail error: {e}')
        return jsonify({'error': str(e)}), 500

# ── API: Chat (proxy to Hermes API server) ────────────────────────────────────

@app.route('/api/chat/responses', methods=['POST'])
def api_chat_responses():
    """Proxy to /v1/responses -- stateful named conversations, no streaming."""
    if not api_server_alive():
        return jsonify({'error': 'Hermes API server is not running. Check the dashboard.'}), 503
    data = request.json or {}
    payload = {
        'input': data.get('input', ''),
        'store': True,
    }
    if data.get('conversation'):
        payload['conversation'] = data['conversation']
    if data.get('instructions'):
        payload['instructions'] = data['instructions']
    try:
        resp = requests.post(
            f'{API_SERVER_URL}/v1/responses',
            headers=api_headers(),
            json=payload,
            timeout=180,
        )
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def api_chat():
    if not api_server_alive():
        return jsonify({'error': 'Hermes API server is not running. Check the dashboard.'}), 503

    data = request.json or {}
    stream = data.get('stream', True)

    payload = {
        'model': 'hermes-agent',
        'messages': data.get('messages', []),
        'stream': stream,
    }

    if stream:
        def generate():
            try:
                with requests.post(
                    f'{API_SERVER_URL}/v1/chat/completions',
                    headers=api_headers(),
                    json=payload,
                    stream=True,
                    timeout=120,
                ) as resp:
                    for line in resp.iter_lines():
                        if line:
                            yield line.decode() + '\n\n'
            except Exception as e:
                yield f'data: {json.dumps({"error": str(e)})}\n\n'

        return Response(generate(), mimetype='text/event-stream',
                        headers={'X-Accel-Buffering': 'no', 'Cache-Control': 'no-cache'})
    else:
        try:
            resp = requests.post(
                f'{API_SERVER_URL}/v1/chat/completions',
                headers=api_headers(),
                json=payload,
                timeout=120,
            )
            return jsonify(resp.json()), resp.status_code
        except Exception as e:
            return jsonify({'error': str(e)}), 500

# ── API: Gateway control ──────────────────────────────────────────────────────

@app.route('/api/gateway/restart', methods=['POST'])
def api_gateway_restart():
    out, code = run_cmd('systemctl --user restart hermes-gateway.service', timeout=15)
    time.sleep(3)
    gw = read_gateway_state()
    return jsonify({
        'ok': code == 0,
        'output': out,
        'gateway_state': gw.get('gateway_state', 'unknown'),
    })

@app.route('/api/gateway/stop', methods=['POST'])
def api_gateway_stop():
    out, code = run_cmd('systemctl --user stop hermes-gateway.service', timeout=10)
    return jsonify({'ok': code == 0, 'output': out})

@app.route('/api/gateway/start', methods=['POST'])
def api_gateway_start():
    out, code = run_cmd('systemctl --user start hermes-gateway.service', timeout=10)
    time.sleep(3)
    gw = read_gateway_state()
    return jsonify({
        'ok': code == 0,
        'output': out,
        'gateway_state': gw.get('gateway_state', 'unknown'),
    })

# ── API: Cron jobs ────────────────────────────────────────────────────────────

@app.route('/api/cron')
def api_cron():
    out, code = run_cmd('hermes cron list --json 2>/dev/null')
    try:
        data = json.loads(out)
        if isinstance(data, dict) and 'jobs' in data:
            return jsonify(data['jobs'])
        return jsonify(data if isinstance(data, list) else [])
    except Exception:
        # fallback: return raw lines
        return jsonify([])

@app.route('/api/cron/<job_id>/pause', methods=['POST'])
def api_cron_pause(job_id):
    out, code = run_cmd(f'hermes cron pause {job_id}')
    return jsonify({'ok': code == 0, 'output': out})

@app.route('/api/cron/<job_id>/resume', methods=['POST'])
def api_cron_resume(job_id):
    out, code = run_cmd(f'hermes cron resume {job_id}')
    return jsonify({'ok': code == 0, 'output': out})

@app.route('/api/cron/<job_id>/run', methods=['POST'])
def api_cron_run(job_id):
    out, code = run_cmd(f'hermes cron run {job_id}')
    return jsonify({'ok': code == 0, 'output': out})

# ── API: Config ───────────────────────────────────────────────────────────────

@app.route('/api/config')
def api_config():
    try:
        with open(CONFIG_YAML) as f:
            content = f.read()
        return jsonify({'content': content})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── API: Diary ────────────────────────────────────────────────────────────────

DIARY_FILE = Path(__file__).parent / 'data' / 'diary.json'

def _load_diary():
    try:
        with open(DIARY_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {'version': 1, 'entries': []}

def _save_diary(data):
    data['lastUpdated'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
    with open(DIARY_FILE, 'w') as f:
        json.dump(data, f, indent=2)

@app.route('/api/diary', methods=['GET'])
def api_diary_get():
    return jsonify(_load_diary())

@app.route('/api/diary', methods=['POST'])
def api_diary_post():
    try:
        body = request.get_json()
        data = _load_diary()
        now = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        entry = {
            'id': f"diary-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            'date': body.get('date', datetime.now().strftime('%Y-%m-%d')),
            'type': body.get('type', 'summary'),
            'title': body.get('title', ''),
            'content': body.get('content', ''),
            'createdAt': now,
        }
        data['entries'].append(entry)
        _save_diary(data)
        return jsonify({'success': True, 'id': entry['id']})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/diary/<entry_id>', methods=['DELETE'])
def api_diary_delete(entry_id):
    try:
        data = _load_diary()
        data['entries'] = [e for e in data['entries'] if e['id'] != entry_id]
        _save_diary(data)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/diary/<entry_id>', methods=['PUT'])
def api_diary_put(entry_id):
    try:
        body = request.get_json()
        data = _load_diary()
        for e in data['entries']:
            if e['id'] == entry_id:
                e['title']   = body.get('title', e['title'])
                e['content'] = body.get('content', e['content'])
                e['type']    = body.get('type', e['type'])
                e['date']    = body.get('date', e['date'])
                break
        _save_diary(data)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── API: Scripts ──────────────────────────────────────────────────────────────

@app.route('/api/scripts')
def api_scripts_list():
    result = []
    for s in RUNNABLE_SCRIPTS:
        prefix = s['id'] + '_'
        logs = sorted([f for f in os.listdir(SCRIPTS_LOG_DIR) if f.startswith(prefix) and f.endswith('.log')], reverse=True)
        last_run = logs[0].replace('.log', '').split('_', 1)[-1] if logs else None
        result.append({**s, 'last_run': last_run, 'log_count': len(logs)})
    return jsonify({'scripts': result})

@app.route('/api/scripts/run', methods=['POST'])
def api_scripts_run():
    data = request.get_json(force=True, silent=True) or {}
    script_id = data.get('id', '').strip()
    meta = next((s for s in RUNNABLE_SCRIPTS if s['id'] == script_id), None)
    if not meta:
        return jsonify({'error': f'Unknown script: {script_id}'}), 404
    # Prevent duplicate runs
    for jid, job in _running_jobs.items():
        if job['script_id'] == script_id and job['status'] == 'running':
            return jsonify({'error': 'Already running', 'job_id': jid}), 409
    script_path = SCRIPTS_DIR / meta['script']
    if not script_path.exists():
        return jsonify({'error': f'Script not found: {meta["script"]}'}), 500
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    job_id = f"{script_id}_{ts}"
    log_path = SCRIPTS_LOG_DIR / f"{job_id}.log"
    with open(log_path, 'w') as lf:
        proc = subprocess.Popen(
            ['bash', str(script_path)],
            stdout=lf, stderr=subprocess.STDOUT,
            text=True, env={**os.environ, 'HOME': str(Path.home())}
        )
    _running_jobs[job_id] = {
        'pid': proc.pid, 'log_path': str(log_path),
        'script_id': script_id, 'started_at': ts,
        'status': 'running', 'returncode': None, 'proc': proc,
    }
    def _watch(jid, p):
        p.wait()
        _running_jobs[jid]['status'] = 'done' if p.returncode == 0 else 'error'
        _running_jobs[jid]['returncode'] = p.returncode
    threading.Thread(target=_watch, args=(job_id, proc), daemon=True).start()
    return jsonify({'job_id': job_id})

@app.route('/api/scripts/log/<job_id>')
def api_scripts_log(job_id):
    if '..' in job_id or '/' in job_id:
        return jsonify({'error': 'Invalid job_id'}), 400
    log_path = SCRIPTS_LOG_DIR / f"{job_id}.log"
    if not log_path.exists():
        return jsonify({'error': 'Log not found'}), 404
    with open(log_path) as f:
        content = f.read()
    job = _running_jobs.get(job_id, {})
    return jsonify({
        'job_id':     job_id,
        'status':     job.get('status', 'done'),
        'returncode': job.get('returncode'),
        'output':     content,
    })

@app.route('/api/scripts/jobs')
def api_scripts_jobs():
    result = []
    for jid, job in _running_jobs.items():
        result.append({
            'job_id':     jid,
            'script_id':  job['script_id'],
            'started_at': job['started_at'],
            'status':     job['status'],
            'returncode': job.get('returncode'),
        })
    return jsonify({'jobs': result})

# ── TTS endpoint ─────────────────────────────────────────────────────────────

@app.route('/api/tts', methods=['POST'])
def api_tts():
    """Generate TTS audio for a given text and return the audio file."""
    import json as _json, tempfile, shlex
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'text is required'}), 400

    hermes_venv_python = os.path.expanduser('~/.hermes/hermes-agent/venv/bin/python')
    hermes_agent_path  = os.path.expanduser('~/.hermes/hermes-agent')

    # Write a small runner script to a temp file
    runner = textwrap.dedent(f"""\
        import sys, json
        sys.path.insert(0, {repr(hermes_agent_path)})
        from tools.tts_tool import text_to_speech_tool
        result = text_to_speech_tool({repr(text)})
        print(result)
    """)

    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(runner)
            tmp_path = f.name

        proc = subprocess.run(
            [hermes_venv_python, tmp_path],
            capture_output=True, text=True, timeout=30
        )
        os.unlink(tmp_path)

        if proc.returncode != 0:
            return jsonify({'error': proc.stderr.strip() or 'TTS subprocess failed'}), 500

        info = _json.loads(proc.stdout.strip())
        if not info.get('success'):
            return jsonify({'error': info.get('error', 'TTS failed')}), 500

        file_path = info['file_path']
        import mimetypes
        mime = mimetypes.guess_type(file_path)[0] or 'audio/ogg'
        return send_file(file_path, mimetype=mime, as_attachment=False)
    except Exception as e:
        log.exception('TTS error')
        return jsonify({'error': str(e)}), 500


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    log.info(f'Starting Hermes App on http://0.0.0.0:{PORT}')
    from waitress import serve
    serve(app, host='0.0.0.0', port=PORT, threads=16)
