#!/usr/bin/env bash
# AI YouTube Automation Pro - setup for Linux / macOS
set -euo pipefail
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
command -v "$PY" >/dev/null || { echo "Python 3.10+ not found (sudo apt install python3 python3-venv)"; exit 1; }
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' || { echo "Python 3.10+ required"; exit 1; }
[ -x .venv/bin/python ] || "$PY" -m venv .venv
.venv/bin/python -m pip install --upgrade pip >/dev/null
.venv/bin/python -m pip install -r requirements.txt
mkdir -p data/secrets projects
[ -f .env ] || cp .env.example .env
command -v espeak-ng >/dev/null || echo "Tip: for offline 'sapi' voices on Linux install espeak-ng (sudo apt install espeak-ng)"
.venv/bin/python -m ytauto doctor || true
read -r -p "Install the Claude Code skills for your user? [y/N] " a; [[ "${a:-n}" =~ ^[Yy]$ ]] && .venv/bin/python scripts/install_skills.py
echo "Setup complete. Run ./start.sh and open http://localhost:8000"
