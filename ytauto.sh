#!/usr/bin/env bash
HERE="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$HERE${PYTHONPATH:+:$PYTHONPATH}"
exec "$HERE/.venv/bin/python" -m ytauto "$@"
