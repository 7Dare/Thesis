#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
YOLOV8_PYTHON="/home/ryh/miniconda3/envs/yolov8/bin/python"
LOCAL_PG_CTL="/home/ryh/miniconda3/bin/pg_ctl"
LOCAL_PSQL="/home/ryh/miniconda3/bin/psql"
LOCAL_PGDATA="${HOME}/pgsql-data"
ENABLE_RELOAD="${ENABLE_RELOAD:-0}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[ERROR] .env not found: $ENV_FILE" >&2
  echo "Create it with DATABASE_URL, e.g.:" >&2
  echo "DATABASE_URL=postgresql://postgres:12345@127.0.0.1:5432/study_room_db" >&2
  exit 1
fi

# Load env vars from .env
set -a
source "$ENV_FILE"
set +a

# Pick one Python runtime and use it for all checks + uvicorn startup.
if [[ -n "${CONDA_PREFIX:-}" && -x "${CONDA_PREFIX}/bin/python" ]]; then
  PY_BIN="${CONDA_PREFIX}/bin/python"
elif [[ -x "$YOLOV8_PYTHON" ]]; then
  PY_BIN="$YOLOV8_PYTHON"
else
  PY_BIN="$(command -v python3 || true)"
fi

if [[ -z "${PY_BIN:-}" || ! -x "$PY_BIN" ]]; then
  echo "[ERROR] python runtime not found." >&2
  exit 1
fi

# Basic checks
if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "[ERROR] DATABASE_URL is empty in .env" >&2
  exit 1
fi

if ! "$PY_BIN" -c "import uvicorn" >/dev/null 2>&1; then
  echo "[ERROR] uvicorn is missing in selected python: $PY_BIN" >&2
  exit 1
fi

if ! "$PY_BIN" -c "import fastapi" >/dev/null 2>&1; then
  echo "[ERROR] fastapi is missing in selected python: $PY_BIN" >&2
  exit 1
fi

if ! "$PY_BIN" -c "import websockets" >/dev/null 2>&1 && ! "$PY_BIN" -c "import wsproto" >/dev/null 2>&1; then
  echo "[ERROR] No WebSocket runtime found in selected python: $PY_BIN" >&2
  echo "Install one of:" >&2
  echo "  pip install 'uvicorn[standard]'" >&2
  echo "  pip install websockets" >&2
  echo "  pip install wsproto" >&2
  exit 1
fi

if ! "$PY_BIN" -c "import psycopg2" >/dev/null 2>&1 && ! "$PY_BIN" -c "import psycopg" >/dev/null 2>&1; then
  echo "[ERROR] DB driver missing. Install one of:" >&2
  echo "  pip install psycopg2-binary" >&2
  echo "  pip install 'psycopg[binary]'" >&2
  exit 1
fi

cd "$ROOT_DIR"
echo "[INFO] Using python: $PY_BIN"
echo "[INFO] Ensuring PostgreSQL is available"
if [[ -x "$LOCAL_PG_CTL" && -d "$LOCAL_PGDATA" ]]; then
  if "$LOCAL_PG_CTL" -D "$LOCAL_PGDATA" status >/dev/null 2>&1; then
    echo "[INFO] Local PostgreSQL is already running"
  else
    echo "[INFO] Starting local PostgreSQL from $LOCAL_PGDATA"
    "$LOCAL_PG_CTL" -D "$LOCAL_PGDATA" -l "$LOCAL_PGDATA/postgres.log" start
  fi
else
  echo "[INFO] Falling back to system PostgreSQL service"
  sudo service postgresql start
fi
echo "[INFO] Starting backend at http://0.0.0.0:8000"
if [[ "$ENABLE_RELOAD" == "1" ]]; then
  echo "[INFO] Uvicorn reload mode: ON"
  "$PY_BIN" -m uvicorn app.main:APP --host 0.0.0.0 --port 8000 --reload
else
  echo "[INFO] Uvicorn reload mode: OFF"
  "$PY_BIN" -m uvicorn app.main:APP --host 0.0.0.0 --port 8000
fi
