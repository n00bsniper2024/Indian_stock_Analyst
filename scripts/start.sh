#!/usr/bin/env bash
# Starts the dashboard and opens it in your browser (macOS / Linux). Keep the window open; Ctrl+C or closing it stops it.
cd "$(dirname "$0")/.."
PORT="${ISA_PORT:-8501}"
PY=".venv/bin/python"
open_url() { if command -v open >/dev/null 2>&1 && [ "$(uname)" = "Darwin" ]; then open "$1"; elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$1" >/dev/null 2>&1; fi; }
up() { "$PY" -c "import socket,sys; s=socket.socket(); s.settimeout(0.5); sys.exit(s.connect_ex(('127.0.0.1', $PORT)))" 2>/dev/null; }
if [ ! -x "$PY" ]; then echo "Not installed yet - run the installer line from the README first."; exit 1; fi
if up; then echo "Already running - opening http://localhost:$PORT"; open_url "http://localhost:$PORT"; exit 0; fi
( for _ in $(seq 1 170); do if up; then open_url "http://localhost:$PORT"; break; fi; sleep 0.7; done ) &
echo "Starting Indian Stock Analyst on http://localhost:$PORT ..."
exec "$PY" -m streamlit run app.py --server.port "$PORT"
