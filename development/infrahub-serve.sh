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
#   INFRAHUB_PG_BACKEND        subprocess (default, Phase 1) | embedded (Phase 2, free-threaded no-GIL)
#   INFRAHUB_FT_PYTHON         embedded only: the free-threaded python (default: `python` on PATH)
#   PG_EMBED_DIR               embedded only: pingora-granian pyembed fork-glue dir
#                              (default /usr/local/lib/pingora-granian/pyembed)
#   PINGORA_GRANIAN_BIN        supervisor binary (default pingora-granian;
#                              pingora-granian-embedded when INFRAHUB_PG_BACKEND=embedded)
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

# 3) Backend selection. subprocess (default, Phase 1) runs one stock granian
#    PROCESS per tier. embedded (Phase 2) runs each tier's granian workers as
#    THREADS in one process sharing a free-threaded (no-GIL) CPython — this is
#    what exercises the no-GIL throughput path.
PG_BACKEND="${INFRAHUB_PG_BACKEND:-subprocess}"
PINGORA_BIN="${PINGORA_GRANIAN_BIN:-pingora-granian}"

if [ "${PG_BACKEND}" = "embedded" ]; then
    # The embedded supervisor links an embedded CPython via PyO3 and drives
    # Granian's MTServer worker loop as in-process threads. It refuses to start
    # unless the GIL is disabled (FR-021). Derive every path from the free-threaded
    # venv python on PATH; the GIL-re-enabling deps are already neutralised
    # (orjson->msgspec shim in infrahub/__init__, lazy gRPC, no hiredis — see
    # pyproject.toml [tool.uv]).
    PINGORA_BIN="${PINGORA_GRANIAN_BIN:-pingora-granian-embedded}"
    FT_PYTHON="${INFRAHUB_FT_PYTHON:-$(command -v python)}"
    if ! "${FT_PYTHON}" -c 'import sys; sys.exit(0 if not sys._is_gil_enabled() else 1)' 2>/dev/null; then
        echo "infrahub-serve: FATAL — embedded backend needs a free-threaded interpreter (3.14t);" \
             "'${FT_PYTHON}' has the GIL enabled" >&2
        exit 2
    fi
    PG_EMBED_DIR="${PG_EMBED_DIR:-/usr/local/lib/pingora-granian/pyembed}"
    GRANIAN_SITE="$("${FT_PYTHON}" -c 'import granian, os; print(os.path.dirname(os.path.dirname(granian.__file__)))')"
    export PYO3_PYTHON="${FT_PYTHON}"
    export LD_LIBRARY_PATH="$("${FT_PYTHON}" -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))'):${LD_LIBRARY_PATH:-}"
    export PYTHONHOME="$("${FT_PYTHON}" -c 'import sys; print(sys.base_prefix)')"
    # Embedded interpreter import path: the venv site-packages (Granian + infrahub),
    # the pyembed fork-glue, and the app import root.
    export PG_EMBED_PYTHONPATH="${GRANIAN_SITE}:${PG_EMBED_DIR}:${APP_DIR}"
fi

echo "infrahub-serve: pingora-granian (${PG_BACKEND}) | app=${APP_TARGET} interactive=${INTERACTIVE_WORKERS} automation=${AUTOMATION_WORKERS} drain_grace=${DRAIN_GRACE}s listen=${PG_LISTEN}"
exec "${PINGORA_BIN}"
