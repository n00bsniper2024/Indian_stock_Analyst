#!/usr/bin/env bash
# Stop the background service and remove it (your code, .env and cache are left untouched).
set -euo pipefail
SERVICE=indian-stock-analyst
sudo systemctl disable --now "$SERVICE" 2>/dev/null || true
sudo rm -f "/etc/systemd/system/$SERVICE.service"
sudo systemctl daemon-reload
echo "✅ Service removed. You can still start the dashboard manually with: bash scripts/run.sh"
