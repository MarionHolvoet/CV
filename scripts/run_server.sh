#!/bin/sh
# run_server.sh — Start the CV server in a loop.
# On each restart (triggered by the /exit webhook), pulls latest code and rebuilds.
#
# Usage on the server:
#   nohup bash scripts/run_server.sh > server.log 2>&1 &
#
# Or with systemd — see README for the unit file example.

set -e
REPO_DIR="$(git rev-parse --show-toplevel)"
cd "$REPO_DIR" || exit 1

while true; do
    echo "[run_server] Pulling latest code..."
    git pull --ff-only

    echo "[run_server] Building server..."
    go build -buildvcs=false -o main main.go

    echo "[run_server] Starting server..."
    ./main || true   # server exits with non-zero after /exit webhook — that's expected

    echo "[run_server] Server exited. Restarting in 2 seconds..."
    sleep 2
done
