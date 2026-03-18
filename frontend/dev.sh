#!/bin/bash
# Frontend Dev Server Manager
# Usage: ./dev.sh {start|stop|restart|status|logs}

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SERVER_NAME="Frontend (Next.js)"
PROCESS_PATTERN="next dev"
LOG_FILE="logs/dev-server.log"
PID_FILE="logs/dev-server.pid"
PORT=3000
URL="http://localhost:$PORT"

# Create logs directory if it doesn't exist
mkdir -p logs

# Function to check if server is running
is_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$PID_FILE"
            return 1
        fi
    else
        if pgrep -f "$PROCESS_PATTERN" > /dev/null 2>&1; then
            return 0
        fi
        return 1
    fi
}

# Function to get PID
get_pid() {
    if [ -f "$PID_FILE" ]; then
        cat "$PID_FILE"
    else
        pgrep -f "$PROCESS_PATTERN" | head -1
    fi
}

# Function to start server
start_server() {
    if is_running; then
        echo -e "${BLUE}i${NC} $SERVER_NAME is already running (PID: $(get_pid))"
        echo -e "${BLUE}i${NC} Access at: $URL"
        echo -e "${BLUE}i${NC} View logs: ./dev.sh logs"
        return 0
    fi

    # Install dependencies if needed
    if [ ! -d "node_modules" ]; then
        echo -e "${BLUE}i${NC} Installing dependencies..."
        pnpm install
    fi

    echo -e "${GREEN}+${NC} Starting $SERVER_NAME..."

    pnpm run dev > "$LOG_FILE" 2>&1 &
    local pid=$!
    echo "$pid" > "$PID_FILE"

    sleep 3

    if ps -p $pid > /dev/null 2>&1; then
        echo -e "${GREEN}+${NC} $SERVER_NAME started successfully (PID: $pid)"
        echo -e "${GREEN}+${NC} Log file: $LOG_FILE"
        echo ""
        echo -e "${GREEN}->${NC} Access the frontend at: ${BLUE}$URL${NC}"
        echo ""
        echo "Commands:"
        echo "  ./dev.sh status   - Check server status"
        echo "  ./dev.sh logs     - View logs"
        echo "  ./dev.sh stop     - Stop server"
        echo "  ./dev.sh restart  - Restart server"
        echo ""
        echo "Recent logs:"
        tail -n 5 "$LOG_FILE" 2>/dev/null || echo "(No logs yet)"
    else
        echo -e "${RED}x${NC} Failed to start $SERVER_NAME"
        echo "Check $LOG_FILE for errors"
        rm -f "$PID_FILE"
        exit 1
    fi
}

# Function to stop server
stop_server() {
    if ! is_running; then
        echo -e "${BLUE}i${NC} $SERVER_NAME is not running"
        rm -f "$PID_FILE"
        return 0
    fi

    local pid=$(get_pid)
    echo -e "${YELLOW}x${NC} Stopping $SERVER_NAME (PID: $pid)..."

    kill "$pid" 2>/dev/null || true

    local count=0
    while ps -p "$pid" > /dev/null 2>&1 && [ $count -lt 5 ]; do
        sleep 1
        count=$((count + 1))
    done

    if ps -p "$pid" > /dev/null 2>&1; then
        echo -e "${YELLOW}x${NC} Force killing process..."
        kill -9 "$pid" 2>/dev/null || true
        sleep 1
    fi

    pkill -f "$PROCESS_PATTERN" 2>/dev/null || true
    rm -f "$PID_FILE"

    echo -e "${GREEN}+${NC} $SERVER_NAME stopped"
}

# Function to clean Next.js cache
clean_cache() {
    echo -e "${BLUE}i${NC} Cleaning Next.js cache..."
    rm -rf .next
    echo -e "${GREEN}+${NC} Cache cleaned"
}

# Function to restart server
restart_server() {
    echo -e "${BLUE}~${NC} Restarting $SERVER_NAME..."
    stop_server
    clean_cache
    sleep 1
    start_server
}

# Function to show status
show_status() {
    if is_running; then
        local pid=$(get_pid)
        echo -e "${GREEN}+${NC} $SERVER_NAME is ${GREEN}running${NC} (PID: $pid)"
        echo -e "${BLUE}->${NC} URL: $URL"
        echo -e "${BLUE}->${NC} Log: $LOG_FILE"
        if [ -n "$pid" ]; then
            local start_time=$(ps -p "$pid" -o lstart= 2>/dev/null || echo "Unknown")
            echo -e "${BLUE}->${NC} Started: $start_time"
        fi
    else
        echo -e "${RED}x${NC} $SERVER_NAME is ${RED}not running${NC}"
    fi
}

# Function to show logs
show_logs() {
    if [ ! -f "$LOG_FILE" ]; then
        echo -e "${RED}x${NC} Log file not found: $LOG_FILE"
        exit 1
    fi
    echo -e "${BLUE}i${NC} Showing logs from: $LOG_FILE"
    echo -e "${BLUE}i${NC} Press Ctrl+C to exit"
    echo ""
    tail -f "$LOG_FILE"
}

# Main script logic
case "${1:-}" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        restart_server
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    clean)
        clean_cache
        ;;
    *)
        echo "Frontend Dev Server Manager"
        echo ""
        echo "Usage: $0 {start|stop|restart|status|logs|clean}"
        echo ""
        echo "Commands:"
        echo "  start    - Start the dev server"
        echo "  stop     - Stop the dev server"
        echo "  restart  - Restart the dev server (clears cache)"
        echo "  status   - Check if server is running"
        echo "  logs     - View server logs (tail -f)"
        echo "  clean    - Clear Next.js cache (.next directory)"
        echo ""
        exit 1
        ;;
esac
