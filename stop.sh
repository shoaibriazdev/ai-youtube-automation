#!/usr/bin/env bash
cd "$(dirname "$0")"
if [ -f data/server.pid ]; then kill "$(cat data/server.pid)" 2>/dev/null && echo "Server stopped." || echo "Server was not running."; rm -f data/server.pid; else echo "No running server found."; fi
