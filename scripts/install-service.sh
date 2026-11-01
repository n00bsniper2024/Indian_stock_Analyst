#!/usr/bin/env bash
# Install the dashboard as a background service (Linux with systemd).
# It starts automatically when the machine boots and restarts itself if it crashes,
# so you no longer need to keep scripts/run.sh open.
#
# Usage (from the repo folder):
#   bash scripts/install-service.sh                     # this machine only  -> http://localhost:8501
#   bash scripts/install-service.sh --address 0.0.0.0   # reachable from other devices (password required)
#   bash scripts/install-service.sh --address 100.x.y.z # bind to one IP, e.g. your Tailscale IP
#   bash scripts/install-service.sh --port 8600         # different port
set -euo pipefail

SERVICE=indian-stock-analyst
ADDRESS=localhost
PORT=8501
while [ $# -gt 0 ]; do
  case "$1" in
    --address) ADDRESS="$2"; shift 2 ;;
    --port)    PORT="$2"; shift 2 ;;
    -h|--help) sed -n 2,12p "$0"; exit 0 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

REPO="$(cd "$(dirname "$0")/.." && pwd)"
RUN_USER="$(id -un)"
STREAMLIT="$REPO/.venv/bin/streamlit"

if ! command -v systemctl >/dev/null || [ ! -d /run/systemd/system ]; then
  echo "❌ systemd is not running on this machine, so a service cannot be installed."
  echo "   Use 'bash scripts/run.sh' instead, or see README → 'Run it permanently' for alternatives."
  exit 1
fi
if [ ! -x "$STREAMLIT" ]; then
  echo "❌ The app is not installed yet. Run:  bash scripts/install.sh   then run this script again."
  exit 1
fi
[ -f "$REPO/.env" ] || cp "$REPO/.env.example" "$REPO/.env"

# Anything other than localhost is reachable by other machines -> require a password,
# because the app uses the API key stored in .env (anyone who can open it could spend your credits).
case "$ADDRESS" in
  localhost|127.0.0.1|::1) ;;
  *)
    if ! grep -qE '^ISA_PASSWORD=.+' "$REPO/.env"; then
      PW="$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 16)"
      sed -i '/^ISA_PASSWORD=/d' "$REPO/.env"
      echo "ISA_PASSWORD=$PW" >> "$REPO/.env"
      echo "🔐 The dashboard will be reachable from other devices, so a password was added to .env:"
      echo "      $PW"
      echo "   (change it any time by editing ISA_PASSWORD in .env, then: sudo systemctl restart $SERVICE)"
    fi
    chmod 600 "$REPO/.env"
    ;;
esac

if command -v ss >/dev/null && ss -ltn "sport = :$PORT" | grep -q LISTEN; then
  if ! systemctl is-active --quiet "$SERVICE"; then
    echo "⚠️  Port $PORT is already in use — probably scripts/run.sh is still running in a terminal."
    echo "   Stop it (Ctrl+C in that terminal) or pick another port with --port, then run this again."
    exit 1
  fi
fi

UNIT="/etc/systemd/system/$SERVICE.service"
echo "Installing $UNIT (needs your sudo password)…"
sudo tee "$UNIT" >/dev/null <<EOF
[Unit]
Description=Indian Stock Analyst dashboard
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$REPO
ExecStart=$STREAMLIT run app.py --server.address=$ADDRESS --server.port=$PORT --server.headless=true
Restart=always
RestartSec=5
# basic hardening: no privilege escalation, private /tmp, OS directories read-only
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE" >/dev/null
sudo systemctl restart "$SERVICE"

echo -n "Starting"
HOST="$ADDRESS"; [ "$HOST" = "0.0.0.0" ] && HOST=127.0.0.1
for _ in $(seq 1 30); do
  if curl -fs "http://$HOST:$PORT/_stcore/health" >/dev/null 2>&1; then
    echo
    echo "✅ Dashboard is running as a service and will start automatically after every reboot."
    case "$ADDRESS" in
      localhost|127.0.0.1|::1) echo "   Open: http://localhost:$PORT  (on this machine — see README for opening it from your laptop)" ;;
      0.0.0.0) echo "   Open: http://$(hostname -I 2>/dev/null | awk '{print $1}'):$PORT  from devices on your network (password protected)" ;;
      *) echo "   Open: http://$ADDRESS:$PORT  (password protected)" ;;
    esac
    echo "   Status: sudo systemctl status $SERVICE    Logs: journalctl -u $SERVICE -f"
    exit 0
  fi
  echo -n "."; sleep 1
done
echo
echo "❌ The service did not come up. Last log lines:"
sudo journalctl -u "$SERVICE" -n 30 --no-pager
exit 1
