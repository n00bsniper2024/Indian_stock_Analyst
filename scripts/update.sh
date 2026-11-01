#!/usr/bin/env bash
# Pull the latest code, update packages, and restart the service if it is installed.
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --ff-only
. .venv/bin/activate
pip install -q -r requirements.txt
if systemctl is-enabled --quiet indian-stock-analyst 2>/dev/null; then
  sudo systemctl restart indian-stock-analyst
  echo "✅ Updated and restarted the service."
else
  echo "✅ Updated. Start it with: bash scripts/run.sh"
fi
