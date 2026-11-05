#!/usr/bin/env bash
# Starts or stops the services Infrahub needs inside the OSS Scanner image, all on localhost.
#
#   start-services.sh deps   Neo4j (7687), RabbitMQ (5672), Redis (6379) and the Prefect task manager (4200).
#                            Enough for the backend tests, which reset the database they use.
#   start-services.sh all    deps, plus the Infrahub API server on http://localhost:8000 and one task worker.
#                            Sign in as admin / infrahub, or send the header X-INFRAHUB-KEY: $INFRAHUB_INITIAL_ADMIN_TOKEN.
#   start-services.sh stop   Stops everything.
#
# Logs are in /var/log/infrahub-scanner.
set -euo pipefail

MODE="${1:-all}"
LOGS=/var/log/infrahub-scanner
mkdir -p "$LOGS"

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
export PREFECT_WORKER_QUERY_SECONDS=2
export PREFECT_SERVER_API_MAX_PARAMETER_SIZE=0

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

stop_all() {
    pkill -f "prefect worker start" || true
    pkill -f "gunicorn --config backend/infrahub/serve/gunicorn_config.py" || true
    pkill -f "infrahub.prefect_server.app:create_infrahub_prefect" || true
    neo4j stop > /dev/null 2>&1 || true
    rabbitmqctl stop > /dev/null 2>&1 || true
    redis-cli shutdown nosave > /dev/null 2>&1 || true
    echo "stopped"
}

start_deps() {
    # Without a network, the container's hostname is missing from /etc/hosts, and Neo4j refuses to start when
    # Java cannot resolve it.
    if ! getent hosts "$(hostname)" > /dev/null; then
        echo "127.0.0.1 $(hostname)" >> /etc/hosts
    fi

    redis-cli ping > /dev/null 2>&1 || redis-server --daemonize yes --logfile "$LOGS/redis.log"
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
    if ! curl -sf http://localhost:8000/api/config > /dev/null 2>&1; then
        (cd /src && gunicorn --config backend/infrahub/serve/gunicorn_config.py -w 1 \
            --logger-class infrahub.serve.log.GunicornLogger infrahub.server:app > "$LOGS/server.log" 2>&1 &)
    fi
    wait_for infrahub-server "curl -sf http://localhost:8000/api/config"

    if ! pgrep -f "prefect worker start" > /dev/null; then
        # The worker's metrics endpoint defaults to port 8000, which the API server already uses in this image.
        (cd /src && INFRAHUB_API_TOKEN="$INFRAHUB_INITIAL_AGENT_TOKEN" INFRAHUB_METRICS_PORT=9091 \
            prefect worker start --type infrahubasync --pool infrahub-worker --with-healthcheck \
            > "$LOGS/task-worker.log" 2>&1 &)
    fi
    wait_for task-worker "grep -q 'Worker .* started' $LOGS/task-worker.log"
}

case "$MODE" in
    deps) start_deps ;;
    all)
        start_deps
        start_app
        ;;
    stop) stop_all ;;
    *) echo "usage: $0 deps|all|stop" >&2; exit 2 ;;
esac
