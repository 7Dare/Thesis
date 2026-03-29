#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/ryh/Thesis"
API_DIR="$ROOT/code/backend/camera_api"
FRONT_DIR="$ROOT/code/frontend/camera_dashboard"

export YOLO_WEIGHTS="${YOLO_WEIGHTS:-$ROOT/results/yolo_demo3/weights/best.pt}"
export SOURCE="${SOURCE:-${CAMERA_INDEX:-0}}"
export DEVICE="${DEVICE:-0}"
export SHOW_WINDOW="${SHOW_WINDOW:-0}"
export CONF="${CONF:-0.10}"
export SKIP_CLASS0="${SKIP_CLASS0:-1}"

if [[ ! -f "$YOLO_WEIGHTS" ]]; then
  echo "Error: YOLO_WEIGHTS not found: $YOLO_WEIGHTS" >&2
  echo "Tip: export YOLO_WEIGHTS=$ROOT/results/yolo_demo3/weights/best.pt" >&2
  exit 1
fi

echo "Starting API on http://localhost:8000"
(
  cd "$API_DIR"
  uvicorn app:APP --host 0.0.0.0 --port 8000
) &

API_PID=$!

echo "Starting dashboard on http://localhost:8080"
(
  cd "$FRONT_DIR"
  python3 -m http.server 8080
) &

FRONT_PID=$!

cleanup() {
  kill "$API_PID" "$FRONT_PID" 2>/dev/null || true
}

trap cleanup EXIT

echo "Press Ctrl+C to stop."
wait
