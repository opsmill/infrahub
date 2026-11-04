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
| `INFRAHUB_GRAFANA_ADMIN_USER` | `admin` | The Grafana admin user. Read by the Grafana service (`GF_SECURITY_ADMIN_USER`) and by the service account step, so one setting changes both. |
| `INFRAHUB_GRAFANA_ADMIN_PASSWORD` | `admin` | Its password, read the same way. The docs say to change it when the server is turned on (spec FR-025). Grafana applies it only when its data volume is created; a password changed later in the Grafana UI must be set here too. |

## Services

| Service | Profile | Image | Port | Restart |
|---------|---------|-------|------|---------|
| `infrahub-grafana-mcp-init` | `grafana-mcp` | Image with `curl` (research R5) | None | None: runs once |
| `infrahub-grafana-mcp` | `grafana-mcp` | `grafana/mcp-grafana:2.0.2`, pinned by digest too | `127.0.0.1:8100:8000` | See below |

The port listens only on the host's loopback address (spec FR-006). To reach the server from another
computer, the operator uses an SSH tunnel (`ssh -L 8100:127.0.0.1:8100 <host>`) or a reverse proxy
with TLS, and adds the proxy's host name to `INFRAHUB_GRAFANA_MCP_ALLOWED_HOSTS`.

The image digest is written next to the tag in the Compose file. The entrypoint check stays valid
when a later `mcp-grafana` release refuses to start without a token on its own.

`infrahub-grafana-mcp` waits for `infrahub-grafana-mcp-init` with
`condition: service_completed_successfully`.

The server runs with:

- `--transport streamable-http --address 0.0.0.0:8000`
- `--allowed-hosts ${INFRAHUB_GRAFANA_MCP_ALLOWED_HOSTS}`
- `--usage-stats=disabled`, and `DO_NOT_TRACK=1`
- `--disable-write --disable-api` in 1.13 (FR-010, research R4). The release of story 4 adds
  `--enable-write-tools=<dashboard, folder and annotation tools>`.
- `GRAFANA_URL=http://infrahub-grafana:3000`
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
| Grafana not reachable after 5 minutes | `infrahub-grafana-mcp-init` log, exit code 1 | `Grafana did not answer at <url> within 5 minutes` |
| Admin login refused | `infrahub-grafana-mcp-init` log, exit code 1 | `Grafana refused the admin login: set INFRAHUB_GRAFANA_ADMIN_USER and INFRAHUB_GRAFANA_ADMIN_PASSWORD` |

The messages never contain a token value.

## What the AI assistant configures

| Field | Value |
|-------|-------|
| Transport | Streamable HTTP |
| URL | `http://localhost:8100/mcp` |
| Header | `Authorization: Bearer <INFRAHUB_GRAFANA_MCP_TOKEN>` |
