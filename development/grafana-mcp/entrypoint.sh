#!/bin/sh
# Entrypoint of the Grafana MCP server in the observability Compose stack.
#
# mcp-grafana 2.0.2 starts without authentication when no caller token is set, and
# serves plain HTTP unless it gets a certificate. This check refuses both cases
# before the server starts, so the token is required and never crosses a network
# unencrypted. The server only reads Grafana: every write tool and the tool that
# calls any Grafana API route are off. The documentation and plugin tools are off
# too, because they send the search text to grafana.com.
set -eu

refuse() {
    echo "$1" >&2
    exit 1
}

token="${INFRAHUB_GRAFANA_MCP_TOKEN:-}"
allowed_hosts="${INFRAHUB_GRAFANA_MCP_ALLOWED_HOSTS:-localhost:8100,127.0.0.1:8100}"
listen_address="${INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS:-127.0.0.1}"
tls_cert_file="${INFRAHUB_GRAFANA_MCP_TLS_CERT_FILE:-}"
tls_key_file="${INFRAHUB_GRAFANA_MCP_TLS_KEY_FILE:-}"

if [ -z "$token" ]; then
    refuse "INFRAHUB_GRAFANA_MCP_TOKEN is not set: set it to the token that AI assistants send"
fi

tls=off
if [ -n "$tls_cert_file" ] && [ -n "$tls_key_file" ]; then
    tls=on
elif [ -n "$tls_cert_file" ] || [ -n "$tls_key_file" ]; then
    refuse "Set both INFRAHUB_GRAFANA_MCP_TLS_CERT_FILE and INFRAHUB_GRAFANA_MCP_TLS_KEY_FILE, or neither"
fi

is_loopback() {
    case "$1" in
        ::1 | "[::1]") return 0 ;;
    esac
    # An IPv4 address in 127.0.0.0/8: "127" and three more groups of digits.
    echo "$1" | grep -Eq '^127(\.[0-9]{1,3}){3}$'
}

if [ "$tls" = off ] && ! is_loopback "$listen_address"; then
    refuse "INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS is $listen_address, which is open to a network: set INFRAHUB_GRAFANA_MCP_TLS_CERT_FILE and INFRAHUB_GRAFANA_MCP_TLS_KEY_FILE"
fi

set -- \
    --transport streamable-http \
    --address 0.0.0.0:8000 \
    --allowed-hosts "$allowed_hosts" \
    --usage-stats=disabled \
    --disable-write \
    --disable-api \
    --disable-docs \
    --disable-plugin

if [ "$tls" = on ]; then
    # The two settings are paths on the Docker host; Compose mounts the files at these paths.
    set -- "$@" \
        --server.tls-cert-file /etc/grafana-mcp/tls/tls.crt \
        --server.tls-key-file /etc/grafana-mcp/tls/tls.key
fi

# The server reads the caller token from its environment, so the value is not in the process arguments.
export MCP_GRAFANA_SERVER_TOKEN="$token"
export DO_NOT_TRACK=1
# The image keeps the server binary in /app, which is not in its PATH.
PATH="$PATH:/app"
export PATH

exec mcp-grafana "$@"
