#!/usr/bin/env bash
# Infrahub API server launcher under pingora-granian (FR-009/010/011).
#
# Replaces the gunicorn launch command. pingora-granian is a pure-Rust Pingora
# supervisor that header-routes (X-Tier) to per-tier Granian worker pools over
# Unix sockets, all in one process — giving tier isolation, graceful drain, and
# zero-downtime binary upgrade with no change to the Infrahub API.
#
# This launcher:
#   1. re-homes the prometheus-multiproc cleanup the gunicorn worker used to do
#      (once, at startup — not per worker),
#   2. renders the tier topology from env (so workers/drain-grace/socket-dir are
#      parameterised by the deployment), unless PG_CONFIG_FILE is provided,
#   3. execs the pingora-granian supervisor.
#
# Env knobs:
#   WEB_CONCURRENCY            interactive-tier workers (default 4)
#   INFRAHUB_AUTOMATION_WORKERS  automation-tier workers (default 2)
#   INFRAHUB_APP_TARGET        ASGI app target (default infrahub.server:app;
#                              enterprise sets infrahub_enterprise.server:app)
#   INFRAHUB_APP_DIR           app working dir / import root (default /source)
#   PG_DRAIN_GRACE             drain grace seconds (default 90, == gunicorn timeout)
#   PG_SOCKET_DIR              per-tier UDS dir (default /tmp/pingora-granian)
#   PG_LISTEN                  gateway bind (default 0.0.0.0:8000)
#   PG_CONFIG_FILE             explicit tier config; skips env-rendering when set
set -euo pipefail

APP_TARGET="${INFRAHUB_APP_TARGET:-infrahub.server:app}"
APP_DIR="${INFRAHUB_APP_DIR:-/source}"
DRAIN_GRACE="${PG_DRAIN_GRACE:-90}"
INTERACTIVE_WORKERS="${WEB_CONCURRENCY:-4}"
AUTOMATION_WORKERS="${INFRAHUB_AUTOMATION_WORKERS:-2}"
export PG_SOCKET_DIR="${PG_SOCKET_DIR:-/tmp/pingora-granian}"
export PG_LISTEN="${PG_LISTEN:-0.0.0.0:8000}"
mkdir -p "${PG_SOCKET_DIR}"

# 1) Re-homed prometheus-multiproc cleanup (was InfrahubUvicorn.__init__): clear
#    the multiproc dir ONCE at container start, before any worker boots.
if [ -n "${PROMETHEUS_MULTIPROC_DIR:-}" ] && [ -d "${PROMETHEUS_MULTIPROC_DIR}" ]; then
    find "${PROMETHEUS_MULTIPROC_DIR}" -mindepth 1 -delete 2>/dev/null || true
fi

# 2) Render the tier topology from env unless an explicit config file is given.
#    interactive = the default tier (SPA/UI + unheadered traffic); automation =
#    heavy SDK traffic routed via `X-Tier: automation`, isolated from interactive.
if [ -z "${PG_CONFIG_FILE:-}" ]; then
    PG_CONFIG_FILE="$(mktemp /tmp/pingora-granian-tiers.XXXXXX.toml)"
    cat > "${PG_CONFIG_FILE}" <<EOF
default_tier = "interactive"
drain_grace = ${DRAIN_GRACE}

[[tier]]
name = "interactive"
workers = ${INTERACTIVE_WORKERS}
app = "${APP_TARGET}"
app_dir = "${APP_DIR}"
interface = "asgi"

[[tier]]
name = "automation"
workers = ${AUTOMATION_WORKERS}
app = "${APP_TARGET}"
app_dir = "${APP_DIR}"
interface = "asgi"
EOF
    export PG_CONFIG_FILE
fi

echo "infrahub-serve: pingora-granian | app=${APP_TARGET} interactive=${INTERACTIVE_WORKERS} automation=${AUTOMATION_WORKERS} drain_grace=${DRAIN_GRACE}s listen=${PG_LISTEN}"
exec pingora-granian
