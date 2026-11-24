# Log audit: personal data and secrets that the Grafana MCP server can return

**Feature**: `spec.md` in this directory | **Requirements**: FR-022, FR-022a, FR-023, FR-024 | **Date**: 2026-11-19

The Grafana MCP server gives an AI assistant what Grafana can read: the log streams in Loki, the
traces in Tempo and the metrics in Prometheus. Everything it returns reaches the AI model provider.
This audit lists each place where a token, a password, an email address, a user name, a client IP
address or a URL query string reaches one of these three stores, and what was done about it.

## Result

- 7 findings are confirmed and fixed in the code that writes the line (rows 1 to 5, 3a and 6a).
- 1 finding is confirmed and not changed: a secret in the path of a webhook URL (row 3b). The docs
  name it.
- 1 finding is confirmed and not changed: the webhook payload line (row 6). Daniel decided on
  2026-11-19 to keep the line, so the docs must name it as data that reaches the AI model provider.
- 1 finding is in the Python SDK (row 7). It is not fixed in this repository. Its fix is delivered
  outside INFP-745, in [IFC-3658](https://opsmill.atlassian.net/browse/IFC-3658) (decided by Daniel
  on 2026-11-24).
- No value was found in a log stream that Infrahub does not write, so no Alloy `drop` rule was added
  and no stream is named in the docs under FR-022a.
- The flow run parameters that the Prefect server stores hold secrets (row 8). The Grafana MCP server
  cannot read them, so they are outside SC-004. They are recorded here because the task asks for it.

## How the audit was done

**Code reading.** The first pass of `research.md` R8, and the code paths named in the
rows below.

**Running stack.** One Compose stack built from the branch
`dp-20261119-grafana-mcp-compose-log-audit-infp-745`: the root `docker-compose.yml`, the standalone
observability file with the profile `grafana-mcp`, the trace sampling ratio set to 1, default log
levels. On it:

1. An account was created with a marker user name, label and password, and a description that holds
   a marker email address. The account logged in, and one login used a wrong password.
2. Requests were sent with an API token, with a JSON Web Token, with a wrong API key, and with a
   marker in the URL query string.
3. Three webhooks were created: one with `?token=secret-value` in its URL and a target that answers
   HTTP 200, one with the same query string and a host that does not exist, and one with a user and a
   password in its URL. An account update triggered them. They were created within a few seconds, so
   the first webhook was not active yet when the others were created. The creation event of a webhook
   was therefore not tested here. The manual test of the branch found it (row 6a).
4. Two repositories were added with a location of the form `http://git-user:secret-value@host/...`.
5. Grafana received a login with a wrong user name and password. The Grafana MCP server received a
   request with a wrong token and a Loki query that holds a marker.

Then each marker was searched for in:

- every log stream in Loki, by container, over the last hour, directly and through the Grafana MCP
  server (`query_loki_logs`);
- every span of the 163 traces in Tempo (744 spans): span names, span attributes, event attributes
  and resource attributes;
- every value of the 154 label names in Prometheus;
- the 281 flow run log records and the parameters of 200 flow runs in the Prefect server.

**Not checked.** Read these limits before you rely on the result:

- A single sign-on login. No identity provider was available, so rows 4 and 5 were checked by calling
  the functions with a provider response, not on the running stack.
- A real client IP address. Every request came from the Docker host, and the API server writes no
  access log in production (`research.md` R8).
- `INFRAHUB_LOG_LEVEL=DEBUG` and the debug levels of the other containers. The audit covers default
  log levels only.
- Every path where an exception message is logged with `exc_info`. The audit covers the paths that the
  five steps above reach: the HTTP adapter, the webhook delivery and the Git connectivity check.
- The Helm chart: which pods its Alloy collects (task T045, in `opsmill/infrahub-helm`).
- Neo4j Enterprise query logging, which is off in the Compose stack.
- Longer use. The stack ran for about 15 minutes, so a line that a service writes rarely, such as a
  PostgreSQL statement error, was not seen.

## Log lines that Infrahub writes

Each location is a file under `backend/infrahub/` and a function or symbol.

| # | Location | Value written | Level and default | Destination | Status | Fix |
|---|----------|---------------|-------------------|-------------|--------|-----|
| 1 | `webhook/log_formatter.py::WebhookLogFormatter.outgoing_request`, called by `webhook/tasks/process.py::webhook_post` | The webhook URL with its query string, user and password, which can hold a token | INFO, written by default | Loki and the Prefect server | Confirmed in the code. Fixed, and checked on the running stack: 0 lines hold `secret-value` | The line names the URL without its query string, fragment, user and password (`masking.py::url_without_secrets`). Test: `backend/tests/unit/webhook/test_log_formatter.py`. This branch |
| 2 | `webhook/log_formatter.py::WebhookLogFormatter.delivery_succeeded`, called by `webhook/tasks/process.py::webhook_send` | The URL of the response, with its query string | INFO, written by default | Loki and the Prefect server | Confirmed in the code. Fixed, and checked on the running stack | Same fix and same test file as row 1. This branch |
| 3 | `services/adapters/http/httpx.py::HttpxAdapter._request` | The request URL with its query string, in three log lines and in the messages of `HTTPServerTimeoutError`, `HTTPServerSSLError` and `HTTPServerError`. The message of the `httpx` error is written too, and can repeat the URL | INFO or WARNING, on a failed request only | Loki; the Prefect server when a flow logs the exception | Confirmed in the code. Fixed, and checked on the running stack with the webhook whose host does not exist | The lines and the messages name the URL without its query string, user and password. A URL inside the `httpx` error message keeps its path and loses its query string. Test: `backend/tests/unit/services/adapters/http/test_httpx.py`. This branch |
| 4 | `auth/auth.py::get_groups_from_provider` (Google, with `fetch_groups` on) | The email address of the user, in the URL query string that row 3 wrote on a failed request | INFO or WARNING, on a failed request only | Loki | Confirmed in the code. Fixed. Checked with a unit test, not on the running stack (no identity provider) | The email address is sent as a request parameter (`params`), a new optional argument of the `get` method of the HTTP adapter, so the URL that the adapter logs does not hold it. Test: `backend/tests/unit/auth/test_google_group_lookup.py`. This branch |
| 5 | `auth/auth.py::validate_auth_response` and `auth/auth.py::safe_get_response_body` | The URL of the identity provider's answer, with its query string if the configured URL has one | ERROR, when the provider answers with an error or an empty body | Loki | Possible in research R8. Confirmed for the URL by calling the functions with a provider answer; not checked on the running stack. Fixed | The `url` field is written without its query string. Test: `backend/tests/unit/auth/test_auth_response.py`. This branch |
| 3a | `services/adapters/http/httpx.py::HttpxAdapter._request`, the text of the `httpx` error in the WARNING line | A request header value. When a header value is not valid, for example an `Authorization` value that ends with a line break, the error text repeats it | WARNING, on such a request only | Loki; the Prefect server | Found by the review of the pull request, and confirmed there by running the adapter. Fixed | For an `httpx.LocalProtocolError`, the line writes the name of the error and not its text. Test: `backend/tests/unit/services/adapters/http/test_httpx.py`. This branch |
| 3b | Rows 1 to 3: the path of the URL | A secret in the path of a webhook URL. Slack, Discord and Microsoft Teams put the secret of an incoming webhook there | INFO, written by default | Loki and the Prefect server | Confirmed by reading the code. Not changed: the path is what tells the user where the webhook went, and Infrahub cannot tell which part of a path is a secret | Named in the webhook docs (`docs/docs/webhooks/overview.mdx`, "Header and payload logging"). The docs page of the Grafana MCP server must name it too (FR-026, task T058) |
| 5a | `auth/auth.py::validate_auth_response`, field `body` | The body of the provider's error answer, written in full. A provider can put a client ID or a user name in `error_description` | ERROR, when the provider answers with an error | Loki | Possible: not checked with a real provider answer. Fixed | The body is not logged. The line writes the `error` field of RFC 6749, a short code such as `invalid_grant`, when it is a string. Decided by Daniel on 2026-11-24. The error message that the user receives still holds `error_description`; it is not written to a log. Test: `backend/tests/unit/auth/test_auth_response.py`. This branch |
| 6 | `webhook/log_formatter.py::WebhookLogFormatter.outgoing_request`, the `Payload:` block (and `full_payload` at DEBUG) | The event payload: the values of the node that changed. For an account, the user name (its human-friendly ID) and its label. For any node, whatever its attributes hold, such as an email address | INFO for the first 2048 characters, written by default. DEBUG for the full payload | Loki and the Prefect server | Possible in research R8. Confirmed on the running stack: the task worker stream holds the marker user name (1 line) and the marker label (5 lines), and the Grafana MCP server returns them | Not changed, decided by Daniel on 2026-11-19, except for the URLs inside the payload (row 6a). The docs must name it (FR-026). See "Decision: the webhook payload line" below |
| 6a | Same lines as row 6, for the payload of the creation event of a webhook | The URL of the new webhook, with its token in the query string, or its user and password. A webhook that listens to all events receives the creation event of every other webhook. The shared key of the new webhook did not appear | INFO, written by default | Loki and the Prefect server | Found by the manual test of the branch: a webhook that listens to all events wrote `?token=secret-value` of a webhook created later, in `task-worker-2`, and Loki returned it. Fixed in the log copy | The logged copy of the payload, in both lines, has the user and password removed and the query string replaced by `[MASKED]` in every URL inside it (`masking.py::replace_url_secrets_in_nested`). The payload that is sent does not change. Test: `backend/tests/unit/webhook/test_log_formatter.py`. This branch |
| 7 | Python SDK: `infrahub_sdk/retry.py::prepare_retry` and the HTTP 429 lines of `infrahub_sdk/rate_limit.py`, used by the task workers | The API URL with its query string. No SDK call puts a token in it. `query_gql_query` puts the variables of a stored GraphQL query in it, and a variable can hold personal data | WARNING, then ERROR after a long retry. Written on a transient failure only | Loki and the Prefect server | Possible in research R8. Confirmed by reading the SDK code; no retry happened on the running stack | Not fixed here: the line is in `opsmill/infrahub-sdk-python`. It needs a change there and an update of the `python_sdk` submodule. Moved to [IFC-3658](https://opsmill.atlassian.net/browse/IFC-3658), outside INFP-745 |
| 8 | Flow run parameters, stored by the Prefect server for each flow run | The repository location with its user and password (`git-repository-check-connectivity`), the webhook URL with its query string (`Configure webhook`), the webhook payload with node values (`Send webhook`) | Stored for every flow run | The Prefect server's database only. Not Loki, Tempo or Prometheus | Confirmed on the running stack (5 flow runs hold `secret-value`). The Grafana MCP server cannot read it | None in this work. It is outside SC-004. Reported to Daniel as a separate finding for anyone who can read the Prefect API or its database |

### Checked and clean

| Location | Value looked for | Result |
|----------|------------------|--------|
| Repository location with credentials: `exceptions.py::RepositoryInvalidBranchError`, `git/base.py::_raise_enriched_error_static`, the error output of Git | User name and token | Clean on the running stack. Git writes the location as `http://*****:*****@host/...`, and the two error messages that were raised name the repository, not its location. `RepositoryInvalidBranchError` was not raised: its message holds the location, so it stays possible for a branch that does not exist on a repository that can be reached |
| Login with a wrong password, request with a wrong API key | The password, the key | Clean: 0 lines |
| Requests with an API token or a JSON Web Token | The token | Clean: 0 lines in Loki, 0 span attributes |
| Request with a marker in the URL query string | The query string | Clean: 0 lines. In spans, `http.url` ends with `?[MASKED]` |
| Account creation and login | The user name, the password, the description with an email address | Clean in the API server stream. The user name appears only through row 6 |
| Webhook `shared_key`, webhook headers | The key | Clean: 0 lines, headers are redacted |
| Every log call in `backend/infrahub` whose arguments contain `token`, `password`, `secret` or `email` | These values | Clean by code reading (research R8) |
| The "SSO user authenticated" line | The user name | Clean by code reading: it writes the account ID (fixed by INFP-742) |

### Out of scope, with the reason

- Google group IDs in the "SSO user authenticated" line: group addresses, not personal data of a user.
- Bolt messages of the Neo4j driver at `INFRAHUB_LOG_LEVEL=DEBUG`: off by default.
- The access log of `uvicorn --reload` in `tasks/dev.py::start`: development only.

## Log streams that Infrahub does not write (Compose)

Alloy sends the logs of every container of the Compose project to Loki
(`development/alloy/config.alloy`). Each stream was searched for every marker, and read for user
names and for IP addresses outside the Docker network.

| Container | Lines read | Result |
|-----------|-----------:|--------|
| `database` (Neo4j) | 20 | Clean. One start line names the database user `neo4j` |
| `message-queue` (RabbitMQ) | 219 | Clean. Start lines name the service user `infrahub`, which is not a person |
| `cache` (Redis) | 60 | Clean |
| `task-manager` (Prefect server) | 261 | Clean. It does not write flow run parameters to its log |
| `task-manager-db` (PostgreSQL) | 49 | Clean |
| `infrahub-grafana` | 6 | Clean. At `GF_LOG_LEVEL=warn`, a login with a wrong user name and password writes neither value |
| `infrahub-grafana-mcp` | 12 | Clean. It writes neither the caller token, a wrong token, the Grafana token nor the text of a query |
| `infrahub-grafana-mcp-init` | 6 | Clean, read with `docker logs`. It writes neither the token nor the admin password |
| `infrahub-loki`, `infrahub-tempo`, `infrahub-alloy`, `infrahub-cadvisor`, `infrahub-node-exporter` | 1461 | Clean |

**FR-022a.** No `drop` rule was added to `development/alloy/config.alloy`, and no stream needs a docs
entry, because no value was found. This holds for default log levels only (see "Not checked").

Helm: not checked (task T045, in `opsmill/infrahub-helm`).

## Metric labels in Prometheus

154 label names were read, with all their values. No marker was found.

| Label | Holds | Result |
|-------|-------|--------|
| `path` (Infrahub request metrics) | The route template, such as `/graphql/{branch_name:path}` | Clean: no query string |
| `name` (GraphQL metrics) | The GraphQL operation name that the client sent | Clean in the test. The client chooses this name, so it is free text |
| `query` (database metrics) | The name of the query class | Clean |
| `span_name` (metrics that Tempo builds from spans) | Flow run names, which hold object names, such as `Check connectivity for audit-repo` and `Configure webhook (configure) - audit-ok` | Clean in the test. An object named after a person would appear here |
| `instance`, `host`, `url`, `address` | Container addresses, the Prometheus write URL, network card addresses of the Docker host | No personal data |
| `user` (Loki metrics) | The Loki tenant, `fake` | No personal data |

## Trace attributes in Tempo

744 spans were read. No marker was found.

- Resource attributes: `service.name`, `service.version` and `worker.id` only.
- Masked by INFP-742 and seen masked: `net.peer.ip` (35 spans) and the query string of `http.url`.
- `prefect.run.parameter.*`: Prefect writes the type of each flow run parameter, such as `dict` or
  `str`, not its value.
- `prefect.run.name` and span names hold flow run names, which hold object names (see `span_name`
  above).
- `query` holds the Cypher text with parameter names, not values. The spec keeps it readable
  (FR-026).

**FR-024.** `backend/tests/unit/test_trace.py` already shows that a span exported through
`MaskingSpanExporter` has its token and user name attributes replaced
(`SpanAttributeMaskingTestCase` cases `access_token` and `user_name_in_one_word`, tests
`test_exported_attribute` and `test_exported_event_attribute`). No test was added. On the running
stack, the Grafana MCP server returned no marker from Tempo.

## Decision: the webhook payload line (row 6)

The INFO line of a webhook delivery writes the first 2048 characters of the payload. The payload is
the changed node, so it can hold any value that a user stored in Infrahub. The line exists so that a
user can view what was sent, in the task logs of the web interface.

**Decision** (Daniel, 2026-11-19): the line stays as it is. The work of INFP-745 does not change the
current behavior of the stack, and writing the payload only at DEBUG would remove it from the task
logs that users view today.

**Added on 2026-11-23, with Daniel's agreement:** a URL inside the payload is written without its user,
password and query string (row 6a). The user name, the label and every other value stay in the line.

**What follows from the decision:**

- The docs page of the Grafana MCP server names this line as data that reaches the AI model provider:
  the values of a node that a webhook sends, for the events that the webhook is subscribed to
  (FR-026, task T058). Not written yet.
- The spec needs an update, because it does not allow this case today. FR-023 says that each log line
  that the audit lists is fixed where it is written. FR-022a and SC-004 allow a docs entry only for a
  stream that Infrahub does not write. SC-007 has the same limit. Not updated yet: the main session
  owns the spec.
- An operator who does not want these values to reach the AI model provider has no setting for it
  today.

Options that were not chosen:

1. Write the payload only at DEBUG. Not chosen: it changes what users view in the task logs.
2. An Alloy `drop` rule for the payload lines, so that they reach the Prefect server and not Loki. Not
   chosen: it changes what the stack sends to Loki.
