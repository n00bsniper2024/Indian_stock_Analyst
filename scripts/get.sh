#!/usr/bin/env bash
# Indian Stock Analyst - one-line installer / updater for macOS and Linux.
#
#   Open Terminal and paste:
#     curl -fsSL https://raw.githubusercontent.com/n00bsniper2024/Indian_stock_Analyst/main/scripts/get.sh | bash
#
# What it does (no sudo, nothing outside your home folder):
#   1. downloads the latest code into ~/IndianStockAnalyst
#   2. installs "uv" (a small Python manager from astral.sh) if you don't have it; uv downloads its own Python 3.12,
#      so you do NOT need to install Python yourself and the system Python is left untouched
#   3. installs the app's libraries into a private folder (.venv) inside the app folder
#   4. adds an "Indian Stock Analyst" launcher (Desktop on macOS, app menu on Linux), then opens the dashboard
# Run the same line again any time to update. Your saved API keys (.env) and cached data are kept.
set -euo pipefail

REPO="n00bsniper2024/Indian_stock_Analyst"
BRANCH="${ISA_BRANCH:-main}"
DIR="${ISA_HOME:-$HOME/IndianStockAnalyst}"
step() { printf '\n\033[36m==> %s\033[0m\n' "$1"; }

step "Getting the latest Indian Stock Analyst ($BRANCH)"
if [ -n "${ISA_SOURCE_DIR:-}" ]; then
  SRC="$ISA_SOURCE_DIR"
else
  TMP="$(mktemp -d)"
  curl -fsSL "https://github.com/$REPO/archive/refs/heads/$BRANCH.tar.gz" | tar -xz -C "$TMP"
  SRC="$(find "$TMP" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
fi
mkdir -p "$DIR"
if [ "$(cd "$SRC" && pwd -P)" != "$(cd "$DIR" && pwd -P)" ]; then
  # copy the code, keeping the user's keys (.env), cache and environment
  (cd "$SRC" && tar --exclude=./.git --exclude=./.venv --exclude=./.cache --exclude=./.env --exclude=./.pytest_cache --exclude="__pycache__" -cf - .) | (cd "$DIR" && tar -xf -)
fi

step "Checking for uv (Python manager)"
UV="$(command -v uv || true)"
if [ -z "$UV" ]; then
  if [ -x "$HOME/.local/bin/uv" ]; then UV="$HOME/.local/bin/uv"
  elif [ -x "$HOME/.cargo/bin/uv" ]; then UV="$HOME/.cargo/bin/uv"
  else
    echo "Installing uv from astral.sh ..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    UV="$HOME/.local/bin/uv"
    [ -x "$UV" ] || { echo "uv did not install. See https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
  fi
fi

step "Installing Python 3.12 and the app's libraries (first time: a few minutes)"
[ -x "$DIR/.venv/bin/python" ] || "$UV" venv --python 3.12 "$DIR/.venv"
"$UV" pip install --python "$DIR/.venv/bin/python" -r "$DIR/requirements.txt"
[ -f "$DIR/.env" ] || cp "$DIR/.env.example" "$DIR/.env"
chmod 600 "$DIR/.env" || true
chmod +x "$DIR/scripts/"*.sh || true

step "Creating a launcher"
if [ "$(uname)" = "Darwin" ]; then
  L="$HOME/Desktop/Indian Stock Analyst.command"
  printf '#!/bin/bash\nexec "%s/scripts/start.sh"\n' "$DIR" > "$L"
  chmod +x "$L"
  echo "Double-click 'Indian Stock Analyst' on your Desktop to open it."
else
  APPS="$HOME/.local/share/applications"; mkdir -p "$APPS"
  cat > "$APPS/indian-stock-analyst.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=Indian Stock Analyst
Comment=AI equity research dashboard for NSE stocks
Exec="$DIR/scripts/start.sh"
Terminal=true
Categories=Office;Finance;
DESK
  echo "Open 'Indian Stock Analyst' from your applications menu, or run: $DIR/scripts/start.sh"
fi

printf '\n\033[32mInstalled in %s\033[0m\n' "$DIR"
if [ -z "${ISA_NO_LAUNCH:-}" ]; then
  step "Starting the dashboard (keep this window open while you use it; Ctrl+C stops it)"
  exec "$DIR/scripts/start.sh"
fi
