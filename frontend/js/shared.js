// Hermes App - Shared utilities

// Mark active sidebar link based on current page
(function() {
  const path = window.location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.sidebar a').forEach(a => {
    const href = a.getAttribute('href') || '';
    if (href === path || (path === '' && href === 'index.html')) {
      a.classList.add('active');
    }
  });
})();

// Toast notifications
function toast(msg, type = 'blue', duration = 3000) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => el.remove(), duration);
}

// Copy to clipboard with feedback
function copyText(text, btn) {
  navigator.clipboard.writeText(text).then(() => {
    const orig = btn ? btn.textContent : '';
    if (btn) btn.textContent = 'Copied!';
    toast('Copied to clipboard', 'green', 1500);
    if (btn) setTimeout(() => btn.textContent = orig, 1500);
  });
}

// Format numbers
function fmtNum(n) {
  if (n == null) return '—';
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
  return n.toString();
}

// Format cost
function fmtCost(usd) {
  if (usd == null || usd === 0) return '—';
  if (usd < 0.001) return '<$0.001';
  return '$' + usd.toFixed(3);
}

// Format timestamp
function fmtTime(ts) {
  if (!ts) return '—';
  const d = new Date(ts * 1000);
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function fmtRelative(ts) {
  if (!ts) return '—';
  const diff = Date.now() / 1000 - ts;
  if (diff < 60) return 'just now';
  if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
  if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
  return Math.floor(diff / 86400) + 'd ago';
}

// Source badge
function sourceBadge(source) {
  const map = {
    cli: ['badge-purple', '💻 CLI'],
    telegram: ['badge-blue', '📱 Telegram'],
    discord: ['badge-blue', '🎮 Discord'],
    api_server: ['badge-green', '🌐 Web'],
    webchat: ['badge-green', '🌐 Web'],
    cron: ['badge-yellow', '⏰ Cron'],
    delegation: ['badge', '🤖 Agent'],
  };
  const [cls, label] = map[source] || ['badge', source];
  return `<span class="badge ${cls}">${label}</span>`;
}
