#!/bin/bash
set -e

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DEFAULT_BACKUP_DIR="/home/neo/Downloads/Backups_Hermes"
BACKUP_DIR="${1:-$DEFAULT_BACKUP_DIR}" # Use first argument or default

DEST="${BACKUP_DIR}/hermes-app_${TIMESTAMP}.tar.gz"
SRC="/home/neo/hermes-app"

echo "🗂️  Hermes App Backup"
echo "📅 $(date '+%Y-%m-%d %H:%M:%S')"
echo "📦 Source: $SRC"
echo "💾 Destination: $DEST"
echo ""

mkdir -p "$BACKUP_DIR"

echo "⏳ Creating archive..."
tar -czf "$DEST" \
  --exclude="$SRC/venv" \
  --exclude="$SRC/logs" \
  --exclude="$SRC/__pycache__" \
  --exclude="$SRC/**/__pycache__" \
  -C / "${SRC#/}"

SIZE=$(du -sh "$DEST" | cut -f1)
echo ""
echo "✅ Done! $DEST ($SIZE)"

# Keep only last 10 backups
echo ""
echo "🧹 Cleaning old backups (keeping last 10)..."
ls -t "${BACKUP_DIR}"/hermes-app_*.tar.gz 2>/dev/null | tail -n +11 | xargs -r rm -v
echo "✅ Cleanup complete"
