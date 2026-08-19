#!/bin/bash
# Memship Dev Environment Manager
# Backend runs in Docker (API + DB), Frontend runs locally with pnpm
# Usage: ./scripts/dev.sh {start|stop|restart|status|logs|seed|test} [backend|frontend|worker|beat|all]

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

# --- Celery Beat (scheduler) ---

beat_start() {
    echo -e "${GREEN}+${NC} Starting Celery beat..."
    docker compose -f "$BACKEND_COMPOSE" up -d celery-beat
    echo -e "${GREEN}+${NC} Celery beat started"
}

beat_stop() {
    echo -e "${YELLOW}x${NC} Stopping Celery beat..."
    docker compose -f "$BACKEND_COMPOSE" stop celery-beat
    echo -e "${GREEN}+${NC} Celery beat stopped"
}

beat_status() {
    echo -e "${BOLD}Celery Beat:${NC}"
    if docker compose -f "$BACKEND_COMPOSE" ps --status running 2>/dev/null | grep -q "celery-beat"; then
        echo -e "  ${GREEN}+${NC} Running"
    else
        echo -e "  ${RED}x${NC} Not running"
    fi
}

beat_logs() {
    docker compose -f "$BACKEND_COMPOSE" logs -f celery-beat
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
    beat_status
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


# --- Credentials & exposure ---

# The dev stack is weak on purpose. That is fine on loopback and dangerous the
# moment anything is published wider, so say so rather than assume the developer
# remembers which network they joined.
warn_if_exposed() {
    local bind="${DEV_BIND:-127.0.0.1}"
    [ "$bind" = "127.0.0.1" ] && return 0
    echo -e "${RED}${BOLD}!! DEV_BIND=$bind — the dev stack is on every interface.${NC}"
    echo -e "${YELLOW}   Fixed database password, Redis without auth, and any seeded accounts"
    echo -e "   are reachable by anyone on this network. Do not do this on a network"
    echo -e "   you do not control.${NC}"
    if has_test_accounts; then
        echo -e "${RED}${BOLD}   This database holds the e2e test accounts, whose passwords are"
        echo -e "   published in this repository. Anyone here can sign in as super admin."
        echo -e "   Run './scripts/dev.sh passwd' or reseed with 'seed demo'.${NC}"
    fi
}

has_test_accounts() {
    docker compose -f "$BACKEND_COMPOSE" exec -T db \
        psql -U memship -d memship_db -tAc \
        "select 1 from users where email = 'super@examplee6e3b1.com' limit 1" 2>/dev/null | grep -q 1
}

gen_password() {
    # Avoid characters that need quoting when a developer pastes this around.
    LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 24
}

# --- Main ---

ACTION="${1:-status}"
TARGET="${2:-all}"

case "$ACTION" in
    start|stop|restart|logs)
        [ "$ACTION" = "start" ] && warn_if_exposed
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
            beat)
                case "$ACTION" in
                    start)   beat_start ;;
                    stop)    beat_stop ;;
                    restart) beat_stop; sleep 1; beat_start ;;
                    logs)    beat_logs ;;
                esac
                ;;
            all)      run_all "$ACTION" ;;
            *)
                echo -e "${RED}x${NC} Invalid target: $TARGET"
                echo "Valid targets: backend, frontend, worker, beat, all"
                exit 1
                ;;
        esac
        ;;
    status)
        show_overall_status
        ;;
    passwd)
        # Thin wrapper over the same CLI every environment uses. The password goes
        # in on the environment, never in argv, so it stays out of `ps` and history.
        EMAIL="${2:-dev@localhost}"
        NEWPW="$(gen_password)"
        echo -e "${BLUE}i${NC} Setting the super admin password for $EMAIL..."
        if MEMSHIP_ADMIN_PASSWORD="$NEWPW" docker compose -f "$BACKEND_COMPOSE" \
                exec -T -e MEMSHIP_ADMIN_PASSWORD api \
                python -m app.cli.seed --admin-email "$EMAIL" >/dev/null; then
            echo -e "${GREEN}+${NC} Super admin: $EMAIL"
            echo -e "${GREEN}+${NC} Password:    $NEWPW"
            echo -e "${YELLOW}i${NC} Shown once — it is stored only as a hash."
        else
            echo -e "${RED}x${NC} Could not set the password. Is the API up?"
            exit 1
        fi
        ;;
    seed)
        if [ "$TARGET" = "test" ]; then
            echo -e "${BLUE}i${NC} Running setup with the fixed e2e test accounts..."
            warn_if_exposed
            docker compose -f "$BACKEND_COMPOSE" exec -it api python -m app.cli.seed --test
        elif [ "$TARGET" = "demo" ]; then
            # Same sample data as `seed test`, but nothing a stranger could look up:
            # the super admin password is generated here and the demo club generates
            # the rest. Use this unless you are running the Cypress suite.
            DEMOPW="$(gen_password)"
            echo -e "${BLUE}i${NC} Seeding a demo club with generated credentials..."
            MEMSHIP_ADMIN_PASSWORD="$DEMOPW" docker compose -f "$BACKEND_COMPOSE" \
                exec -T -e MEMSHIP_ADMIN_PASSWORD api \
                python -m app.cli.seed --admin-email dev@localhost --demo
            echo ""
            echo -e "${GREEN}+${NC} Super admin: dev@localhost"
            echo -e "${GREEN}+${NC} Password:    $DEMOPW"
            echo -e "${YELLOW}i${NC} Shown once — it is stored only as a hash."
        else
            echo -e "${BLUE}i${NC} Running the interactive setup..."
            docker compose -f "$BACKEND_COMPOSE" exec -it api python -m app.cli.seed
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
        docker compose -f "$BACKEND_COMPOSE" exec -T api python -m app.cli.seed --test
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
        echo "Usage: $0 {start|stop|restart|status|logs|seed|passwd|test|e2e} [backend|frontend|worker|beat|all]"
        echo ""
        echo -e "${BOLD}Commands:${NC}"
        echo "  start [target]    - Start services"
        echo "  stop [target]     - Stop services"
        echo "  restart [target]  - Restart services"
        echo "  status            - Show status of all services"
        echo "  logs [target]     - View logs (requires specific target)"
        echo "  seed              - Run the interactive setup (same on every environment)"
        echo "  seed demo         - Seed a demo club with generated credentials (prefer this)"
        echo "  seed test         - Seed the fixed e2e test accounts, published in this repo"
        echo "  passwd [email]    - Set the super admin password to a fresh generated one"
        echo "  reset             - Wipe DB, restart backend, and re-seed with test data"
        echo "  test              - Run backend tests"
        echo "  e2e               - Run Cypress E2E tests (headless)"
        echo "  e2e:open          - Open Cypress GUI (interactive)"
        echo ""
        echo -e "${BOLD}Targets:${NC}"
        echo "  backend    - API + DB + Redis + worker + beat (Docker, port 8003)"
        echo "  worker     - Celery worker only"
        echo "  beat       - Celery beat scheduler only"
        echo "  frontend   - Next.js dev server (local, port 3000)"
        echo "  all        - Both services (default)"
        echo ""
        echo -e "${BOLD}Examples:${NC}"
        echo "  $0 start all          # Start everything"
        echo "  $0 stop frontend      # Stop only frontend"
        echo "  $0 logs backend       # View API logs"
        echo "  $0 seed               # Run initial setup (interactive)"
        echo "  $0 seed demo          # Seed with generated credentials"
        echo "  $0 seed test          # Seed with the fixed e2e accounts"
        echo "  $0 passwd             # Rotate the super admin password"
        echo "  $0 reset              # Wipe DB and re-seed with test data"
        echo "  $0 test               # Run backend tests"
        echo ""
        exit 1
        ;;
esac
