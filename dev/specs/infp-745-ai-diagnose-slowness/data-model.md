# Data Model: Find the Slow Component of an Infrahub Instance with an AI Assistant

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

The feature adds no data to the Infrahub database. The entities below are deployment objects, files
and the content of the skill's report.

## Grafana MCP server

The container or pod that gives an AI assistant tools to read and write in the stack's Grafana.

| Field | Value | Rule |
|-------|-------|------|
| Enabled | Off by default | Compose: profile `grafana-mcp`. Helm: `grafanaMcp.enabled`. Off means no container (FR-001). |
| Published address | Compose: `127.0.0.1:8100` to container port 8000. Helm: a `ClusterIP` Service on port 8000. | Not reachable from another computer by default (FR-006). |
| Listen address | Compose: `INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS`, default `127.0.0.1`. Helm: `service.type`, default `ClusterIP`. | One setting opens the port to a network (FR-006). |
| TLS | Off by default | On when a certificate and its key are given; both or neither (FR-006a). |
| Allowed hosts | Default `localhost:8100,127.0.0.1:8100` | One setting changes it (FR-007). |
| Caller token | No default | Required when enabled; without it the container does not start (FR-003, FR-004). |
| Usage statistics | Disabled | Always (FR-008). |
| Write tools | None in 1.13 | No tool that calls any Grafana API route. From the release of story 4: dashboards, folders and annotations only (FR-010). |
| Grafana token | Read from a file | Written by the service account step. |

**States.**

```text
off ── operator turns it on ──► waiting for the service account step
waiting ── step succeeds ──► running
waiting ── step fails ──► stopped, error logged by the step
running ── no caller token ──► stopped, error names INFRAHUB_GRAFANA_MCP_TOKEN (Compose) or the Helm value
```

## Caller token

The value that each AI assistant sends as `Authorization: Bearer <token>`.

- Set by the operator: Compose variable `INFRAHUB_GRAFANA_MCP_TOKEN`; Helm value
  `grafanaMcp.serverToken.value` or an existing Secret.
- Shared with the users who diagnose the instance.
- Changing it needs a restart of the container.

## Grafana service account and its token

| Field | Value |
|-------|-------|
| Name | `infrahub-grafana-mcp` |
| Role | Viewer in 1.13; Editor from the release of story 4 (FR-010). The step changes the role of an existing account when it differs. |
| Token name | `infrahub-grafana-mcp` |
| Where the token is stored | Compose: file `token` in the volume `grafana_mcp_token`. Helm: key `token` of the Secret `<release>-grafana-mcp-grafana-token`. |

**Rules.**

- Created at start (Compose) or at install and upgrade (Helm), never by the operator (FR-009).
- When the stored token still works, nothing changes.
- When it does not work or is missing, the step deletes the token with that name and creates a new
  one. Grafana returns a token only once, so a lost token is always replaced.

## Diagnosis report

The output of one run of the skill. The format is in
[contracts/diagnosis-report.md](contracts/diagnosis-report.md).

| Field | Rule |
|-------|------|
| Infrahub version | From `infrahub_info{version}`. A version before 1.13 ends the run (FR-021). |
| Data sources | The Prometheus, Tempo and Loki data sources found, and each one that is missing with the checks it stops (FR-013). |
| Time window | The window that the skill read. |
| Slow component | Neo4j, the API server, the task workers, the code of a generator, or "not found". |
| Findings | Each with its evidence: a metric query, a trace ID or a log line (FR-015). |
| Not checked | Each check that did not run, with the reason (for example no trace, logs older than 24 hours). |
| Missing panels | In 1.13: each query and panel that would answer a question the dashboards do not answer (FR-017a). From the release of story 4: each dashboard built or changed, and whether the user chose to contribute it. |

## Log audit result

Recorded in `log-audit.md` (FR-022).

| Field | Rule |
|-------|------|
| Location | For Infrahub's code: file and function or symbol, no line number. For another stream: the container (Compose) or pod (Helm), or the metric or trace attribute. |
| Value written | Token, password, email address, user name, client IP address or URL query string. |
| Level and default | The log level, and whether the line is written with the default settings. |
| Destination | Loki, the Prefect server, or both. |
| Status | Confirmed, possible (with the runtime check), or clean. |
| Fix | What the change does, and the pull request that makes it (FR-023). For a stream that Infrahub does not write: the Alloy `drop` rule, or the docs entry (FR-022a). Or the decision that keeps the line, with its docs entry (FR-023). |
