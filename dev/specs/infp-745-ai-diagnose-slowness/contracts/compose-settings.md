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
| `INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS` | `127.0.0.1` | The host address that port 8100 listens on. `0.0.0.0` opens it on every interface. Compose also passes it into the container. When it is not a loopback address (`127.0.0.0/8`, `::1` or `[::1]`; Compose needs the brackets in a port mapping), the two TLS settings are required, or the container does not start; also add the host name that users connect to to `INFRAHUB_GRAFANA_MCP_ALLOWED_HOSTS` (spec FR-006, FR-006a). |
| `INFRAHUB_GRAFANA_MCP_TLS_CERT_FILE` | Not set | Path on the Docker host of the certificate (PEM), with its chain. Set with the key file, or neither. When both are set, the server serves HTTPS (spec FR-006a). |
| `INFRAHUB_GRAFANA_MCP_TLS_KEY_FILE` | Not set | Path on the Docker host of the private key (PEM) of that certificate. |
| `INFRAHUB_GRAFANA_ADMIN_USER` | `admin` | The Grafana admin user. Read by the Grafana service (`GF_SECURITY_ADMIN_USER`) and by the service account step, so one setting changes both. |
| `INFRAHUB_GRAFANA_ADMIN_PASSWORD` | `admin` | Its password, read the same way. The docs say to change it when the server is turned on (spec FR-025). Grafana applies it only when its data volume is created; a password changed later in the Grafana UI must be set here too. |

## Services

| Service | Profile | Image | User | Port | Restart |
|---------|---------|-------|------|------|---------|
| `infrahub-grafana-mcp-init` | `grafana-mcp` | `grafana/grafana:11.4.0`, the image of the `infrahub-grafana` service: no new image. Tag only, as the Grafana service; a unit test checks that the two are equal. It has `curl`, `sed` and `grep`, and no `jq` | `root`, because a new volume belongs to root | None | None: runs once |
| `infrahub-grafana-mcp` | `grafana-mcp` | `grafana/mcp-grafana:2.0.2@sha256:78d208116ec52b09b44f0eca66892073b39aefcb64483c54d43255c8eab7e97a` | `1000:999`, the user of the image | `${INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS:-127.0.0.1}:8100:8000` | None (see below) |

By default, the port listens only on the host's loopback address (spec FR-006). To reach the server
from another computer, the operator does one of these:

- sets `INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS`, turns on TLS with the two certificate settings, and adds
  the host name to `INFRAHUB_GRAFANA_MCP_ALLOWED_HOSTS`, for example `infrahub.example.com:8100`;
- uses an SSH tunnel (`ssh -L 8100:127.0.0.1:8100 <host>`);
- uses a reverse proxy with TLS, and adds the proxy's host name to
  `INFRAHUB_GRAFANA_MCP_ALLOWED_HOSTS`.

**TLS files.** Compose always mounts two files read-only, with these bind mounts:

- source `${INFRAHUB_GRAFANA_MCP_TLS_CERT_FILE:-/dev/null}`, target `/etc/grafana-mcp/tls/tls.crt`;
- source `${INFRAHUB_GRAFANA_MCP_TLS_KEY_FILE:-/dev/null}`, target `/etc/grafana-mcp/tls/tls.key`.

A Compose bind mount needs a source path even when the setting is empty, so the default source is
`/dev/null`. The entrypoint turns TLS on from the two settings, not from the files: when both are
set, it adds `--server.tls-cert-file` and `--server.tls-key-file` with the two target paths. The
server runs as user 1000, so the key file on the Docker host must be readable by that user.

The image digest of the server is written next to the tag in the Compose file. The entrypoint check stays valid
when a later `mcp-grafana` release refuses to start without a token on its own.

`infrahub-grafana-mcp` waits for `infrahub-grafana-mcp-init` with
`condition: service_completed_successfully`. `infrahub-grafana-mcp-init` depends on
`infrahub-grafana` with `required: false`, because in the development stack the Grafana service is
in the `debug` profile.

The init service writes the token file with mode `0400` and gives it to `1000:999`, the user of the
server, with the script setting `GRAFANA_MCP_TOKEN_FILE_OWNER`.

The server runs with:

- `--transport streamable-http --address 0.0.0.0:8000`
- `--allowed-hosts ${INFRAHUB_GRAFANA_MCP_ALLOWED_HOSTS}`
- `--usage-stats=disabled`, and `DO_NOT_TRACK=1`
- `--server.tls-cert-file /etc/grafana-mcp/tls/tls.crt --server.tls-key-file
  /etc/grafana-mcp/tls/tls.key`, only when both TLS settings are set (spec FR-006a)
- `--disable-write --disable-api` in 1.13 (FR-010, research R4). The release of story 4 adds
  `--enable-write-tools=<dashboard, folder and annotation tools>`.
- `--disable-docs --disable-plugin`, in 1.13 and in the later release, because the documentation and
  plugin tools call grafana.com (FR-008). With these options and the two above, the server has 57
  tools, none open-world, all read-only (checked on 2026-11-19).
- `--instructions-append "In this stack the Grafana MCP server only reads: it has no tool that
  creates or changes dashboards, folders, annotations, incidents, alert rules or data sources."`
- `GRAFANA_URL=http://infrahub-grafana:3000`
- `INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS=${INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS:-127.0.0.1}`, read only
  by the entrypoint check (spec FR-006a)
- `GRAFANA_SERVICE_ACCOUNT_TOKEN_FILE` pointing to the token file in the volume `grafana_mcp_token`,
  mounted read-only
- `INFRAHUB_GRAFANA_MCP_TOKEN`, which Compose passes into the container. The entrypoint exports it as
  `MCP_GRAFANA_SERVER_TOKEN`, so the value is not in the process arguments.

The image keeps the server binary at `/app/mcp-grafana`, which is not in its `PATH`. The entrypoint
adds `/app` to `PATH`.

**Restart policy.** Decided: no `restart` key. When the token is missing, the entrypoint exits with
code 1. With `unless-stopped`, Docker would restart the container in a loop, and the spec requires
that it does not start (FR-004). With `on-failure:1` and no token, Docker started the container a
second time and the error was logged twice. Without a `restart` key, the server does not come back
after the Docker host restarts; no other service of the observability file has a `restart` key
either. A restart of the Docker daemon was not tested. The unit test checks that the key is absent.

**Upgrade.** After the embedded entrypoint changed in the standalone file, `docker compose up -d`
did not recreate the container once, and `--force-recreate` was needed. Seen once, not investigated.

## Messages

| Case | Where | Text |
|------|-------|------|
| Profile on, no token | `infrahub-grafana-mcp` log, exit code 1 | `INFRAHUB_GRAFANA_MCP_TOKEN is not set: set it to the token that AI assistants send` |
| Only one TLS setting is set | `infrahub-grafana-mcp` log, exit code 1 | `Set both INFRAHUB_GRAFANA_MCP_TLS_CERT_FILE and INFRAHUB_GRAFANA_MCP_TLS_KEY_FILE, or neither` |
| Listen address is not a loopback address, and TLS is not set | `infrahub-grafana-mcp` log, exit code 1 | `INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS is <address>, which is open to a network: set INFRAHUB_GRAFANA_MCP_TLS_CERT_FILE and INFRAHUB_GRAFANA_MCP_TLS_KEY_FILE` |
| Grafana not reachable after 5 minutes | `infrahub-grafana-mcp-init` log, exit code 1 | `Grafana did not answer at <url> within 5 minutes`. When `GRAFANA_WAIT_SECONDS` is not 300: `within <n> seconds` |
| Admin login refused | `infrahub-grafana-mcp-init` log, exit code 1 | `Grafana refused the admin login: set INFRAHUB_GRAFANA_ADMIN_USER and INFRAHUB_GRAFANA_ADMIN_PASSWORD` |
| Any other failed call to Grafana | `infrahub-grafana-mcp-init` log, exit code 1 | `Grafana answered HTTP <status> when asked to <action>` |

The messages never contain a token value.

## What the AI assistant configures

| Field | Value |
|-------|-------|
| Transport | Streamable HTTP |
| URL | `http://localhost:8100/mcp` |
| Header | `Authorization: Bearer <INFRAHUB_GRAFANA_MCP_TOKEN>` |
