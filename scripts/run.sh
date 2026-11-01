#!/usr/bin/env bash
# Start the dashboard on http://localhost:8501   (add --demo for offline synthetic data)
set -e
cd "$(dirname "$0")/.."
. .venv/bin/activate
if [ "$1" = "--demo" ]; then export ISA_DEMO=1; fi
streamlit run app.py
