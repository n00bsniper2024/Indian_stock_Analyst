#!/usr/bin/env bash
# Start the dashboard in this terminal on http://localhost:8501   (add --demo for offline synthetic data)
# To keep it running permanently instead, use: bash scripts/install-service.sh
set -e
cd "$(dirname "$0")/.."
if command -v systemctl >/dev/null && systemctl is-active --quiet indian-stock-analyst 2>/dev/null; then
  echo "ℹ️  The dashboard is already running as a background service — just open it in your browser."
  echo "   (Restart it with: sudo systemctl restart indian-stock-analyst)"
  exit 0
fi
. .venv/bin/activate
if [ "$1" = "--demo" ]; then export ISA_DEMO=1; fi
streamlit run app.py
