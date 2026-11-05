# Contract: Docker Compose settings of the Grafana MCP server

**Requirements**: FR-001 to FR-009, FR-025 | **Research**: R1 to R5

These are the settings that the operator sets in the shell or in the `.env` file next to the
observability Compose file. They apply to `development/docker-compose-observability.yml` and to the
standalone file generated from it.

## Settings

| Setting | Default | Effect |
|---------|---------|--------|
| `COMPOSE_PROFILES=grafana-mcp` (or `--profile grafana-mcp`) | Not set | Turns the Grafana MCP server on. Without it, the two services are not created. |
| `INFRAHUB_GRAFANA_MCP_TOKEN` | None | The token that AI assistants send as `Authorization: Bearer`. Required when the profile is on. |
| `INFRAHUB_GRAFANA_MCP_ALLOWED_HOSTS` | `localhost:8100,127.0.0.1:8100` | The `Host` values the server accepts. Change it when the server is published on another host name or port. |
| `INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS` | `127.0.0.1` | The host address that port 8100 listens on. `0.0.0.0` opens it on every interface. Compose also passes it into the container. When it is not a loopback address (`127.0.0.0/8` or `::1`), the two TLS settings are required, or the container does not start; also add the host name that users connect to to `INFRAHUB_GRAFANA_MCP_ALLOWED_HOSTS` (spec FR-006, FR-006a). |
| `INFRAHUB_GRAFANA_MCP_TLS_CERT_FILE` | Not set | Path on the Docker host of the certificate (PEM), with its chain. Set with the key file, or neither. When both are set, the server serves HTTPS (spec FR-006a). |
| `INFRAHUB_GRAFANA_MCP_TLS_KEY_FILE` | Not set | Path on the Docker host of the private key (PEM) of that certificate. |
| `INFRAHUB_GRAFANA_ADMIN_USER` | `admin` | The Grafana admin user. Read by the Grafana service (`GF_SECURITY_ADMIN_USER`) and by the service account step, so one setting changes both. |
| `INFRAHUB_GRAFANA_ADMIN_PASSWORD` | `admin` | Its password, read the same way. The docs say to change it when the server is turned on (spec FR-025). Grafana applies it only when its data volume is created; a password changed later in the Grafana UI must be set here too. |

## Services

| Service | Profile | Image | Port | Restart |
|---------|---------|-------|------|---------|
| `infrahub-grafana-mcp-init` | `grafana-mcp` | Image with `curl` (research R5) | None | None: runs once |
| `infrahub-grafana-mcp` | `grafana-mcp` | `grafana/mcp-grafana:2.0.2`, pinned by digest too | `${INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS:-127.0.0.1}:8100:8000` | See below |

By default, the port listens only on the host's loopback address (spec FR-006). To reach the server
from another computer, the operator does one of these:

- sets `INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS`, turns on TLS with the two certificate settings, and adds
  the host name to `INFRAHUB_GRAFANA_MCP_ALLOWED_HOSTS`, for example `infrahub.example.com:8100`;
- uses an SSH tunnel (`ssh -L 8100:127.0.0.1:8100 <host>`);
- uses a reverse proxy with TLS, and adds the proxy's host name to
  `INFRAHUB_GRAFANA_MCP_ALLOWED_HOSTS`.

**TLS files.** When both TLS settings are set, Compose mounts the two files read-only at
`/etc/grafana-mcp/tls/tls.crt` and `/etc/grafana-mcp/tls/tls.key`, and the entrypoint adds
`--server.tls-cert-file` and `--server.tls-key-file` with these paths. A Compose bind mount needs a
source path even when the setting is empty; how to mount the files only when they are set is checked
in the Compose phase, with the restart policy.

The image digest is written next to the tag in the Compose file. The entrypoint check stays valid
when a later `mcp-grafana` release refuses to start without a token on its own.

`infrahub-grafana-mcp` waits for `infrahub-grafana-mcp-init` with
`condition: service_completed_successfully`.

The server runs with:

- `--transport streamable-http --address 0.0.0.0:8000`
- `--allowed-hosts ${INFRAHUB_GRAFANA_MCP_ALLOWED_HOSTS}`
- `--usage-stats=disabled`, and `DO_NOT_TRACK=1`
- `--server.tls-cert-file /etc/grafana-mcp/tls/tls.crt --server.tls-key-file
  /etc/grafana-mcp/tls/tls.key`, only when both TLS settings are set (spec FR-006a)
- `--disable-write --disable-api` in 1.13 (FR-010, research R4). The release of story 4 adds
  `--enable-write-tools=<dashboard, folder and annotation tools>`.
- `GRAFANA_URL=http://infrahub-grafana:3000`
- `INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS=${INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS:-127.0.0.1}`, read only
  by the entrypoint check (spec FR-006a)
- `GRAFANA_SERVICE_ACCOUNT_TOKEN_FILE` pointing to the token file in the volume `grafana_mcp_token`,
  mounted read-only

**Restart policy.** When the token is missing, the entrypoint exits with code 1. With
`unless-stopped`, Docker would restart the container in a loop, and the spec requires that it does not
start (FR-004). Without a `restart` key, the server does not come back after the Docker host restarts.
The choice between no `restart` key and `on-failure:1` is the first task of the Compose phase: check
both on a running stack, after a missing token and after a restart of Docker, and record the result
here before the service is written. The unit test checks the chosen value.

## Messages

| Case | Where | Text |
|------|-------|------|
| Profile on, no token | `infrahub-grafana-mcp` log, exit code 1 | `INFRAHUB_GRAFANA_MCP_TOKEN is not set: set it to the token that AI assistants send` |
| Only one TLS setting is set | `infrahub-grafana-mcp` log, exit code 1 | `Set both INFRAHUB_GRAFANA_MCP_TLS_CERT_FILE and INFRAHUB_GRAFANA_MCP_TLS_KEY_FILE, or neither` |
| Listen address is not a loopback address, and TLS is not set | `infrahub-grafana-mcp` log, exit code 1 | `INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS is <address>, which is open to a network: set INFRAHUB_GRAFANA_MCP_TLS_CERT_FILE and INFRAHUB_GRAFANA_MCP_TLS_KEY_FILE` |
| Grafana not reachable after 5 minutes | `infrahub-grafana-mcp-init` log, exit code 1 | `Grafana did not answer at <url> within 5 minutes` |
| Admin login refused | `infrahub-grafana-mcp-init` log, exit code 1 | `Grafana refused the admin login: set INFRAHUB_GRAFANA_ADMIN_USER and INFRAHUB_GRAFANA_ADMIN_PASSWORD` |

The messages never contain a token value.

## What the AI assistant configures

| Field | Value |
|-------|-------|
| Transport | Streamable HTTP |
| URL | `http://localhost:8100/mcp` |
| Header | `Authorization: Bearer <INFRAHUB_GRAFANA_MCP_TOKEN>` |
