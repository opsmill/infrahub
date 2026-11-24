# Research: Find the Slow Component of an Infrahub Instance with an AI Assistant

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Date**: 2026-11-04

Sources read for this research:

- This repository at branch `dp-20261104-ai-diagnose-slowness-infp-745` (based on `develop` at
  `a5b817f231`).
- [grafana/mcp-grafana](https://github.com/grafana/mcp-grafana) at tag `v2.0.2` (released 2026-10-07):
  [`cmd/mcp-grafana/main.go`](https://github.com/grafana/mcp-grafana/blob/v2.0.2/cmd/mcp-grafana/main.go),
  [`mcpgrafana.go`](https://github.com/grafana/mcp-grafana/blob/v2.0.2/mcpgrafana.go),
  [README](https://github.com/grafana/mcp-grafana/blob/v2.0.2/README.md).
- [opsmill/infrahub-helm](https://github.com/opsmill/infrahub-helm) at commit `2975865` (2026-11-03).
- [opsmill/infrahub-skills](https://github.com/opsmill/infrahub-skills) at commit `8b578cb`
  (2026-11-02).
- [Grafana 11.4 service account API](https://github.com/grafana/grafana/blob/v11.4.0/docs/sources/developers/http_api/serviceaccount.md).
- [grafana/skills](https://github.com/grafana/skills) (read on 2026-11-04).

Nothing was run for this research. Items marked "not verified" need a check on a running stack; each
one is a task in `tasks.md`.

## R1. How the Compose stack keeps the Grafana MCP server off by default

**Facts.**

- The observability services are in `development/docker-compose-observability.yml`. Each service has
  `profiles: [debug]`, except the two Tempo services, which have `profiles: [trace]`.
  `tasks/shared.py::get_compose_cmd` adds these profiles for the development stack.
- The file that operators download, `development/docker-compose-observability-standalone.yml`, is
  written by `development/convert_compose_standalone.py::convert`. The script removes every `profiles`
  key, so every service in the standalone file starts.
- The service behind `https://infrahub.opsmill.io/?observability=true` is not in this repository. Not
  known: whether it serves the standalone file as it is, or changes it.
- Compose reads the active profiles from the `COMPOSE_PROFILES` variable, in the shell or in the
  `.env` file next to the Compose file.

**Decision.** Put the two new services (R4, R5) in a Compose profile named `grafana-mcp`, and change
the converter so that it keeps the `profiles` key of the services in that profile. The operator turns
the server on with one setting: `COMPOSE_PROFILES=grafana-mcp`, or `--profile grafana-mcp` on the
command line.

**Rationale.** A profile is the only Compose mechanism that keeps a service from being created. A
container that starts and exits when a variable is false still appears in `docker compose ps`, and
FR-001 requires that no container runs.

**Alternatives considered.**

- An environment variable read by the entrypoint, with the container exiting when it is false: a
  container is still created, against FR-001.
- A separate Compose file that the operator adds with `-f`: two files to download and keep in step,
  where the card asks for one setting.

**Open item.** Ask the owner of `infrahub.opsmill.io` whether the service changes the standalone file,
and whether it keeps the `profiles` key (task in `tasks.md`).

## R2. How the container refuses to start without a token

**Facts.**

- `mcp-grafana` reads the token that callers send from `--server-auth-token` or from the
  `MCP_GRAFANA_SERVER_TOKEN` variable. A request without it, or with a wrong value, gets HTTP 401.
- When no token is set and the address is not a loopback address, `mcp-grafana` 2.0.2 logs a
  `SECURITY:` warning and **starts without authentication** (`checkCallerAuthPolicy`). The release notes
  say this becomes a start error in a later release.
- Compose interpolation with `${VAR:?message}` fails `docker compose up` for the whole file, also when
  the profile is off, so it would break every stack that does not use the server.
- The image `grafana/mcp-grafana:2.0.2` is based on Debian bookworm-slim and has `/bin/sh`.

**Decision.**

- Compose: the service overrides the entrypoint with a short `/bin/sh` check. When
  `INFRAHUB_GRAFANA_MCP_TOKEN` is empty, the check writes
  `INFRAHUB_GRAFANA_MCP_TOKEN is not set: set it to the token that AI assistants send` to standard
  error and exits with code 1. The service has no `restart` key, so it stays stopped.
- Helm: the template uses `required` on the token value, unless an existing Secret is named. The
  install or upgrade fails with a message that names the value.

**Rationale.** FR-004 requires that the container does not start. The upstream default starts the
server open, so the check must be ours.

**Alternatives considered.** Waiting for the upstream start error: not released, and the release is not
known.

## R3. The `mcp-grafana` options that the stack sets

| Need | Option in 2.0.2 | Value in the stack |
|------|-----------------|--------------------|
| Streamable HTTP transport (D10) | `--transport streamable-http` | Set. The image entrypoint uses `--transport sse`, so the stack passes the full command. |
| Listen address | `--address` | `0.0.0.0:8000` |
| Caller token (FR-005) | `MCP_GRAFANA_SERVER_TOKEN` | From `INFRAHUB_GRAFANA_MCP_TOKEN` |
| Allowed hosts (FR-007) | `--allowed-hosts` (comma-separated). No environment variable exists. | From `INFRAHUB_GRAFANA_MCP_ALLOWED_HOSTS`, default `localhost:8100,127.0.0.1:8100` |
| No usage statistics (FR-008) | `--usage-stats=disabled`; also `DO_NOT_TRACK=1` | Both set. The upstream default is `enabled`. |
| Grafana address | `GRAFANA_URL` | `http://infrahub-grafana:3000` |
| Grafana token | `GRAFANA_SERVICE_ACCOUNT_TOKEN_FILE`, read again on every call | The file written by the init container (R5) |
| HTTPS for the users (FR-006a) | `--server.tls-cert-file` and `--server.tls-key-file`, both or neither. With one only, the server refuses to start: "incomplete TLS configuration". With both, `effectiveTLSEnabled` turns TLS on for `streamable-http` and `sse`, and the server uses Go's `ListenAndServeTLS`. Only command-line flags were found; no environment variable form. | Passed by the entrypoint when `INFRAHUB_GRAFANA_MCP_TLS_CERT_FILE` and `INFRAHUB_GRAFANA_MCP_TLS_KEY_FILE` are set. Not set by default. |
| Health check | `/healthz`, outside the token check | Used by the Helm probes, on the side listener `--healthz-address :8081`, because a probe sends the pod IP as `Host`. Checked in the vcluster e2e test without TLS, and by hand with a TLS Secret: the side listener serves plain HTTP also when the main port serves HTTPS ([infrahub-helm #131](https://github.com/opsmill/infrahub-helm/pull/131)). |
| No tools that call grafana.com (FR-008) | `--disable-docs --disable-plugin`. Without them, `search_docs`, `get_doc` and `search_plugin_information` are marked `openWorldHint: true`, and `search_docs` returned live results from grafana.com (running server, 2026-11-19). | Both set (R4) |
| Instructions sent to the clients | `--instructions-append` | `In this stack the Grafana MCP server only reads: it has no tool that creates or changes dashboards, folders, annotations, incidents, alert rules or data sources.` The server's own text says that it can create dashboards and incidents. |
| User of the container | The image runs as `1000:999` | Compose sets `user: "1000:999"`, because the init service gives the token file to that user. Helm sets `runAsUser: 1000`, `runAsGroup: 999` and `fsGroup: 999`. |

The design document named the variable `GRAFANA_MCP_ALLOWED_HOSTS`. That name does not exist in
`mcp-grafana`, so the stack defines its own variable, `INFRAHUB_GRAFANA_MCP_ALLOWED_HOSTS`, and passes
it to the flag.

`--allowed-origins` is empty by default, so the server rejects a request that carries an `Origin`
header. AI assistants that run on the user's computer, such as Claude Code, send no `Origin` header.
A web-based client would need it. Not verified with a client.

Host port 8100 is free in the root Compose file, the observability Compose file and the development
override.

**Which address the port listens on** (critique of 2026-11-04, E3). A Compose mapping `8100:8000`
listens on every network interface of the host. The allowed hosts check reads the `Host` header, which
the client sets, so it does not limit who connects. The server serves plain HTTP, so the token travels
unencrypted. Decision: publish `127.0.0.1:8100:8000` by default, which matches the default allowed
hosts. Access from another computer goes through an SSH tunnel or a reverse proxy with TLS that the
operator sets up. In Helm, the Service stays `ClusterIP`, and an Ingress needs TLS.

**Opening the port to a network, with TLS in the server** (clarification of 2026-11-04). The
loopback default stays. `INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS` (default `127.0.0.1`) sets the host
address of the published port, for example `0.0.0.0` for every interface. In Helm, `service.type`
can be `LoadBalancer` or `NodePort`. `mcp-grafana` 2.0.2 serves HTTPS itself when it gets a
certificate and a key (table above), so no proxy container and no other image are needed.

Do not confuse these flags with `--tls-cert-file`, `--tls-key-file`, `--tls-ca-file` and
`--tls-skip-verify`, without the `server.` prefix: those are for the connection from the server to
Grafana.

Source: `cmd/mcp-grafana/main.go` at tag `v2.0.2`. Read, not run.

Checked by hand in a vcluster with a self-signed certificate
([infrahub-helm #131](https://github.com/opsmill/infrahub-helm/pull/131)): the server serves HTTPS,
and `/healthz` on the side listener stays plain HTTP, so the Helm probes use the HTTP scheme.

Not verified:

- how Claude Code and other MCP clients handle a self-signed certificate;
- whether the server reads a renewed certificate without a restart. Go's `ListenAndServeTLS` reads
  the files once at start, so a restart is probably needed (spec Edge Cases).

The certificate stays the operator's job.

Alternatives considered:

- A reverse proxy container in the stack (for example Caddy or nginx). Not chosen: it adds an image
  to pin and review, and the server serves TLS itself.
- Allowing plain HTTP on a network address, with only a warning in the docs. Not chosen (decided by
  Daniel on 2026-11-05, critique E2). The first reason given here, that the entrypoint does not see
  the host address, was wrong: Compose can pass the same variable into the container.

**Refusing a network address without TLS** (clarification of 2026-11-05). Compose passes
`INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS` into the environment of `infrahub-grafana-mcp`, with the same
default `127.0.0.1` as the port mapping, so both read one value. The entrypoint exits with code 1
when the address is not in `127.0.0.0/8` and is not `::1` or `[::1]` (Compose needs the brackets in a
port mapping), and the two TLS settings are not set.
Consequence: an operator whose reverse proxy runs on another host cannot reach the server over plain
HTTP; that proxy must connect with HTTPS, or the proxy must run on the Docker host. In Helm, the chart
applies the same rule with `fail` to a `LoadBalancer` or `NodePort` Service (critique E3).

## R4. Which write tools the server keeps

**Facts.** With write tools on, `mcp-grafana` 2.0.2 can:

- change dashboards and folders, and create, change and delete annotations;
- create and delete snapshots;
- write alert rules, silences and contact points;
- create and change data sources (`tools/datasources.go`) and install plugins (`tools/plugins.go`);
- call any Grafana API route with any method (`grafana_api_request`, `tools/api.go`), limited only by
  the role of the Grafana service account.

Options that limit them: `--disable-write`, `--enable-write-tools=<tool,...>` (keeps the named write
tools when `--disable-write` is set), one `--disable-<category>` flag per category (for example
`--disable-api`, `--disable-plugin`), and `--enabled-tools`.

In Grafana, a service account with the Editor role can change dashboards, folders, annotations, alert
rules and silences, but cannot create data sources or install plugins, which need the Admin role.

**Decision** (Daniel, 2026-11-04; spec FR-010), in two steps:

- **1.13:** no write tools. `--disable-write --disable-api --disable-docs --disable-plugin`, and the
  Grafana service account has the Viewer role. Story 4 (building dashboards) is moved to a later
  release. With these options, the server has 57 tools, none open-world, all read-only (checked on a
  running server on 2026-11-19).
- **Later release of story 4:** keep only the write tools that the skill uses:
  `--disable-write --enable-write-tools=<dashboard, folder and annotation tools> --disable-api
  --disable-docs --disable-plugin`, and the Editor role. `--disable-docs --disable-plugin` stay,
  because the documentation and plugin tools call grafana.com (R3, spec FR-008).

**Rationale.** D8 needs write tools only so that the skill can build and change dashboards and add
annotations. The diagnosis itself only reads. D10 turns on all write tools, and its "Costs us" item
names the change of data sources, alert rules and silences, and plugin installs as a risk for the
security review. In 1.13 the server only reads, so the security review, which is a release condition,
judges a smaller risk. The later release adds back only what D8 needs.

**Alternatives considered.**

- All write tools on, as D10 says: the skill does not use the others, and they widen what anyone with
  the token can do in Grafana.
- The dashboard, folder and annotation write tools already in 1.13: chosen first, then moved to the
  later release so that the 1.13 security review covers a server that only reads.

The exact tool names for annotations are read from `mcp-grafana` 2.0.2 when the Compose service is
written.

## R5. Creating the Grafana service account and its token at installation

**Facts.**

- Grafana 9 and later has a service account API. The calls are:
  - `GET /api/serviceaccounts/search?query=<name>`;
  - `POST /api/serviceaccounts` (`name`, `role`);
  - `POST /api/serviceaccounts/<id>/tokens` (`name`). It returns the token once; it cannot be read
    again;
  - `DELETE /api/serviceaccounts/<id>/tokens/<tokenId>`;
  - `PATCH /api/serviceaccounts/<id>` (`role`);
  - `GET /api/user` with the service account token, to check that the token still works.
- A duplicate name returns HTTP 400 (`ErrAlreadyExists`, `ErrTokenAlreadyExists`).
- Grafana is `grafana/grafana:11.4.0` in Compose and 11.1.5 in Helm (chart `grafana` 8.5.0). Both
  have the API. The calls were run on 11.1.5 and 11.4.0 (component test of
  [#11657](https://github.com/opsmill/infrahub/pull/11657)).
- The Compose Grafana reads its admin login from `INFRAHUB_GRAFANA_ADMIN_USER` and
  `INFRAHUB_GRAFANA_ADMIN_PASSWORD` (default `admin` for both), not from fixed values, and has no
  health check.
- The Compose stack already has a one-time container, `infrahub-tempo-init`, that another service
  waits for with `depends_on: condition: service_completed_successfully`.
- The Helm charts in `infrahub-helm` already use hook Jobs, for example
  `charts/infrahub/templates/infrahub-upgrade-job.yaml`. The observability chart has none.

**Decision.** One script, run once at each start or upgrade:

1. Wait until `GET /api/health` answers HTTP 200, for at most 5 minutes.
2. Find the service account `infrahub-grafana-mcp`, or create it with the Viewer role (Editor from the
   release of story 4; R4).
3. Give it the Viewer role if it has another one, also when its token still works.
4. Check the stored token with `GET /api/user`. HTTP 200 stops the script. HTTP 401 or 403 means that
   the token is replaced. Any other answer stops the script with an error, so that a temporary error
   never replaces a token that may still work.
5. Delete the tokens named `infrahub-grafana-mcp`, create a new one, and write it through a `.new`
   file and `mv`.

Consequence: the script logs in as the Grafana admin at every start, not only when the token is
replaced.

- Compose: a one-time service `infrahub-grafana-mcp-init` in the `grafana-mcp` profile. It writes the
  token to a named volume that the MCP service mounts read-only. The MCP service waits for it with
  `service_completed_successfully`.
- Helm: a `post-install,post-upgrade` hook Job with a ServiceAccount and a Role. The Role allows
  `create` on Secrets, because Kubernetes cannot limit `create` to one name, and `get` and `update`
  on the one token Secret. The MCP Deployment mounts the Secret as a file.

The script reads the Grafana admin user and password from variables, so that an operator who changed
the admin password sets it once (Compose: `INFRAHUB_GRAFANA_ADMIN_USER` and
`INFRAHUB_GRAFANA_ADMIN_PASSWORD`, default `admin`; Helm: the Grafana admin Secret).

**Rationale.** FR-009 requires that the operator sets only the token that AI assistants send. The
token file is read again on every call, so a new token after a restart needs no restart of the MCP
server.

**Alternatives considered.**

- The operator creates the service account by hand: two tokens to set, which the card names as the
  problem to remove.
- A Grafana provisioning file: Grafana cannot create a service account from one.

**Image of the init script** (decided during implementation). The script uses the Grafana image of
the stack, which has `curl`, `sed` and `grep`, and no `jq`; the script reads `id`, `role` and `key`
with `sed`. Compose uses `grafana/grafana:11.4.0`, the image of the `infrahub-grafana` service, so the
stack pulls no new image; a unit test checks that the two tags are equal. Helm uses
`grafana/grafana:11.1.5` for the hook Job. The `mcp-grafana` image has no `curl`.

## R6. Where the skill lives and how it is tested

**Facts** (from `opsmill/infrahub-skills` at `8b578cb`):

- Each skill is a directory `skills/infrahub-<verb>-<noun>/` with `SKILL.md`, `examples.md`,
  `reference.md` and `rules/` (one file per rule, plus `_sections.md` and `_template.md`).
- `SKILL.md` has YAML front matter with `name`, a `description` that contains `TRIGGER when:` and
  `DO NOT TRIGGER when:`, and `metadata.version` and `author`. `tests/test_skill_frontmatter.py`
  checks the trigger clauses.
- "Rule = Test" ([`dev/guidelines/rule-equals-test.md`](https://github.com/opsmill/infrahub-skills/blob/main/dev/guidelines/rule-equals-test.md)):
  each rule needs, in the same change, a check in `graders/<skill>/lib.py`, a task in `eval.yaml`, a
  grader run against four fixtures (compliant, compliant but written differently, violating, a
  violating near-miss), and the regenerated `evaluations/*.json`.
- Evals run with `skillgrade`. `skill-evals.yml` runs them on release pull requests (not blocking) and
  every Monday. It needs `ANTHROPIC_API_KEY`.
- Users install the skills with `npx skills add opsmill/infrahub-skills`, or as the Claude Code plugin
  `infrahub@opsmill`. Neither installs an MCP server.
- `infrahub-analyzing-diagnostics` has a CRITICAL rule, `report-evidence-per-finding`: each finding
  cites its evidence. Neither diagnostics skill mentions Grafana.
- The repository has no CODEOWNERS file. Not verified from the repository: which team owns it.

**Decision.** The skill follows this layout. Its rules, each with its grader and four fixtures:

| Rule | What it checks | Requirement |
|------|----------------|-------------|
| `check-version-first` | Reads `infrahub_info{version}` and stops on a version before 1.13 | FR-021 |
| `check-datasources-first` | Lists the Prometheus, Tempo and Loki data sources by type, not by UID, and names a missing one | FR-013 |
| `follow-check-order` | Durations, then component, then trace, then logs | FR-014 |
| `report-evidence-per-finding` | Each finding has a metric query, a trace ID or a log line | FR-015 |
| `describe-missing-panel` | When the dashboards do not answer, describes the query, panel and data source, and changes nothing in Grafana | FR-017a |
| `no-generic-query-help` | Sends PromQL and TraceQL questions to `grafana/skills` | FR-012 |

The release of story 4 adds a rule `ask-before-contributing` (sends nothing to GitHub without the
user's yes, FR-018).

The fixtures are recorded `mcp-grafana` responses from a local stack with a known slow query (design
document, test for D8).

**Rationale.** It is the repository's own format and test rule.

**Alternatives considered.** The private `opsmill/opsmill-skills` repository: rejected in D8, because
the operator is the main user.

## R7. What the skill reads

| Question | Data | Source in this repository |
|----------|------|---------------------------|
| Which Infrahub version | `infrahub_info{version}` | `backend/infrahub/worker.py::INFO_METRIC` |
| Are API requests slow | `infrahub_request_duration_seconds`, `infrahub_graphql_duration_seconds` | [`metrics.mdx`](../../../docs/docs/deploy-manage/run-observe/metrics.mdx) |
| Is the database slow | `infrahub_db_query_execution_seconds`, `infrahub_db_connection_wait_seconds`, `infrahub_db_last_connection_pool_usage`, `infrahub_db_connection_pool_size` | same |
| Are locks slow | `infrahub_lock_acquire_seconds`, `infrahub_lock_reserved_duration_seconds` | same |
| Are the task workers saturated | `infrahub_task_flow_run_start_delay_seconds`, `infrahub_task_flow_runs_in_progress`, `prefect_work_queues_late_runs_count` | same |
| Is the API rejecting requests | `infrahub_admission_*` | same |
| Which code is slow | Spans `execute_graphql`, `Query.execute`, `execute_db_query_with_metadata` and the flow run spans | [`observability.md`](../../knowledge/backend/observability.md) |
| What happened in that trace | Loki lines with `trace_id` | same, "Logs" |

The shipped data source UIDs are `localprometheus`, `localloki` and `localtempo`
(`development/grafana/provisioning/datasources/datasource.yml`), but the skill finds data sources by
type (FR-013), because the operator's own Grafana uses other UIDs.

## R8. Log audit, first pass

A first, read-only pass of the audit (FR-022). It reads the code only; the possible findings need a
check on a running instance. The full result goes into `log-audit.md` when the audit is
finished.

**Already fixed by INFP-742.** The single sign-on "SSO user authenticated" line writes `account_id`, not
the user name (commit `5a22997549`). Spans are masked (`backend/infrahub/masking.py::MASKING_RULES`,
`backend/infrahub/trace.py::MaskingSpanExporter`).

**How logs reach Loki and the Prefect server.**

- Alloy sends the logs of **every** container of the Compose project to Loki:
  `development/alloy/config.alloy`, `discovery.docker "containers"`, whose only filter is the label
  `com.docker.compose.project`. So Loki also holds the logs of Neo4j (`database`), RabbitMQ
  (`message-queue`), Redis (`cache`), the Prefect server (`task-manager`) and its database
  (`task-manager-db`), Grafana, and the Grafana MCP server itself. The first pass below covers only the
  lines that Infrahub writes; the other streams are part of the full audit (spec FR-022, critique of
  2026-11-04, X1). For Helm, which pods the chart's Alloy collects is not checked yet.
- `backend/infrahub/log.py::configure_logging` sets the structlog processors. None masks a value.
  `httpx` and `httpcore` log only at ERROR.
- In production, the API server writes no access log (`serve/worker.py::InfrahubUvicorn` sends
  `uvicorn.access` to a null handler, and gunicorn runs without `--access-logfile`). So no client IP
  address or request URL is logged.
- Flow run logs go to the Prefect server through Prefect's `APILogHandler`
  (`workers/infrahub_async.py::_init_logger`). That handler does not run the structlog processors. A
  failed flow also sends its exception message and stack trace.

**Confirmed findings.**

| Where | Value written | Level | Fix |
|-------|---------------|-------|-----|
| `webhook/tasks/process.py::webhook_process`, through `webhook/log_formatter.py::outgoing_request` | The webhook URL with its query string, which can hold a token | INFO | Remove the query string |
| Same, through `log_formatter.py::delivery_succeeded` | `response.url` with its query string | INFO | Remove the query string |
| `services/adapters/http/httpx.py::HttpxAdapter._request` | The request URL with its query string, in log lines and in the messages of `HTTPServerTimeoutError`, `HTTPServerSSLError`, `HTTPServerError` | INFO or WARNING, on failure | Remove the query string in the adapter |
| `auth/auth.py::get_groups_from_provider` (Google, `fetch_groups` on) | The user's email address in the URL query string, written by the adapter on failure | INFO or WARNING, on failure | Send the email as a request parameter; the adapter fix removes it from logs |

**Possible findings, to check on a running instance.**

| Where | Value | Check |
|-------|-------|-------|
| `auth/auth.py::validate_auth_response`, `safe_get_response_body` | The token or user info endpoint URL, and the error body, at ERROR | An identity provider that returns HTTP 400 and 401 |
| Repository location with credentials (`https://user:token@host`), in `exceptions.py::RepositoryInvalidBranchError`, `git/base.py::_raise_enriched_error_static`, `RepositoryError` from Git's error output | User name and token | Add a repository with such a location and read the flow run log. `git/writeback/credentials.py::scrub_credentials` already removes them for write-back errors. |
| `webhook/tasks/process.py` payload lines (INFO truncated, DEBUG full) | Node attribute values, for example an account's email address | The payload of an account change event |
| `infrahub_sdk/retry.py::prepare_retry`, `rate_limit.py` | The API URL with its query string, at WARNING or ERROR | Whether any SDK call puts a token in the query string |

**Out of scope, with the reason.**

- The Google group IDs in the "SSO user authenticated" line: they are group addresses, not personal
  data of a user.
- The Neo4j driver's Bolt messages at `INFRAHUB_LOG_LEVEL=DEBUG`: off by default. The docs say that
  debug logs can contain query parameters.
- The access log of `uvicorn --reload` in `tasks/dev.py::start`: development only.

**Checked and clean.** Every log call in `backend/infrahub` whose arguments contain `token`,
`password`, `secret` or `email`, apart from the rows above; webhook header lines (`redact_headers`); the
GraphQL error formatter; `core/initialization.py::create_account` (built-in accounts only).

**Not checked.** Every path where an exception message that contains a value is logged with
`exc_info`; the Prefect server's own logs; the flow run parameters that the Prefect server stores; the
log streams of the other containers in Loki; the labels of the metrics in Prometheus; the resource
attributes of traces; whether `mcp-grafana` logs the caller token, the Grafana token or the queries it
runs. Each is part of the full audit (spec FR-022).

## R9. Infrahub version that the skill supports

**Decision.** 1.13 and later (spec clarification of 2026-11-04). The skill reads `infrahub_info{version}`
first (R6, rule `check-version-first`). `infrahub_info` exists before 1.13, so an older instance
answers with its version and the skill can name it.

## R10. Approvals and owners outside this repository

| Item | Needed from | Status on 2026-11-19 |
|------|-------------|----------------------|
| New container image in Compose and Helm: `grafana/mcp-grafana:2.0.2` | Engineering approval for new dependencies (root `AGENTS.md`, "Ask First") | Chosen by D10 of the [design document](https://app.notion.com/p/opsmill/Diagnose-a-slow-Infrahub-instance-3f2228b8302581a08eeaf9fc23a7f2de), whose status is "Approved" |
| The image of the init script (R5) | Engineering approval for new dependencies | Not needed: the init script uses the Grafana image of the stack, so it adds no new image |
| The one-time container (Compose) and the hook Job (Helm) that create the Grafana service account | Fatih Acar, engineering reviewer of the design document | Accepted on 2026-11-05 (comment on Appendix C, C5, of the design document) |
| Changes C2, C3 and C4 of Appendix C of the design document | Its engineering and architect reviewers | Not reviewed |
| Hosting the skill in `infrahub-skills` | Solution Engineering and Architecture team | Not asked |
| Security review of the container | Fatih Acar (decided by Daniel on 2026-11-04) | Not done, date not set |
| Whether `infrahub.opsmill.io` keeps `profiles` (R1) | Owner of the service | Not asked |

## R11. Repositories and pull requests

| Repository | Content |
|------------|---------|
| `opsmill/infrahub` | Compose services, converter change, unit tests of the Compose files, log fixes, docs, `development/grafana/AGENTS.md` rule, changelog fragments, `log-audit.md` |
| `opsmill/infrahub-helm` | `infrahub-observability` chart: the Deployment, Service, Secret handling and hook Job |
| `opsmill/infrahub-skills` | The skill, its graders, evals and fixtures, and the `DO NOT TRIGGER` cross-link in `infrahub-analyzing-diagnostics` |
