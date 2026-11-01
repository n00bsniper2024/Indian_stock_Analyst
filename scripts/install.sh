#!/usr/bin/env bash
# One-time setup on Linux / macOS. Run from the repo folder:  bash scripts/install.sh
set -e
cd "$(dirname "$0")/.."
PY=$(command -v python3 || command -v python)
if [ -z "$PY" ]; then echo "Python 3.10+ is required: https://www.python.org/downloads/"; exit 1; fi
"$PY" -c 'import sys; assert sys.version_info >= (3,10), "Python 3.10+ required"'
"$PY" -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
[ -f .env ] || cp .env.example .env
echo
echo "✅ Installed. Next:"
echo "   1) (optional) put your API key in .env"
echo "   2) bash scripts/run.sh"
