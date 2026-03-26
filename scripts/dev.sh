#!/bin/bash
# Memship Dev Environment Manager
# Backend runs in Docker (API + DB), Frontend runs locally with pnpm
# Usage: ./scripts/dev.sh {start|stop|restart|status|logs|seed|test} [backend|frontend|all]

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

# Paths (relative to repo root)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_COMPOSE="$REPO_ROOT/backend/docker/docker-compose.yml"
FRONTEND_DIR="$REPO_ROOT/frontend"

# --- Backend (Docker) ---

backend_start() {
    echo -e "${GREEN}+${NC} Starting backend services (Docker)..."
    docker compose -f "$BACKEND_COMPOSE" up -d
    echo -e "${GREEN}+${NC} Backend services started"
    echo -e "${BLUE}->${NC} API:     http://localhost:8003"
    echo -e "${BLUE}->${NC} Docs:    http://localhost:8003/api/docs"
    echo -e "${BLUE}->${NC} DB:      localhost:5433"
}

backend_stop() {
    echo -e "${YELLOW}x${NC} Stopping backend services..."
    docker compose -f "$BACKEND_COMPOSE" down
    echo -e "${GREEN}+${NC} Backend services stopped"
}

backend_status() {
    echo -e "${BOLD}Backend (Docker):${NC}"
    if docker compose -f "$BACKEND_COMPOSE" ps --status running 2>/dev/null | grep -q "memship"; then
        docker compose -f "$BACKEND_COMPOSE" ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null
    else
        echo -e "  ${RED}x${NC} Not running"
    fi
}

backend_logs() {
    docker compose -f "$BACKEND_COMPOSE" logs -f api
}

# --- Celery Worker ---

worker_start() {
    echo -e "${GREEN}+${NC} Starting Celery worker..."
    docker compose -f "$BACKEND_COMPOSE" up -d celery-worker
    echo -e "${GREEN}+${NC} Celery worker started"
}

worker_stop() {
    echo -e "${YELLOW}x${NC} Stopping Celery worker..."
    docker compose -f "$BACKEND_COMPOSE" stop celery-worker
    echo -e "${GREEN}+${NC} Celery worker stopped"
}

worker_status() {
    echo -e "${BOLD}Celery Worker:${NC}"
    if docker compose -f "$BACKEND_COMPOSE" ps --status running 2>/dev/null | grep -q "celery"; then
        echo -e "  ${GREEN}+${NC} Running"
    else
        echo -e "  ${RED}x${NC} Not running"
    fi
}

worker_logs() {
    docker compose -f "$BACKEND_COMPOSE" logs -f celery-worker
}

# --- Frontend (local pnpm) ---

frontend_cmd() {
    (cd "$FRONTEND_DIR" && ./dev.sh "$1")
}

# --- Orchestrator ---

run_backend() {
    local cmd="$1"
    case "$cmd" in
        start)   backend_start ;;
        stop)    backend_stop ;;
        restart) backend_stop; sleep 1; backend_start ;;
        status)  backend_status ;;
        logs)    backend_logs ;;
    esac
}

run_frontend() {
    local cmd="$1"
    echo -e "${BOLD}Frontend:${NC}"
    frontend_cmd "$cmd"
}

run_all() {
    local cmd="$1"
    if [ "$cmd" = "logs" ]; then
        echo -e "${RED}x${NC} Cannot tail logs from multiple services simultaneously"
        echo "Use: $0 logs backend  OR  $0 logs frontend"
        exit 1
    fi
    echo -e "${BOLD}=== Running '$cmd' on all services ===${NC}"
    echo ""
    run_backend "$cmd"
    echo ""
    run_frontend "$cmd"
}

show_overall_status() {
    echo -e "${BOLD}=== Memship Dev Environment ===${NC}"
    echo ""
    backend_status
    echo ""
    worker_status
    echo ""
    run_frontend "status"
    echo ""
    echo -e "${BOLD}Quick Commands:${NC}"
    echo "  ./scripts/dev.sh start all      - Start everything"
    echo "  ./scripts/dev.sh stop all       - Stop everything"
    echo "  ./scripts/dev.sh status         - Show this status"
    echo "  ./scripts/dev.sh logs backend   - View API logs"
    echo "  ./scripts/dev.sh logs frontend  - View frontend logs"
}

# --- Main ---

ACTION="${1:-status}"
TARGET="${2:-all}"

case "$ACTION" in
    start|stop|restart|logs)
        case "$TARGET" in
            backend)  run_backend "$ACTION" ;;
            frontend) run_frontend "$ACTION" ;;
            worker)
                case "$ACTION" in
                    start)   worker_start ;;
                    stop)    worker_stop ;;
                    restart) worker_stop; sleep 1; worker_start ;;
                    logs)    worker_logs ;;
                esac
                ;;
            all)      run_all "$ACTION" ;;
            *)
                echo -e "${RED}x${NC} Invalid target: $TARGET"
                echo "Valid targets: backend, frontend, worker, all"
                exit 1
                ;;
        esac
        ;;
    status)
        show_overall_status
        ;;
    seed)
        if [ "$TARGET" = "test" ]; then
            echo -e "${BLUE}i${NC} Running seed command with test accounts..."
            docker compose -f "$BACKEND_COMPOSE" exec -it api uv run python -m app.cli.seed --test
        else
            echo -e "${BLUE}i${NC} Running seed command (interactive)..."
            docker compose -f "$BACKEND_COMPOSE" exec -it api uv run python -m app.cli.seed
        fi
        ;;
    reset)
        echo -e "${YELLOW}x${NC} Stopping frontend..."
        (cd "$FRONTEND_DIR" && ./dev.sh stop) 2>/dev/null || true
        echo -e "${YELLOW}x${NC} Stopping all backend services (including test db)..."
        docker compose -f "$BACKEND_COMPOSE" --profile test --profile tools down -v
        echo -e "${GREEN}+${NC} Rebuilding and starting backend services..."
        docker compose -f "$BACKEND_COMPOSE" up -d --build
        echo -e "${BLUE}i${NC} Waiting for API to be ready (migrations + startup)..."
        sleep 3
        until curl -sf http://localhost:8003/api/v1/health > /dev/null 2>&1; do
            sleep 2
        done
        echo -e "${BLUE}i${NC} Running seed with test accounts..."
        docker compose -f "$BACKEND_COMPOSE" exec -T api uv run python -m app.cli.seed --test
        echo -e "${GREEN}+${NC} Restarting frontend (clearing cache)..."
        (cd "$FRONTEND_DIR" && ./dev.sh restart)
        echo -e "${GREEN}+${NC} Reset complete"
        ;;
    test)
        echo -e "${BLUE}i${NC} Running backend tests..."
        docker compose -f "$BACKEND_COMPOSE" --profile test up -d db-test
        sleep 2
        (cd "$REPO_ROOT/backend" && uv run pytest tests/ -v)
        ;;
    e2e)
        echo -e "${BLUE}i${NC} Running Cypress E2E tests..."
        (cd "$REPO_ROOT/e2e" && pnpm test)
        ;;
    e2e:open)
        echo -e "${BLUE}i${NC} Opening Cypress GUI..."
        (cd "$REPO_ROOT/e2e" && pnpm cypress:open)
        ;;
    e2e:parallel)
        echo -e "${BLUE}i${NC} Running Cypress E2E tests in parallel..."
        (cd "$REPO_ROOT/e2e" && pnpm test:parallel)
        ;;
    *)
        echo -e "${BOLD}Memship Dev Environment Manager${NC}"
        echo ""
        echo "Usage: $0 {start|stop|restart|status|logs|seed|test} [backend|frontend|all]"
        echo ""
        echo -e "${BOLD}Commands:${NC}"
        echo "  start [target]    - Start services"
        echo "  stop [target]     - Stop services"
        echo "  restart [target]  - Restart services"
        echo "  status            - Show status of all services"
        echo "  logs [target]     - View logs (requires specific target)"
        echo "  seed              - Run database seed command (interactive)"
        echo "  seed test         - Seed with test accounts (no prompts)"
        echo "  reset             - Wipe DB, restart backend, and re-seed with test data"
        echo "  test              - Run backend tests"
        echo "  e2e               - Run Cypress E2E tests (headless)"
        echo "  e2e:open          - Open Cypress GUI (interactive)"
        echo ""
        echo -e "${BOLD}Targets:${NC}"
        echo "  backend    - API + DB (Docker, port 8003)"
        echo "  frontend   - Next.js dev server (local, port 3000)"
        echo "  all        - Both services (default)"
        echo ""
        echo -e "${BOLD}Examples:${NC}"
        echo "  $0 start all          # Start everything"
        echo "  $0 stop frontend      # Stop only frontend"
        echo "  $0 logs backend       # View API logs"
        echo "  $0 seed               # Run initial setup (interactive)"
        echo "  $0 seed test          # Seed with test accounts"
        echo "  $0 reset              # Wipe DB and re-seed with test data"
        echo "  $0 test               # Run backend tests"
        echo ""
        exit 1
        ;;
esac
