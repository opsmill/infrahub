# Quickstart: Validate the Grafana MCP server, the skill and the log fixes

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

Run these checks on a branch where the work is done. Each check names the requirement or success
criterion it proves. Settings and messages are in [contracts/compose-settings.md](contracts/compose-settings.md)
and [contracts/helm-values.md](contracts/helm-values.md).

## Prerequisites

- Docker with Compose 2.20 or later (profiles and `service_completed_successfully`).
- Claude Code, or another AI assistant that speaks MCP over Streamable HTTP.
- For the Helm checks: a kind cluster and Helm 3.
- An Infrahub 1.13 instance with the observability stack, from this branch.

## 1. Off by default (FR-001, SC-002)

Start the stack without the profile:

```bash
docker compose -f development/docker-compose-observability-standalone.yml up -d
```

Expected: `docker compose ps -a` lists no `infrahub-grafana-mcp` or `infrahub-grafana-mcp-init`, and
nothing listens on port 8100.

## 2. No token: the server does not start (FR-004, SC-002)

```bash
COMPOSE_PROFILES=grafana-mcp docker compose -f development/docker-compose-observability-standalone.yml up -d
```

Expected: `infrahub-grafana-mcp` exits with code 1, its log names `INFRAHUB_GRAFANA_MCP_TOKEN`, and it
is not restarted.

## 3. Connect Claude Code (FR-005, FR-006, SC-001)

Set `INFRAHUB_GRAFANA_MCP_TOKEN` and start again with the profile. Then:

```bash
claude mcp add --transport http grafana http://localhost:8100/mcp --header "Authorization: Bearer <token>"
```

Expected:

- `infrahub-grafana-mcp-init` exits with code 0; a second start does not create a second token.
- In Claude Code, the assistant lists the data sources `Prometheus (Local)`, `Tempo (Local)` and
  `Loki (Local)`.
- A request with a wrong token or without the header gets HTTP 401.
- From another computer on the same network, `http://<host>:8100/mcp` does not answer: the port
  listens only on `127.0.0.1` (FR-006). Through `ssh -L 8100:127.0.0.1:8100 <host>`, it answers.
- Repeat the connection with one other MCP client that speaks Streamable HTTP, and record which
  clients work in the docs (research R3, `--allowed-origins`).

## 3a. Open to the network, with TLS (FR-006, FR-006a)

Create a certificate for the host name of the Docker host, and make the computer of the AI assistant
trust it. Set `INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS=0.0.0.0`, the two TLS settings, and add
`<host name>:8100` to `INFRAHUB_GRAFANA_MCP_ALLOWED_HOSTS`. Start again with the profile.

Expected:

- From another computer, `https://<host name>:8100/mcp` answers, and Claude Code connects with that
  URL and the token.
- `http://<host name>:8100/mcp` does not answer with MCP data.
- With only `INFRAHUB_GRAFANA_MCP_TLS_CERT_FILE` set, `infrahub-grafana-mcp` exits with code 1 and its
  log names both TLS settings.
- Record in the docs how Claude Code handles a self-signed certificate (research R3, not verified).

## 4. No usage statistics (FR-008, SC-005)

While the assistant runs a query, watch the connections of the container (for example with
`docker exec infrahub-grafana-mcp cat /proc/net/tcp` or a packet capture on the Docker network).

Expected: connections only to `infrahub-grafana`.

## 5. Another host name (FR-007)

Publish the server on another port, for example `9100:8000`, without changing the allowed hosts.

Expected: the assistant cannot connect. After setting `INFRAHUB_GRAFANA_MCP_ALLOWED_HOSTS` to
`localhost:9100`, it connects.

## 6. Helm (FR-001 to FR-009 in Kubernetes)

- `helm install` with `grafanaMcp.enabled=true` and no token: fails with the message in the contract.
- With a token: the Job completes, the Secret with the Grafana token exists, and after
  `kubectl port-forward svc/<release>-grafana-mcp 8100:8000`, check 3 passes.
- `helm upgrade` with no change: the Job keeps the existing token.

## 7. Diagnosis (FR-013 to FR-016, SC-003)

Install the skill from the `infrahub-skills` branch. Make one query slow, for example with a generator
that sends many queries, and ask "Why is Infrahub slow?".

Expected: the report follows [contracts/diagnosis-report.md](contracts/diagnosis-report.md), names the
slow query and its component, and each finding has its evidence. Then remove the Tempo data source in
Grafana and ask again: the report says that Tempo is missing and which checks did not run.

On a 1.12 instance: the report says that the version is not supported (FR-021).

## 8. Missing panel (FR-017a, FR-010, SC-006)

Ask for a view that the shipped dashboards do not have, for example "the connection wait per worker".

Expected:

- The report describes the query, the panel type and the data source.
- Grafana has no new or changed dashboard, folder or annotation.
- Asked directly to create a dashboard, the assistant cannot: the server has no write tool.

The check of FR-017 and FR-018 (build and contribute a dashboard) belongs to the later release of
story 4.

## 9. Personal data (FR-022 to FR-024, FR-022a, SC-004, SC-007)

- Log in with single sign-on, create a webhook whose URL has `?token=secret-value`, and trigger it with
  an unreachable URL as well.
- Through the assistant, query Tempo, every container's stream in Loki (`{container=~".+"}`), and the
  labels of the Infrahub metrics in Prometheus, for that time window.
- Read the log lines of `infrahub-grafana-mcp` itself for that window.

Expected:

- No response contains `secret-value`, the user name or the email address, apart from the streams that
  the docs name (FR-022a).
- The Grafana MCP server's own lines contain neither the caller token nor the Grafana token.
- Each row of `log-audit.md` marked "confirmed" has a fix and a passing test, or a `drop` rule, or a
  docs entry.

## 10. Automated checks

```bash
uv run pytest backend/tests/unit/test_observability_compose.py
```

```bash
cd development && python convert_compose_standalone.py && git diff --exit-code docker-compose-observability-standalone.yml
```

In `infrahub-skills`, run the evals of the new skill as `dev/guides/getting-started.md` there
describes.
