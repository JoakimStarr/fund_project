#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"
HOST="127.0.0.1"
PORT="8000"
APP_URL="http://$HOST:$PORT"
LOG_DIR="$ROOT_DIR/logs"
START_LOG="$LOG_DIR/start.log"
PID_FILE="$LOG_DIR/uvicorn.pid"

mkdir -p "$LOG_DIR"

if [[ ! -x "$PYTHON_BIN" ]]; then
  python3 -m venv "$VENV_DIR"
fi

"$PYTHON_BIN" -m pip install --upgrade pip >/dev/null
"$PYTHON_BIN" -m pip install -r "$ROOT_DIR/requirements.txt" >/dev/null

if pgrep -f "uvicorn app.main:app --app-dir backend --host $HOST --port $PORT" >/dev/null; then
  echo "服务已在运行: $APP_URL"
else
  nohup "$PYTHON_BIN" -m uvicorn app.main:app --app-dir backend --host "$HOST" --port "$PORT" > "$START_LOG" 2>&1 &
  echo $! > "$PID_FILE"
fi

for _ in {1..30}; do
  if "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import urllib.request
urllib.request.urlopen("http://127.0.0.1:8000/", timeout=2).read()
PY
  then
    break
  fi
  sleep 1
done

if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$APP_URL" >/dev/null 2>&1 &
fi

echo "服务已启动: $APP_URL"
echo "日志文件: $START_LOG"