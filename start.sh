#!/usr/bin/env bash
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || { echo "Run ./setup.sh first"; exit 1; }
nohup .venv/bin/python -m ytauto serve > data/server.log 2>&1 &
sleep 2
echo "Dashboard: http://localhost:${YTAUTO_PORT:-8000}   (log: data/server.log, stop: ./stop.sh)"
(command -v xdg-open >/dev/null && xdg-open "http://localhost:${YTAUTO_PORT:-8000}" >/dev/null 2>&1) || true
