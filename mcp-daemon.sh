#!/usr/bin/env bash
# Simple controller script for running the Facebook MCP server.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${MCP_SERVER_DIR:-$SCRIPT_DIR}"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
PID_FILE="$PROJECT_DIR/server.pid"
LOG_FILE="$PROJECT_DIR/server.log"

COLOR_RED='\033[0;31m'
COLOR_GREEN='\033[0;32m'
COLOR_YELLOW='\033[1;33m'
COLOR_BLUE='\033[0;34m'
COLOR_RESET='\033[0m'

echo -e "${COLOR_BLUE}MCP Server Controller${COLOR_RESET}"
echo "======================="

ensure_environment() {
    if [ ! -d "$PROJECT_DIR" ]; then
        echo -e "${COLOR_RED}Project directory not found: $PROJECT_DIR${COLOR_RESET}"
        return 1
    fi

    if [ ! -x "$VENV_PYTHON" ]; then
        echo -e "${COLOR_RED}Virtual environment not found at $VENV_PYTHON${COLOR_RESET}"
        echo "Create it with: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
        return 1
    fi

    if [ ! -f "$PROJECT_DIR/.env" ]; then
        cat > "$PROJECT_DIR/.env" <<'EOF'
# Fill in your long-lived Facebook user or page access token.
FACEBOOK_ACCESS_TOKEN=replace_with_your_token

# Optional overrides
#HOST=127.0.0.1
#PORT=8000
EOF
        echo -e "${COLOR_YELLOW}Created default .env; update FACEBOOK_ACCESS_TOKEN before running.${COLOR_RESET}"
    fi

    mkdir -p "$PROJECT_DIR/.mcp_cache"

    # shellcheck disable=SC1090
    source "$PROJECT_DIR/.env"

    HOST="${HOST:-127.0.0.1}"
    PORT="${PORT:-8001}"
}

run_server() {
    ensure_environment || return 1

    echo -e "${COLOR_GREEN}Starting server on http://${HOST}:${PORT}${COLOR_RESET}"
    echo "Press Ctrl+C to stop."

    cd "$PROJECT_DIR" || exit 1
    exec "$VENV_PYTHON" -m uvicorn app.main:app --host "$HOST" --port "$PORT"
}

start_server() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo -e "${COLOR_YELLOW}Server already running (PID: $(cat "$PID_FILE"))${COLOR_RESET}"
        return 0
    fi

    ensure_environment || return 1

    echo -e "${COLOR_GREEN}Starting server in background...${COLOR_RESET}"
    cd "$PROJECT_DIR" || exit 1

    nohup "$VENV_PYTHON" -m uvicorn app.main:app --host "$HOST" --port "$PORT" > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    sleep 2

    if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo -e "${COLOR_GREEN}Server started (PID: $(cat "$PID_FILE"))${COLOR_RESET}"
        echo "Log file: $LOG_FILE"
    else
        echo -e "${COLOR_RED}Failed to start server; see $LOG_FILE for details.${COLOR_RESET}"
        rm -f "$PID_FILE"
        return 1
    fi
}

stop_server() {
    if [ ! -f "$PID_FILE" ]; then
        echo -e "${COLOR_YELLOW}Server not running.${COLOR_RESET}"
        return 0
    fi

    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo -e "${COLOR_YELLOW}Stopping server (PID: $PID)...${COLOR_RESET}"
        kill "$PID"
        sleep 2
        if kill -0 "$PID" 2>/dev/null; then
            echo -e "${COLOR_YELLOW}Force stopping server...${COLOR_RESET}"
            kill -9 "$PID"
        fi
    else
        echo -e "${COLOR_YELLOW}Process not active.${COLOR_RESET}"
    fi

    rm -f "$PID_FILE"
    echo -e "${COLOR_GREEN}Server stopped.${COLOR_RESET}"
}

status_server() {
    ensure_environment || return 1

    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        PID=$(cat "$PID_FILE")
        echo -e "${COLOR_GREEN}Server running (PID: $PID)${COLOR_RESET}"
        echo "URL: http://${HOST}:${PORT}"
        if command -v curl >/dev/null 2>&1; then
            if curl -s "http://${HOST}:${PORT}/health" | grep -q '"status":"ok"'; then
                echo "Health check: OK"
            else
                echo "Health check: FAILED"
            fi
        fi
    else
        echo -e "${COLOR_RED}Server not running.${COLOR_RESET}"
        rm -f "$PID_FILE"
    fi
}

restart_server() {
    stop_server
    start_server
}

show_logs() {
    if [ ! -f "$LOG_FILE" ]; then
        echo -e "${COLOR_YELLOW}Log file missing: $LOG_FILE${COLOR_RESET}"
        return 1
    fi
    tail -f "$LOG_FILE"
}

usage() {
    cat <<'EOF'
Usage: ./mcp-daemon.sh [command]

Commands:
  run       Start server in foreground
  start     Start server in background
  stop      Stop background server
  restart   Restart background server
  status    Show server status
  logs      Tail server log file
  help      Show this message
EOF
}

COMMAND="${1:-help}"

case "$COMMAND" in
    run) run_server ;;
    start) start_server ;;
    stop) stop_server ;;
    restart) restart_server ;;
    status) status_server ;;
    logs) show_logs ;;
    help|*) usage ;;
esac
