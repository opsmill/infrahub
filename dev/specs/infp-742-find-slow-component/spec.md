# Feature Specification: Find the Slow Component of an Infrahub Instance

**Feature Branch**: `dp-20261014-find-slow-component-infp-742`

**Created**: 2026-10-14

**Status**: Draft

**Input**: Jira idea [INFP-742](https://opsmill.atlassian.net/browse/INFP-742) (read on 2026-10-14) and
its design document [Diagnose a slow Infrahub instance](https://app.notion.com/p/opsmill/Diagnose-a-slow-Infrahub-instance-3f2228b8302581a08eeaf9fc23a7f2de)
(Notion, status "Approved", read in full on 2026-10-14). INFP-742 follows
[INFP-611](https://opsmill.atlassian.net/browse/INFP-611). This spec covers
only the part of that work that INFP-742 plans for Infrahub 1.13: phases 1 to 4 and 6 of the design
document. Bug (B) and decision (D) numbers refer to sections 4 and 5 of the design document.

## Summary

**Problem.** When an Infrahub instance is slow, the operator cannot tell which component causes it:
Neo4j, the API server, the task workers or the code of a generator. A background task that calls the
API through the Python SDK starts a new trace at each call, durations above 1 second are lost, the load
on the connection pool and on the task workers is hidden or not recorded, and changing the sampling
ratio needs a restart. Some shipped values are wrong, and single sign-on writes tokens and user details
into spans and logs. Every slowness report then becomes an OpsMill investigation without data.

**What is needed.**

- Follow one trace from a background task to its API calls and database queries, with any
  OpenTelemetry backend, and move between a trace and its log lines.
- View the real duration of queries and requests up to several minutes, the connection pool usage
  against its size, the time queries wait for a connection, and the task worker start delay per
  priority queue.
- Raise the sampling ratio for a chosen time during an incident, without a restart, and record who
  changed it.
- Keep tokens, user names, email addresses, client IP addresses and URL query strings out of spans and
  logs before any monitoring system stores them.
- Fix the shipped dashboards so that they show correct data in any Grafana.

**Not decided yet.**

- The cost of tracing at the default sampling ratio of 0.1. It is not measured. The limit is in
  SC-006.
- Why the HTTP metrics record no API or GraphQL request (B13). The cause is not known.
- Which personal data Infrahub writes into logs today. The audit is
  [INFP-745](https://opsmill.atlassian.net/browse/INFP-745); its results add fields to FR-013.

## Clarifications

### Session 2026-10-14

- Q: Does a Docker Compose installation with the observability stack turn tracing on after the
  upgrade? The design document (D3) says yes; the card's "Must not" forbade anything new until the
  operator changes a setting. → A: Follow the design document. The Compose file generated with the
  stack turns tracing on at the default ratio; this is the one exception to the "Must not" rule
  (FR-032). The card was updated to say so.
- Q: What does a masked value look like in spans and logs? → A: A fixed marker, `[MASKED]`. The
  attribute or field name stays, and a URL keeps its path (FR-013a).
- Q: Is the end time of a temporary ratio required, is there a maximum, and what does a second change
  do? → A: The end time is required, at most 24 hours ahead. A new change replaces the active one
  (FR-026).
- Q: Can the operator turn masking off, for example in their own monitoring system? → A: No. Masking
  is always on, and this card adds no setting for it (FR-013a). A setting can be a follow-up if
  operators ask for one.

### Session 2026-10-15

Source: [review by Damien Garros in Slack](https://opsmillworkspace.slack.com/archives/C08075KCU3A/p1792049481147779?thread_ts=1792048837.114539&cid=C08075KCU3A)
of the API changes. Answers decided by Daniel.

- Q: Should the ratio endpoints be hidden from the API schema? → A: No. Infrahub adds no hidden REST
  endpoint. The endpoints are public and documented, including why they exist (FR-036).
- Q: Where do the endpoints live? → A: Under a troubleshooting area of the API,
  `/api/troubleshooting`, so that later troubleshooting endpoints can go there too (FR-036).
- Q: Which permission changes the ratio? → A: The super admin permission, as for the response delay
  (FR-029). Damien confirmed it with the approval below.
- Q: Why a runtime endpoint and not a normal setting, and what do other tools do? → A: Keep both. The
  `INFRAHUB_TRACE_SAMPLE_RATIO` setting is the normal, documented default and needs a restart to
  change. The endpoint is for an incident, when a restart can remove the slow behaviour. Other tools
  use the same kind of administration endpoint, a central sampling server, or a vendor control panel;
  the comparison is in [research.md](research.md) R12.
- Approval: Damien Garros approved the API changes on 2026-10-15
  ([Slack](https://opsmillworkspace.slack.com/archives/C08075KCU3A/p1792057541808779?thread_ts=1792048837.114539&cid=C08075KCU3A)).
  He asked to track a central sampling server in the Python implementation of OpenTelemetry as the
  long-term solution: [IFC-3423](https://opsmill.atlassian.net/browse/IFC-3423), see
  [research.md](research.md) R12.

Decided by Daniel, after the approval:

- Q: Is the SDK work part of this feature's tasks, and how is it split? → A: Yes. Both SDK tickets are
  done in this feature, in the `python_sdk` submodule, with one pull request per ticket.
- Q: Does the SDK add a dependency on OpenTelemetry? → A: No. It uses OpenTelemetry only when the
  caller's process already has it (FR-001).

## Personas

From section "Personas" of the design document and "Customer use cases" of the card:

- **Operator**: installs, upgrades and runs the Infrahub instance, usually a platform or SRE team.
  Reads the dashboards, traces and logs in their own monitoring system or in the OpsMill
  observability stack, and changes the `INFRAHUB_*` settings.
- **Administrator**: an Infrahub account with the super admin permission. Often the same person as the
  operator.
- **Generator author**: writes generators, transforms and checks with the Python SDK. Their code runs
  in the task workers and sends queries through the SDK.

OpsMill support benefits when the operator can name the slow component and query in a report. One
person can have several roles.

## Terms

- **Trace**: the record of one request or background task from start to end, made of **spans**: one
  span per step, such as an HTTP request, a GraphQL operation or a database query.
- **Sampling ratio**: the share of traces that are recorded, from 0 (none) to 1 (all). The decision is
  made once, when the trace starts, so a trace is complete or absent.
- **Observability stack**: the optional set of monitoring services that OpsMill ships with Infrahub
  (Alloy, Prometheus, Loki, Tempo, Grafana and exporters). Installing it is
  [INFP-743](https://opsmill.atlassian.net/browse/INFP-743).
- **Priority queue**: the `high`, `medium` and `low` queues that background tasks wait in before a
  task worker starts them.
- **Flow run**: one run of a background task on a task worker.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Operator follows a slow background task to its database queries in one trace (Priority: P1)

Users report that a generator is slow. The operator opens the trace of the generator run. The trace
contains the flow run, every API call the generator made through the Python SDK, and the database
queries of each call. From a span, the operator opens its log lines; from a task worker log line, they
open its trace. A generator author finds the query they named with `query_name` inside the trace of
the task that sent it. This works with any OpenTelemetry backend.

Delivered in phase 3: D1, B10 and the `INFRAHUB_TRACE_SAMPLE_RATIO` setting of D3. Needs a change in
the Python SDK repository.

**Why this priority**: This is the main question of the card: which task caused the slow query. Today
each SDK call from a task worker starts a new trace, so the link is lost, and task worker log lines
carry no trace ID.

**Independent Test**: With tracing on, run a generator that sends several named queries through the
SDK, then open its trace and its task worker logs in Grafana.

**Acceptance Scenarios**:

1. **Given** tracing is on, **When** a task worker runs a generator that calls the API through the
   SDK, **Then** the flow run, its API calls and their database queries form one trace.
2. **Given** an API request, **When** the operator views its trace, **Then** each database query span
   is a child of the request span.
3. **Given** a generator author names a query with `query_name`, **When** the operator views the trace
   of the task that sent it, **Then** the query name appears in that trace.
4. **Given** a traced flow run, **When** the operator reads its task worker log lines, **Then** each
   line carries the trace ID of that trace.
5. **Given** a trace in Grafana, **When** the operator opens "Logs for this span", **Then** Grafana
   shows the log lines of that trace and no others.
6. **Given** a log line with a trace ID in Grafana, **When** the operator opens its trace link,
   **Then** Grafana opens that trace, including for a trace ID that starts with a zero.
7. **Given** a log line written before the upgrade, with the old `0x` form of the trace ID, **When**
   the operator opens its trace link, **Then** Grafana opens that trace.
8. **Given** an SDK script that runs outside Infrahub with OpenTelemetry installed, **When** it calls
   the API, **Then** the API spans join the script's trace. Without OpenTelemetry, the script behaves
   as today.
9. **Given** `INFRAHUB_TRACE_SAMPLE_RATIO` is 0.5, **When** many requests run, **Then** about half of
   them produce a trace, and a request whose caller already decided to record it is always recorded.
10. **Given** an operator installs or upgrades Infrahub with the Compose file generated with the
    observability stack, **When** Infrahub starts, **Then** tracing is on, spans go to the stack's
    Tempo, and the default sampling ratio applies.
11. **Given** an instance without the observability stack, **When** it is upgraded, **Then** tracing
    stays off and nothing new is sent.

---

### User Story 2 - Operator stores spans and logs that hold no secrets or personal data (Priority: P1)

The operator turns tracing on and sends spans and logs to their monitoring system. Before any span or
log line leaves the API server or the task worker, Infrahub masks tokens, user names, email
addresses, client IP addresses and URL query strings. The Cypher text, URL paths and query names stay
readable, so the operator can still diagnose a slow query. Single sign-on no longer writes the access
token, the user information, the authorization code, the state or the user name.

Delivered in phase 1: B7, B8, and the masking step for spans and the redaction step for logs of D9.

**Why this priority**: Today anyone with access to the trace store can read single sign-on tokens and
user details. The card requires that B8 ships before tracing is turned on for more operators.

**Independent Test**: With tracing on, log in through single sign-on, send requests with query strings
and a client IP address, then search the trace store and the log store for the token, the code, the
state, the user name, the email address and the IP address.

**Acceptance Scenarios**:

1. **Given** tracing is on, **When** a user logs in through single sign-on, **Then** no span contains
   the access token or the user information returned by the identity provider.
2. **Given** tracing is on, **When** the identity provider redirects to the single sign-on token
   endpoint with a `code` and a `state` in the URL, **Then** the span has the URL path and no code or
   state.
3. **Given** a user logs in through single sign-on, **When** the operator reads the log line of the
   login, **Then** it contains the account ID and not the user name.
4. **Given** a span that contains a token, a user name, an email address, a client IP address or a URL
   query string, **When** it reaches the trace store, **Then** each of those values reads `[MASKED]`
   and the attribute name is still present.
5. **Given** a span of a database query, **When** it reaches the trace store, **Then** its Cypher text,
   URL path and query name are still readable.
6. **Given** a log line, including a Prefect or gunicorn log line, with a key that names a token, a
   password, an email address or a user name, **When** it reaches the log store, **Then** the value of
   that key is masked.
7. **Given** a request fails with an exception whose message contains a URL with a `code` and a `state`
   in its query string, **When** the span reaches the trace store, **Then** its exception event shows
   the URL path followed by `?[MASKED]`.
8. **Given** a flow run writes a log line with a token, **When** the line is sent to the Prefect
   server, **Then** the token reads `[MASKED]`.
9. **Given** a single sign-on login fails with an exception whose message contains a URL with a `code`
   and a `state`, **When** the log line reaches the log store, **Then** the URL shows its path
   followed by `?[MASKED]`.

---

### User Story 3 - Operator views the real duration of slow requests and the load on the connection pool (Priority: P2)

During an incident, the operator opens the Infrahub dashboard. Duration panels show the real value of
a slow query or request, for example 30 seconds, instead of stopping at 1 second. HTTP panels include
API and GraphQL requests. The operator views connection pool usage against the pool size, and how long
queries wait for a connection. The panel that counts API requests against the admission limit says
that it is not the connection pool.

Delivered in phases 1 and 2: B4, B5, B9, B13 and D6.

**Why this priority**: Pool starvation and long queries are named on the card. Today a 30-second query
is shown as 1 second, so the operator underestimates how slow the instance is, and the pool is on no
panel.

**Independent Test**: Run a load that holds connections, a database query that lasts more than 30
seconds, a GraphQL request and an `/api/…` request, then open the Infrahub dashboard.

**Acceptance Scenarios**:

1. **Given** a database query that lasts 30 seconds, **When** the operator views the query duration
   panels, **Then** the panels show a value near 30 seconds, not 1 second.
2. **Given** an HTTP request that lasts several minutes, **When** the operator views the request
   duration panels, **Then** the value is recorded up to 20 minutes.
3. **Given** a lock held for 2 minutes, **When** the operator views the lock panels, **Then** the value
   is recorded as about 2 minutes, not 10 seconds.
4. **Given** a GraphQL request and an `/api/…` request, **When** the operator views the HTTP panels,
   **Then** both requests are counted with their route.
5. **Given** queries hold connections, **When** the operator opens the Infrahub dashboard, **Then** it
   shows pool usage against pool size, and the time queries wait for a connection.
6. **Given** the panel that counts running API requests against the admission limit, **When** the
   operator reads its title and description, **Then** they say that it counts API requests and that it
   is not the Neo4j connection pool.
7. **Given** several API worker processes have recorded requests, **When** one of them starts or
   restarts, **Then** the request and query counts of the other processes are still on the dashboard.
8. **Given** an API worker process that stopped, **When** the operator views pool usage against pool
   size, **Then** that process no longer shows a value.

---

### User Story 4 - Operator views task worker saturation per priority queue (Priority: P2)

The operator views how long background tasks wait before a task worker starts them, and how many
tasks each worker runs at the same time. A "Priority queues" row shows, for each of the `high`,
`medium` and `low` queues, the start delay and the runs in progress. A rising delay on `high` means
users are waiting.

Delivered in phase 4: D5.

**Why this priority**: Worker saturation is named on the card. Today no metric shows the queue delay,
and no panel separates the priority queues.

**Independent Test**: Start more flow runs than the workers can handle at once, on each queue, and open
the "Priority queues" row.

**Acceptance Scenarios**:

1. **Given** a flow run that starts later than its expected start time, **When** the worker starts it,
   **Then** the recorded start delay equals the real start time minus the expected start time.
2. **Given** a worker starts a flow run, **When** the run is in progress and then ends, **Then** the
   count of runs in progress rises and then falls.
3. **Given** a flow run dispatched to the `high` queue, **When** it is counted, **Then** it is counted
   under the `high` queue.
4. **Given** an operator who does not run the Prefect exporter, **When** they collect the task worker
   metrics, **Then** they still receive the start delay and the runs in progress.

---

### User Story 5 - Operator uses the shipped dashboards in any Grafana (Priority: P2)

The operator imports the shipped dashboards into their own Grafana, or uses them in the OpsMill
stack. Every Infrahub panel shows data. Panels that cannot have data in the operator's Neo4j edition
are explained. The Prefect panels count flow runs, not states.

Delivered in phase 1: B2, B3, B12 and the dashboard rule of section 5 of the design document.

**Why this priority**: The card requires that the dashboards work in any Grafana, not only in the
OpsMill stack (review thread in Slack). Some panels are empty or show wrong counts today.

**Independent Test**: Import each shipped dashboard into a Grafana with only a Prometheus data source
and Infrahub's metrics, then into the OpsMill stack on a Linux host.

**Acceptance Scenarios**:

1. **Given** a Grafana with only a Prometheus data source and Infrahub's metrics, **When** the operator
   imports a shipped dashboard, **Then** its Infrahub panels show data.
2. **Given** a dashboard used in the OpsMill stack, **When** the operator opens it, **Then** it looks
   as today, because each fixed value became a template variable whose default is today's value.
3. **Given** a flow with runs, **When** the operator views "Flow Runs total", **Then** it equals the
   number of runs.
4. **Given** the log panels of both Prefect dashboards, **When** the operator opens them, **Then** they
   show log lines.
5. **Given** the Prefect CPU and memory panels, **When** the operator opens them, **Then** they show
   data, or the panels are removed.
6. **Given** a Neo4j Community instance, **When** the operator opens the Neo4j dashboard, **Then** it
   shows only panels that can have data, and a note says why the server panels need Neo4j Enterprise.

---

### User Story 6 - Administrator records more traces during an incident, without a restart (Priority: P3)

During an incident, an administrator raises the sampling ratio through the API or `infrahubctl` for a
chosen time, for example 1.0 for 30 minutes. Every running API server and task worker uses the new
ratio within seconds. At the end time, the default ratio applies again. Infrahub records an event with
who changed the ratio, the old and new values and the end time.

Delivered in phase 6: D4. Needs story 1 (the default ratio).

**Why this priority**: At the default ratio, most slow traces are not recorded. A restart to change
the ratio can remove the slow behaviour the operator wants to record.

**Independent Test**: With tracing on, set the ratio to 1.0 for 2 minutes, check that every new request
is traced, then check that the default applies after 2 minutes.

**Acceptance Scenarios**:

1. **Given** tracing is on, **When** an administrator sets the ratio to 1.0 for 30 minutes, **Then**
   every running API server and task worker records every new trace within seconds.
2. **Given** a ratio change with an end time, **When** the end time passes, **Then** every process uses
   the default ratio again.
3. **Given** a ratio change, **When** the administrator clears it before the end time, **Then** every
   process uses the default ratio again.
4. **Given** a ratio change, **When** it is applied, **Then** Infrahub creates an event with the
   account, the old value, the new value and the end time.
5. **Given** an account without the super admin permission, **When** it tries to change the ratio,
   **Then** the request is rejected.
6. **Given** tracing is off, **When** an administrator tries to change the ratio, **Then** the API and
   `infrahubctl` return "Tracing is not enabled on this instance; set `INFRAHUB_TRACE_ENABLE`".
7. **Given** a process that starts after the change, **When** it records traces, **Then** it uses the
   default ratio.
8. **Given** an administrator, **When** they set a ratio without an end time or with an end time more
   than 24 hours ahead, **Then** the change is rejected with an error that names the limit.
9. **Given** an active ratio change, **When** the administrator sends a new change, **Then** the new
   ratio and end time replace the active ones in every process.

---

### Edge Cases

- **Process restarts during an incident**: a process that starts after a ratio change uses the default
  ratio until the administrator sends the change again. Traces that start on other processes stay
  complete, because a process follows the decision of its caller (design document, D4).
- **Processes disagree for a few seconds**: just after a ratio change, processes can use different
  ratios. A trace is still complete or absent, because the decision follows the caller.
- **The default ratio drops slow traces**: at 0.1, 9 slow traces in 10 are not recorded. The
  administrator raises the ratio during the incident (story 6).
- **Instance without tracing**: nothing is traced, and the ratio cannot be changed at runtime until the
  operator turns tracing on and restarts once.
- **Operator runs their own monitoring system**: they turn tracing on with the existing
  `INFRAHUB_TRACE_*` settings and their own collector. The default ratio and the runtime ratio apply in
  the same way.
- **SDK caller without OpenTelemetry**: the SDK sends no trace context and behaves as today.
- **Query longer than the SDK waits**: the SDK stops waiting after 60 seconds, but the server records
  the full duration, up to 20 minutes for HTTP requests.
- **Connection wait limit**: the Neo4j driver stops waiting for a connection after 60 seconds and
  raises an error, so 60 seconds is the highest wait value.
- **Neo4j driver upgrade removes the internal method that gives out connections**: a test fails, and a
  failure while recording the connection wait never stops a query (design document, D6).
- **Masking changes what the operator views**: masked values are no longer readable in their own
  Grafana, and the operator cannot tell whether two slow requests came from the same user or IP
  address. Cypher text, URL paths and query names stay readable.
- **Text inside a log message that is not a known field**, such as an email address in an exception
  message, is not masked until the log audit lists it (design document, D9). URL query strings are the
  one exception: they are replaced in the message and exception text of every log line (FR-013). Only
  URLs with a scheme (`https://…?…`) are found in free text; a request target without one
  (`GET /api/…?code=…`) keeps its query string. Infrahub writes no access log today (uvicorn's access
  logger has a null handler and gunicorn has no access log configured), so no such line exists.
- **Docker Desktop for macOS**: cAdvisor sends container metrics without the container name, so panels
  that filter by container are empty there. The Prefect panel fix must be checked on a Linux host
  (design document, B2).
- **Trace ID format change**: the API server log field `trace_id` changes from `0x` plus hexadecimal to
  32 lowercase hexadecimal characters. Queries and alerts that operators wrote against the old form
  must change. This is a breaking change: the changelog names it as one, with the old and the new
  form, and the upgrade notes tell operators to update their queries.
- **Upgrade**: no data migration. Provisioned dashboards are replaced, so edits to them are lost, as
  today.

## Requirements *(mandatory)*

### Functional Requirements

**One trace from task to query (story 1)**

- **FR-001**: The Python SDK MUST send the W3C trace context with every API request when OpenTelemetry
  is installed in the caller's process. The SDK MUST NOT declare a dependency on OpenTelemetry, not even
  an optional one: it uses OpenTelemetry only when the caller's process already has it.
- **FR-002**: A flow run, its SDK calls and their database queries MUST form one trace.
- **FR-003**: Task worker log lines of a traced flow run MUST carry the trace ID.
- **FR-004**: The API server and the task workers MUST write the trace ID in log lines as 32 lowercase
  hexadecimal characters, with leading zeros and without `0x`.
- **FR-005**: The shipped Grafana data sources MUST link a span to its log lines and a log line to its
  trace, including log lines with the old `0x` form. The settings MUST be documented for operators who
  run their own Grafana.
- **FR-006**: A new setting, `INFRAHUB_TRACE_SAMPLE_RATIO`, MUST set the default share of traces that
  are recorded, from 0 to 1, with a provisional default of 0.1. It MUST be listed in the configuration
  reference with the other `INFRAHUB_TRACE_*` settings.
- **FR-007**: Sampling MUST follow the caller's decision when the caller sends a trace context, so a
  trace is complete or absent.
- **FR-008**: An automated test MUST confirm that database query spans are children of the request
  span.

**No secrets or personal data in spans and logs (story 2)**

- **FR-009**: Single sign-on spans MUST NOT contain the access token or the user information returned
  by the identity provider (B7, [IFC-3330](https://opsmill.atlassian.net/browse/IFC-3330)).
- **FR-010**: Spans MUST NOT contain the authorization code or the state sent to the single sign-on
  token endpoints. The single sign-on login log line MUST name the account ID, not the user name (B8).
- **FR-011**: FR-009 and FR-010 MUST ship before tracing is turned on for more operators (card, scope).
- **FR-012**: Before a span leaves the API server or the task worker, Infrahub MUST mask tokens, user
  names, email addresses, client IP addresses and URL query strings in its attributes and in the
  attributes of its events, including the exception events. In `exception.message` and
  `exception.stacktrace`, URL query strings MUST be replaced, because the stack trace repeats the
  message. Cypher text, URL paths and query names MUST stay readable.
- **FR-013**: In every log line, including Prefect and gunicorn log lines, Infrahub MUST mask, before
  any log pipeline reads it, the values of keys that name a token, a password, an email address or a
  user name, and the fields that the log audit
  ([INFP-745](https://opsmill.atlassian.net/browse/INFP-745)) lists. In the message and the exception
  text of every log line, the query string of each URL MUST be replaced, as in `exception.message` of
  spans (FR-012).
- **FR-013a**: To mask a value, Infrahub MUST replace it with the fixed marker `[MASKED]` and keep the
  attribute or field name. In a URL, only the query string is replaced; the path stays readable. Two
  masked values cannot be told apart. Masking is always on: no setting turns it off.

**Durations and connection pool (story 3)**

- **FR-014**: Database query durations MUST be recorded up to 300 seconds, HTTP request durations up to
  1200 seconds, connection wait up to 60 seconds and lock durations up to 300 seconds. The bucket limits
  are listed in decision D6 of the design document.
- **FR-015**: Panels that read the old highest bucket limits MUST be checked and corrected.
- **FR-016**: The HTTP request metrics MUST record API and GraphQL requests with their route (B13).
- **FR-017**: Infrahub MUST export the connection pool size and the time a query waits for a
  connection. The Infrahub dashboard MUST show pool usage against pool size, and the wait time.
- **FR-018**: When an API worker process starts or restarts, the metric values recorded by the other
  running processes MUST be kept. Each gauge MUST declare how values from several processes are
  combined, so that a process that stopped no longer shows a value (B9).
- **FR-019**: The panels that count API requests against the admission limit MUST be renamed and
  described so that they cannot be read as the Neo4j connection pool (B5).

**Task worker saturation (story 4)**

- **FR-020**: Each task worker MUST record the start delay of each flow run (real start time minus
  expected start time) and the number of flow runs in progress, each by flow name and priority queue.
  The flow label MUST never be a run ID.
- **FR-021**: The Infrahub dashboard MUST show a "Priority queues" row with, for each queue, the start
  delay p95 and the runs in progress.

**Dashboards in any Grafana (story 5)**

- **FR-022**: Every shipped dashboard MUST work in any Grafana: its queries use Infrahub's metric names
  and template variables for job, instance and container. Each fixed value becomes a template variable
  whose default is today's value. No panel is removed for this reason.
- **FR-023**: The Prefect dashboards MUST count flow runs, not states, MUST read the `namespace`
  variable from the log store, and MUST NOT show run time panels that read a metric the exporter does
  not publish (B12).
- **FR-024**: The Prefect CPU and memory panels MUST show data with the stack's own metrics, or MUST be
  removed (B2).
- **FR-025**: On Neo4j Community, the Neo4j dashboard MUST NOT show panels that cannot have data and
  MUST explain why. The stack MUST NOT collect from a Neo4j metrics endpoint that does not exist (B3).

**Ratio without restart (story 6)**

- **FR-026**: An administrator MUST be able to set a temporary sampling ratio with an end time through
  the API and `infrahubctl`, and to clear it before the end time. The end time is required and MUST
  be at most 24 hours after the change; a change without an end time, with an end time in the past
  or more than 24 hours ahead, or with a ratio outside 0 to 1 MUST be rejected with an error that
  names the limit. A new change replaces the active one.
- **FR-027**: Every running API server and task worker MUST apply a change within seconds, without a
  restart, and MUST return to the default ratio at the end time.
- **FR-028**: The temporary ratio MUST NOT be stored in the database. A process that starts after the
  change MUST use the default ratio.
- **FR-029**: Changing the ratio MUST require the super admin permission.
- **FR-030**: Each change MUST create an Infrahub event with the account, the old value, the new value
  and the end time.
- **FR-031**: When tracing is off, the API and `infrahubctl` MUST return an error that tells the
  administrator to set `INFRAHUB_TRACE_ENABLE`.

**Compatibility and documentation**

- **FR-032**: An upgraded instance MUST NOT send or trace anything new until the operator changes a
  setting (card, "Must not"), with one exception: the Docker Compose file generated with the
  observability stack (`?observability=true`) MUST turn tracing on, send spans to the stack's Tempo and
  set the default sampling ratio, as decision D3 and section 3 of the design document say. A Compose
  operator who already runs the stack therefore sends traces after the upgrade, at the default ratio.
  An instance without the stack keeps tracing off.
- **FR-033**: The changes MUST NOT need a database migration.
- **FR-034**: The documentation MUST include the observability knowledge page
  (`dev/knowledge/backend/observability.md`), an updated `metrics.mdx`, and a new page "Send Infrahub
  telemetry to your own monitoring" that covers metrics, traces to any OTLP collector, and logs with the
  trace ID. The operator documentation MUST also explain:
  - How to raise the sampling ratio during an incident, with the `infrahubctl` command once it exists
    and the REST call until then.
  - How to check that every API server and task worker applied a ratio change, from the log line that
    each process writes when it applies one.
  - How to reduce the cost of tracing: set a temporary ratio of 0 for up to 24 hours without a
    restart, then lower `INFRAHUB_TRACE_SAMPLE_RATIO` or set `INFRAHUB_TRACE_ENABLE` to false at the
    next restart.
- **FR-035**: Each process MUST write one log line when it applies or clears a temporary ratio, with
  the ratio and the end time.
- **FR-036**: The endpoints that read, set and clear the temporary ratio MUST be public: listed in the
  API schema, under a troubleshooting area of the API, and documented with what they do, who may call
  them and why they exist. Infrahub MUST NOT add a hidden REST endpoint for this feature.

### Key Entities

- **Trace context**: the identifier of a trace and the caller's sampling decision, sent from the SDK to
  the API server so both sides record one trace.
- **Default sampling ratio**: the share of traces recorded when no temporary ratio is set. Set by the
  operator at startup.
- **Temporary sampling ratio**: a ratio with an end time, set by an administrator, kept only in the
  memory of each process.
- **Ratio change event**: the record of a temporary ratio change: account, old value, new value, end
  time.
- **Connection pool metrics**: the pool size, the pool usage and the time a query waits for a
  connection, per API worker process.
- **Task worker saturation metrics**: the start delay and the runs in progress, by flow name and
  priority queue.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a slow generator, the operator finds the slowest database query and the task that sent
  it from one trace, without matching separate traces by hand.
- **SC-002**: A 30-second database query is shown as about 30 seconds on the duration panels, not as
  1 second.
- **SC-003**: Every shipped dashboard shows data in its Infrahub panels in the OpsMill stack and in a
  Grafana with only Infrahub's metrics. No panel is empty because of a defect in what is shipped.
- **SC-004**: After an administrator raises the ratio, every running process applies it within 10
  seconds, without a restart.
- **SC-005**: No token, authorization code, state, user name, email address, client IP address or URL
  query string appears unmasked in the trace store. No URL query string and no field listed by the log
  audit appears unmasked in the log store.
- **SC-006**: At the default sampling ratio, tracing adds at most 5 % to the API p95 response time and
  at most 5 % to CPU use, compared with tracing off on the same load. If the measurement is higher, the
  default ratio is lowered until it passes. This is measured before tracing is turned on for more
  operators.
- **SC-007**: From a trace, the operator reaches its log lines, and from a task worker log line, its
  trace, in one step, for every trace ID including those that start with a zero.
- **SC-008**: Measured after release: for the slowness reports that OpsMill support receives in the
  3 months after Infrahub 1.13, the share in which the operator names the slow component and the slow
  query. The baseline is taken from the slowness reports received before 1.13; its value is not known
  yet.

## Assumptions

- The plan and the tasks of this spec cover the `infrahub` repository and two changes in
  [infrahub-sdk-python](https://github.com/opsmill/infrahub-sdk-python), made in the `python_sdk`
  submodule, one pull request each on `infrahub-develop` (decided on 2026-10-15). The SDK pull requests
  merge before the submodule pointer moves:
  - The `traceparent` header (FR-001): [IFC-3419](https://opsmill.atlassian.net/browse/IFC-3419).
  - The `infrahubctl` command to change the ratio (FR-026):
    [IFC-3420](https://opsmill.atlassian.net/browse/IFC-3420).
- The link from the API server to a task worker already works: Prefect carries the trace context to the
  flow run. Checked by hand on 2026-10-07 on the development stack (design document, section 1).
- The card lists phase 1 as "B2 to B5, B7, B8 and B12". B1 and B6 are in the Helm chart and the
  install guide, which INFP-743 covers. B11 (the Prefect server shown as down) is in phase 1 of the
  design document but not named on the card; it is not known whether it was left out on purpose. This
  spec leaves it out.
- The Redis metrics (D7) are out of this spec: the card moves the Redis exporter to INFP-743.
- The 10-second limit in SC-004 is a target chosen for this spec. The card and the design document say
  only "within seconds".
- A local draft of everything except the SDK change was tested on a development stack on 2026-10-13
  and 2026-10-14 (card, solution overview). Its code is not part of this spec.
- How slow is too slow (SLOs) is tracked in
  [INFP-408](https://opsmill.atlassian.net/browse/INFP-408).

## Out of Scope

- **Installing the stack, the Helm chart and the Redis exporter**:
  [INFP-743](https://opsmill.atlassian.net/browse/INFP-743).
- **Redis dashboards and the Prefect event stream panels** (how far each Prefect consumer group is
  behind, and the dead-letter queue): [INFP-743](https://opsmill.atlassian.net/browse/INFP-743),
  added on 2026-10-15 after
  [Fatih's request](https://opsmillworkspace.slack.com/archives/C08075KCU3A/p1792047478027969) and a
  [customer incident](https://opsmillworkspace.slack.com/archives/C0B8Z19RB1C/p1792037644127899?thread_ts=1791926464.093109&cid=C0B8Z19RB1C).
  Their alert rules: [INFP-746](https://opsmill.atlassian.net/browse/INFP-746).
- **Traces in the support bundle** (phase 5, D2) and **the AI skill and the Grafana MCP server**
  (phase 7, D8, D10): not in the 1.13 goals of the card.
- **Sampling by GraphQL operation**: a follow-up, not planned.
- **Publishing the dashboards for import**, for example on grafana.com: a follow-up, not planned.
- **Alerting**: [INFP-746](https://opsmill.atlassian.net/browse/INFP-746) (design document, section 6).
- **A maximum number of concurrent flow runs per task worker**: the start delay per queue shows
  saturation instead (design document, section 6).

## Sources

- [INFP-742](https://opsmill.atlassian.net/browse/INFP-742): the card this spec implements
- [Design doc: Diagnose a slow Infrahub instance](https://app.notion.com/p/opsmill/Diagnose-a-slow-Infrahub-instance-3f2228b8302581a08eeaf9fc23a7f2de):
  sections 1 to 6 and appendices A and B
- [Review thread in Slack, 2026-10-08 and 2026-10-09](https://opsmillworkspace.slack.com/archives/C08075KCU3A/p1791550490171499?thread_ts=1791466634.093319&cid=C08075KCU3A),
  as cited by the card (not read for this spec)
- [INFP-611](https://opsmill.atlassian.net/browse/INFP-611): the card this one follows
- [INFP-743](https://opsmill.atlassian.net/browse/INFP-743), [INFP-745](https://opsmill.atlassian.net/browse/INFP-745),
  [INFP-542](https://opsmill.atlassian.net/browse/INFP-542), [IFC-3330](https://opsmill.atlassian.net/browse/IFC-3330)
