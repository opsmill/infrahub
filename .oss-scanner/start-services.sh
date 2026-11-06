#!/usr/bin/env bash
# Starts or stops the services Infrahub needs inside the OSS Scanner image. Clients reach them on localhost.
#
#   start-services.sh deps   Neo4j (7687), RabbitMQ (5672), Redis (6379) and the Prefect task manager (4200).
#                            Enough for the backend tests, which empty the database they use.
#   start-services.sh all    deps, plus the Infrahub API server on http://localhost:8000 and one task worker.
#                            Sign in as admin / infrahub, or send the header X-INFRAHUB-KEY: $INFRAHUB_INITIAL_ADMIN_TOKEN.
#                            Resets the database first after `deps`, or when the server cannot start or sign in the
#                            admin token, because the backend tests empty the database and remove the admin account.
#   start-services.sh stop   Stops everything.
#
# Logs are in /var/log/infrahub-scanner.
set -euo pipefail

MODE="${1:-all}"
LOGS=/var/log/infrahub-scanner
TESTS_MARKER=/var/lib/infrahub-scanner/database-used-by-tests
GUNICORN="gunicorn --config backend/infrahub/serve/gunicorn_config.py"
mkdir -p "$LOGS" "${TESTS_MARKER%/*}"

# Development defaults from docker-compose.yml; this image is never exposed outside the scanner.
export INFRAHUB_ADDRESS=http://localhost:8000
export INFRAHUB_INTERNAL_ADDRESS=http://localhost:8000
export INFRAHUB_INITIAL_ADMIN_TOKEN=06438eb2-8019-4776-878c-0941b1f1d1ec
export INFRAHUB_INITIAL_AGENT_TOKEN=44af444d-3b26-410d-9546-b758657e026c
export INFRAHUB_SECURITY_SECRET_KEY=327f747f-efac-42be-9e73-999f08f86b92
export INFRAHUB_STORAGE_LOCAL_PATH=/opt/infrahub/storage
export INFRAHUB_GIT_REPOSITORIES_DIRECTORY=/opt/infrahub/git
export INFRAHUB_PRODUCTION=false
export PREFECT_API_URL=http://localhost:4200/api

wait_for() {
    local name="$1" check="$2"
    for _ in $(seq 1 180); do
        if bash -c "$check" > /dev/null 2>&1; then
            echo "$name is up"
            return 0
        fi
        sleep 1
    done
    echo "$name did not start; see $LOGS" >&2
    tail -n 50 "$LOGS"/* >&2 || true
    exit 1
}

admin_token_works() {
    curl -sf -X POST http://localhost:8000/graphql \
        -H "X-INFRAHUB-KEY: $INFRAHUB_INITIAL_ADMIN_TOKEN" -H "Content-Type: application/json" \
        -d '{"query": "{ AccountProfile { id } }"}' | grep -q '"AccountProfile":{"id"'
}

stop_app() {
    pkill -f "prefect worker start" || true
    pkill -f "$GUNICORN" || true
    for _ in $(seq 1 30); do
        pgrep -f "$GUNICORN" > /dev/null || break
        sleep 1
    done
}

stop_all() {
    stop_app
    pkill -f "infrahub.prefect_server.app:create_infrahub_prefect" || true
    neo4j stop > /dev/null 2>&1 || true
    rabbitmqctl stop > /dev/null 2>&1 || true
    redis-cli shutdown nosave > /dev/null 2>&1 || true
    echo "stopped"
}

# Returns 1 as soon as the server process exits, so a server that cannot initialize the database fails fast.
start_server() {
    if ! curl -sf http://localhost:8000/api/config > /dev/null 2>&1; then
        (cd /src && $GUNICORN -w 1 --logger-class infrahub.serve.log.GunicornLogger infrahub.server:app \
            > "$LOGS/server.log" 2>&1 &)
    fi
    for _ in $(seq 1 180); do
        sleep 1
        if curl -sf http://localhost:8000/api/config > /dev/null 2>&1; then
            echo "infrahub-server is up"
            return 0
        fi
        pgrep -f "$GUNICORN" > /dev/null || return 1
    done
    return 1
}

reset_database() {
    echo "resetting the database, which the backend tests empty"
    stop_app
    (cd /src && INFRAHUB_DB_ADDRESS=localhost infrahub db reset --yes-graph > "$LOGS/db-reset.log" 2>&1)
    rm -f "$TESTS_MARKER"
}

start_deps() {
    # Without a network, the container's hostname is missing from /etc/hosts, and Neo4j refuses to start when
    # Java cannot resolve it.
    if ! getent hosts "$(hostname)" > /dev/null; then
        echo "127.0.0.1 $(hostname)" >> /etc/hosts
    fi

    mkdir -p /var/lib/redis
    redis-cli ping > /dev/null 2>&1 \
        || redis-server --daemonize yes --save '' --dir /var/lib/redis --logfile "$LOGS/redis.log"
    wait_for redis "redis-cli ping"

    if ! rabbitmq-diagnostics -q check_port_connectivity > /dev/null 2>&1; then
        rabbitmq-server > "$LOGS/rabbitmq.log" 2>&1 &
    fi
    wait_for rabbitmq "rabbitmq-diagnostics -q check_port_connectivity"

    neo4j status > /dev/null 2>&1 || neo4j start > "$LOGS/neo4j-start.log" 2>&1
    wait_for neo4j "curl -sf http://localhost:7474"

    if ! curl -sf http://localhost:4200/api/health > /dev/null 2>&1; then
        (cd /src && uvicorn --host 127.0.0.1 --port 4200 --factory infrahub.prefect_server.app:create_infrahub_prefect \
            > "$LOGS/task-manager.log" 2>&1 &)
    fi
    wait_for task-manager "curl -sf http://localhost:4200/api/health"
}

start_app() {
    # The server creates the admin account and tokens only when it initializes an empty database.
    if [ -f "$TESTS_MARKER" ] || ! start_server || ! admin_token_works; then
        reset_database
        start_server || { echo "infrahub-server did not start; see $LOGS" >&2; tail -n 50 "$LOGS/server.log" >&2; exit 1; }
        admin_token_works || { echo "the admin token does not work; see $LOGS" >&2; exit 1; }
    fi

    if ! pgrep -f "prefect worker start" > /dev/null; then
        : > "$LOGS/task-worker.log"
        # The worker's metrics endpoint defaults to port 8000, which the API server already uses in this image.
        (cd /src && INFRAHUB_API_TOKEN="$INFRAHUB_INITIAL_AGENT_TOKEN" INFRAHUB_METRICS_PORT=9091 \
            prefect worker start --type infrahubasync --pool infrahub-worker --with-healthcheck \
            > "$LOGS/task-worker.log" 2>&1 &)
    fi
    wait_for task-worker "grep -q 'Worker .* started' $LOGS/task-worker.log"
}

case "$MODE" in
    deps)
        start_deps
        touch "$TESTS_MARKER"
        ;;
    all)
        start_deps
        start_app
        ;;
    stop) stop_all ;;
    *) echo "usage: $0 deps|all|stop" >&2; exit 2 ;;
esac
