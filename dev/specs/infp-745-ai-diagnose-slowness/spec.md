# Feature Specification: Find the Slow Component of an Infrahub Instance with an AI Assistant

**Feature Branch**: `dp-20261104-ai-diagnose-slowness-infp-745`

**Created**: 2026-11-04

**Status**: Draft

**Input**: Jira idea [INFP-745](https://opsmill.atlassian.net/browse/INFP-745) (read on 2026-11-04) and
its design document [Diagnose a slow Infrahub instance](https://app.notion.com/p/opsmill/Diagnose-a-slow-Infrahub-instance-3f2228b8302581a08eeaf9fc23a7f2de)
(Notion, status "Approved", fetched on 2026-11-04: decisions D8, D9 and D10, section 6 and phase 7).
INFP-745 follows [INFP-611](https://opsmill.atlassian.net/browse/INFP-611) and depends on
[INFP-742](https://opsmill.atlassian.net/browse/INFP-742), whose spec is
[`dev/specs/infp-742-find-slow-component/spec.md`](../infp-742-find-slow-component/spec.md).
Decision (D) numbers refer to section 4 of the design document.

## Summary

**Problem.** When users report that an Infrahub instance is slow, the operator does not know which of
the dashboards, metrics or traces answers the question. No AI tool reads the live data of an instance:
the two diagnostics skills in [`opsmill/infrahub-skills`](https://github.com/opsmill/infrahub-skills),
`infrahub-collecting-diagnostics` and `infrahub-analyzing-diagnostics`, work offline from a support
bundle. Everything that Grafana returns to an AI assistant also reaches the AI model provider, so
personal data in traces and logs must not be there.

**What is needed.**

- The operator turns on a Grafana MCP server in the observability stack with one setting and a token.
  Each user connects their AI assistant to it with one URL and that token.
- A skill, `infrahub-diagnosing-performance`, runs the checks in a fixed order, finds the slow
  component from the stack's metrics, traces and logs, and writes a report with the evidence.
- When the shipped dashboards do not answer the question, the skill describes the query and the panel
  that would answer it, so the operator can add it in Grafana. Building the dashboard itself and
  offering it to OpsMill come in a later release (story 4).
- No token, password, email address or user name that Infrahub writes reaches the AI model provider. A
  log audit lists where Infrahub writes personal data into logs, and each finding is fixed where the
  line is written.
- Nothing leaves the operator's network without their choice, including the Grafana MCP server's
  usage statistics.

**Customer evidence.** An Enterprise customer, during its proof of concept in September and October
2026:

- had a slowness case: load shedding and exhausted API workers while about 12,000 computed attributes
  were updated. OpsMill connected Grafana to watch CPU spikes and the back-offs of the web interface, and an
  OpsMill engineer helped read the observability data
  ([POC update in Slack, 2026-09-29](https://opsmillworkspace.slack.com/archives/C0BAHJT7FK5/p1790701544445299?thread_ts=1790701544.445299&cid=C0BAHJT7FK5));
- built a Grafana dashboard with an AI assistant through a Grafana MCP server
  ([Slack message, 2026-09-30](https://opsmillworkspace.slack.com/archives/D0C3E146LBE/p1790756990768129),
  a direct message that only its participants can open);
- showed in a session with OpsMill how useful the Grafana MCP server was to connect its observability
  data to its own AI agents (Daniel, 2026-11-04). No written record of that session is known.

The customer is not named here because this repository is public; the Slack links are readable only
by OpsMill staff.

**Not decided yet.**

- Whether the Solution Engineering and Architecture team, which owns `infrahub-skills`, agrees to host
  the skill. Not asked yet.
- Whether the installation can create the Grafana service account and its token. Not verified.
- Whether the Grafana MCP server container passes a security review. Not done. Fatih Acar does it
  (clarification of 2026-11-04); the date is not set.
- The skill name `infrahub-diagnosing-performance` is a first draft.

## Clarifications

### Session 2026-11-04

- Q: Which Infrahub versions does the skill support? → A: 1.13 and later. INFP-742 adds and changes
  metrics in 1.13, so the checks find no data on earlier versions. On an earlier version, the skill
  says that the version is not supported (FR-021).
- Q: Which Grafana write tools does the server keep? D10 turns on all of them. → A: Only the tools for
  dashboards, folders and annotations, which the skill uses (D8). The tools for data sources, plugins,
  alert rules, silences and the tool that calls any Grafana API route are off, and the Grafana service
  account has the Editor role, which cannot create data sources or install plugins (FR-010,
  [research.md](research.md) R4). Replaced for 1.13 by the next answer.
- Q: Does building dashboards (story 4) ship in 1.13? It is the only story that needs write tools. →
  A: No. 1.13 ships a server that only reads: no write tools, and a Grafana service account with the
  Viewer role (FR-010). Story 4, FR-017 and FR-018 come in a later release, with the write tools of
  the previous answer. In 1.13, when the dashboards do not answer the question, the skill describes
  the query and the panel instead (FR-017a). Reason: a smaller security review for the 1.13 release
  condition, and the diagnosis, which is the main value, does not need write tools.
- Q: Who does the security review of the Grafana MCP server container? No source names one. → A:
  Fatih Acar, from Daniel's team, who reviewed the INFP-742 masking and retention decisions. The date
  is not set; the card's goals place the four release conditions in the first weeks of 1.13.
- Q: Which customer cases show the need for an AI-assisted diagnosis? → A: An Enterprise customer's
  proof of concept: a slowness case read with Grafana, a dashboard built with AI through a Grafana MCP
  server, and a session where the customer showed the use of the Grafana MCP server with its own
  agents. See "Customer evidence" in the Summary. The customer is not named because the repository is
  public (decided by Daniel).
- Q: Can the operator open the server to the local network or another network, without an SSH tunnel
  or a proxy? → A: Yes. The loopback address stays the default. One setting changes the address that
  the port listens on, and two optional settings give the server a TLS certificate and its private
  key, which `mcp-grafana` 2.0.2 serves itself (`--server.tls-cert-file` and
  `--server.tls-key-file`). The docs say to use TLS whenever the port is open to a network (FR-006,
  FR-006a, [research.md](research.md) R3). Asked by Daniel on 2026-11-04.

### Critique of 2026-11-04

Source: [critiques/critique-20261104-142632.md](critiques/critique-20261104-142632.md). Daniel chose to
apply all its suggested edits.

- Loki holds the logs of every container of the Compose project, not only Infrahub's, so the log audit
  covers every log stream in Loki, the metric labels and the trace resource attributes (FR-022,
  FR-022a, SC-004).
- The server listens only on the host's loopback address by default. Access from another computer goes
  through an SSH tunnel or a reverse proxy with TLS (FR-006, FR-025).
- Smaller changes: token rotation and the Grafana admin password in the docs (FR-025); the next step
  when no trace was sampled (story 2, scenario 5); the eval pass criterion (SC-003); a measure after
  release (SC-008).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Connect an AI assistant to the stack's Grafana (Priority: P1)

The operator runs Infrahub with the observability stack, installed with Docker Compose or with the
`infrahub-observability` Helm chart. They turn on the Grafana MCP server with one setting and set a
token. They share the URL and the token with the people who diagnose the instance. Each person adds
the URL and the token to their AI assistant, such as Claude Code, and the assistant can read the
stack's metrics, traces and logs.

**Why this priority**: The skill cannot read any data until this works. The design document requires
a setup that is simple for the user (D10, review comment).

**Independent Test**: With the setting on and a token set, in Compose and in Helm, connect Claude Code
to the Grafana MCP server with the URL and the token, and list the stack's data sources from the
assistant. This works without the skill.

**Acceptance Scenarios**:

1. **Given** a stack with the setting off, **When** it starts, **Then** no Grafana MCP server
   container runs and no new network address is open.
2. **Given** the setting on and a token set, **When** a user adds the URL and the token to their AI
   assistant, **Then** the assistant reads the stack's Prometheus, Tempo and Loki data.
3. **Given** the setting on and no token set, **When** the stack starts, **Then** the Grafana MCP
   server container does not start and its log names the missing setting.
4. **Given** a running Grafana MCP server, **When** a request arrives without the token or with a wrong
   token, **Then** the server rejects it.
5. **Given** a running Grafana MCP server, **When** a diagnosis runs, **Then** the server sends no
   usage statistics to Grafana Labs.

---

### User Story 2 - Find why the instance is slow (Priority: P1)

Users report that the instance is slow. The operator asks their AI assistant why. The skill checks
that the data sources it needs exist, compares request and task durations, finds the slow component in
the metrics (Neo4j, the API server, the task workers or the code of a generator), opens a slow trace,
reads the log lines of that trace and writes a report. Each finding in the report names the metric,
trace or log line it comes from, so the operator can open it in Grafana.

**Why this priority**: This is the outcome the card asks for: a first diagnosis without knowing which
panel or query to read.

**Independent Test**: From recorded Grafana MCP server responses of a known slow query, the skill
names the slow query and its component (design document, section 6, test for D8).

**Acceptance Scenarios**:

1. **Given** an instance where one query is slow, **When** the operator asks why the instance is slow,
   **Then** the report names the slow query, the component that runs it and the evidence for each
   finding.
2. **Given** a Grafana without a Tempo or a Loki data source, **When** the skill starts, **Then** it
   says which data source is missing and which checks it cannot run, and runs the other checks.
3. **Given** a Grafana where the data source IDs differ from the shipped stack, **When** the skill
   runs, **Then** it finds the data sources at run time and runs its checks.
4. **Given** the operator's own Grafana with Prometheus, Tempo and Loki data sources that hold
   Infrahub's data, **When** the skill runs, **Then** it works as with the shipped stack.
5. **Given** no trace was sampled for the slow requests, **When** the skill reaches the trace check,
   **Then** the report says so and gives the next step: a super admin raises the sampling ratio for a
   limited time without a restart ([INFP-742 spec](../infp-742-find-slow-component/spec.md), FR-026
   to FR-031), and the operator asks again after the slowness happens.

---

### User Story 3 - Keep personal data away from the AI model provider (Priority: P1)

The operator connects an AI assistant to Grafana. Everything that Grafana returns reaches the AI model
provider. The operator needs to know that Infrahub does not write tokens, passwords, email addresses
or user names into the traces and logs that the assistant reads, and which data does reach the
provider.

**Why this priority**: The card lists it as a must-have, and the card's goals make the log audit a
condition of the release.

**Independent Test**: After a single sign-on login and a set of requests that carry a token, a user
name and an email address, query Tempo and Loki through the Grafana MCP server for that time window.
No response contains these values.

**Acceptance Scenarios**:

1. **Given** the log audit is done, **When** a reviewer reads its result, **Then** it lists each log
   line that writes personal data, with its file and the field, or states that it found none.
2. **Given** a log line that the audit lists, **When** the fix is merged, **Then** the line no longer
   writes the value.
3. **Given** the operator reads the docs, **When** they plan to connect an AI assistant, **Then** the
   docs say which data reaches the AI model provider and which data Infrahub masks.

---

### User Story 4 - Build a missing dashboard and contribute it (Priority: P2, later release)

Not in 1.13 (clarification of 2026-11-04). This story ships in a later release, when the server keeps
the dashboard, folder and annotation write tools. In 1.13, the skill describes the missing query and
panel instead (FR-017a).

The operator needs a view that the shipped dashboards do not have. They ask the assistant to build it
instead of editing it by hand in Grafana. When the dashboard helped, the skill asks whether to
contribute it to OpsMill and, on a yes, proposes it as a GitHub issue or pull request.

**Why this priority**: The card lists the contribution as "nice to have". Building a dashboard is part
of the solution overview, but the diagnosis in story 2 works without it.

**Independent Test**: Ask for a view that the shipped dashboards do not have. The skill builds a
dashboard and offers to contribute it (design document, section 6, test for D8).

**Acceptance Scenarios**:

1. **Given** the shipped dashboards do not show what the operator asks for, **When** they ask the
   assistant, **Then** the skill builds or changes a dashboard in Grafana.
2. **Given** a dashboard the skill built, **When** it helped, **Then** the skill asks whether to
   contribute it, and sends nothing to GitHub without the user's yes.
3. **Given** the skill changed a shipped dashboard, **When** the operator upgrades the stack, **Then**
   the shipped version of the dashboard is restored.

---

### Edge Cases

- No slow trace is available, because tracing is off or the sampling ratio missed the slow requests:
  the report says that no trace was found and why, lists the findings from metrics alone, and gives
  the next step (story 2, scenario 5).
- The instance runs Infrahub 1.12 or earlier: the skill says that the version is not supported and
  that the operator must upgrade to 1.13 or later (FR-021).
- The slow trace is older than 24 hours: Loki keeps logs 24 hours
  ([INFP-742 spec](../infp-742-find-slow-component/spec.md), clarification of 2026-10-19), so the
  trace has no log lines. The report says so.
- The operator publishes the Grafana MCP server on another port or host name: without a change to the
  allowed hosts, no AI assistant can connect. The docs say which setting to change.
- The operator uses another monitoring tool, such as Datadog: the skill does not work with it
  (design document, Appendix B). The skill says which data sources it needs.
- A metric, a span or a dashboard UID that the skill reads is renamed: the skill breaks. A rule in
  [`development/grafana/AGENTS.md`](../../../development/grafana/AGENTS.md) requires updating the skill
  in the same change.
- Anyone with the shared token reads all telemetry in Grafana, and Grafana cannot tell which person ran
  which query. Each person's own Grafana token is an option for operators who need to know (FR-010).
- The installation cannot create the Grafana service account and its token: not known yet. The
  operator would then set two tokens by hand, as today.

## Requirements *(mandatory)*

### Functional Requirements

#### Grafana MCP server container in Compose and Helm (story 1)

- **FR-001**: The Docker Compose installation and the `infrahub-observability` Helm chart MUST include
  a Grafana MCP server container that is off by default. When it is off, no container runs and no new
  network address is open (D10).
- **FR-002**: The operator MUST turn the container on with one setting: a Compose variable or a Helm
  value (D10).
- **FR-003**: The container MUST require a token that has no default value. The operator sets it with a
  Compose variable, a Helm value or their own Kubernetes Secret (D10).
- **FR-004**: When the container is on and no token is set, the container MUST NOT start, and MUST log
  an error that names the missing setting (D10).
- **FR-005**: The server MUST reject a request that has no token or a wrong token. Clients send the
  token as `Authorization: Bearer` (D10, verified with `mcp-grafana` 2.0.2 on 2026-10-14).
- **FR-006**: A user MUST connect their AI assistant with one URL and the token, and no other step
  (D10). By default, the server MUST listen only on the loopback address of the host (Compose) or on
  a cluster-internal Service (Helm), because without TLS it serves plain HTTP and the token is its
  only protection (critique of 2026-11-04). The operator MUST be able to open the port to a network
  with one setting: the listen address in Compose, the Service type or an Ingress in Helm
  (clarification of 2026-11-04). Access through an SSH tunnel, `kubectl port-forward` or a reverse
  proxy with TLS stays possible.
- **FR-006a**: The operator MUST be able to give the server a TLS certificate and its private key, so
  that the server serves HTTPS and the token is encrypted between the AI assistant and the server.
  TLS is off by default. When only one of the two is set, the container MUST NOT start, and MUST log
  an error that names both settings (clarification of 2026-11-04).
- **FR-007**: The server MUST accept requests addressed to its published address. The default allowed
  hosts are `localhost:8100` and `127.0.0.1:8100`, and the operator changes them with one setting
  (D10).
- **FR-008**: The container MUST turn off the usage statistics that the server sends to Grafana Labs
  by default. Nothing leaves the operator's network without their choice (D10, decided on
  2026-10-14).
- **FR-009**: The installation MUST create the Grafana service account and its token that the
  container uses to reach Grafana, so that the operator sets only the token that AI assistants send.
  Grafana cannot create a service account from a provisioning file, so a one-time step calls the
  Grafana API: a job in Helm and a one-time container in Compose. Not verified yet (D10, section 6).
- **FR-010**: In 1.13, the server MUST keep no write tool and MUST NOT keep the tool that calls any
  Grafana API route. The Grafana service account MUST have the Viewer role (clarification of
  2026-11-04; this replaces "write tools enabled" in D10). In the later release of story 4, the server
  keeps only the write tools for dashboards, folders and annotations, and the service account gets the
  Editor role; the write tools for data sources, plugins, alert rules, silences, contact points,
  snapshots and incidents stay off. Each person's own
  Grafana token, instead of the shared token, is an option for operators who need to know who ran
  which query (card, "Nice to have").

#### Diagnostic skill and dashboards (stories 2 and 4)

- **FR-011**: The skill MUST be published in [`opsmill/infrahub-skills`](https://github.com/opsmill/infrahub-skills)
  as `infrahub-diagnosing-performance` (name is a first draft), and MUST follow that repository's
  rules, including evals with fixtures for every rule (D8).
- **FR-012**: The skill MUST contain only Infrahub knowledge: which metric or span answers which
  question, and the order of the checks. General help with PromQL and TraceQL stays in
  [`grafana/skills`](https://github.com/grafana/skills) (D8).
- **FR-013**: The skill MUST find the Prometheus, Tempo and Loki data sources at run time, without
  fixed IDs. When one is missing, it MUST say which one and which checks it cannot run (D8).
- **FR-014**: The skill MUST run the checks in this order: check the data sources, compare request and
  task durations, find the slow component in the metrics, open a slow trace, read the log lines of
  that trace (card, solution overview, step 4).
- **FR-015**: The skill MUST write a report. Each finding MUST name its evidence: the metric query, the
  trace ID or the log line, so that the operator can open it in Grafana.
- **FR-016**: The skill MUST work with the operator's own Grafana when it has Prometheus, Tempo and
  Loki data sources with Infrahub's data (card, solution overview).
- **FR-017** (later release, story 4): When the shipped dashboards do not answer the question, the
  skill MUST build or change a dashboard in Grafana. The shipped dashboards stay in OpsMill's
  repositories and are restored at upgrade (D8).
- **FR-017a** (1.13): When the shipped dashboards do not answer the question, the skill MUST describe
  the query and the panel that would answer it, with the data source, so that the operator can add
  it in Grafana by hand. The skill MUST NOT try to change Grafana.
- **FR-018** (later release, story 4): When a dashboard helped, the skill MUST ask the user whether to
  contribute it. On a yes, it exports the dashboard and proposes it as a GitHub issue or pull request
  on [`development/grafana`](../../../development/grafana). It MUST send nothing to GitHub without the
  user's yes (D8).
- **FR-019**: The skill and `infrahub-analyzing-diagnostics` MUST each list the other under
  `DO NOT TRIGGER`, so that an AI assistant picks the live diagnosis or the support bundle analysis
  as the user asks (design document, section 6, follow-ups).
- **FR-020**: [`development/grafana/AGENTS.md`](../../../development/grafana/AGENTS.md) MUST state that
  renaming a metric, a span or a dashboard UID updates the skill in the same change (design document,
  section 6, follow-ups).
- **FR-021**: The skill MUST support Infrahub 1.13 and later, because INFP-742 adds and changes
  metrics in 1.13. When the instance runs an earlier version, the skill MUST say that the version is
  not supported and that the operator must upgrade to 1.13 or later (clarification of 2026-11-04).

#### Log audit and personal data in traces and logs (story 3)

- **FR-022**: An audit MUST list each place where a token, a password, an email address, a user name,
  a client IP address or a URL query string reaches the data that the Grafana MCP server can return,
  with its source and its field (card, open questions; D9; critique of 2026-11-04). It MUST cover:
  - the log lines that Infrahub writes: the API server, the task workers, the Prefect and gunicorn
    logs, and the flow run logs that the task workers send to the Prefect server;
  - every other log stream that the stack sends to Loki, listed by container. In Compose, Alloy sends
    the logs of every container of the project (`development/alloy/config.alloy`): Neo4j, RabbitMQ,
    Redis, the Prefect server and its database, Grafana and the Grafana MCP server itself. For Helm,
    the pods that the chart's Alloy collects (not checked yet);
  - the labels of the metrics in Prometheus, and the resource attributes of traces.

  The result is recorded in this feature directory.
- **FR-022a**: For a value that the audit finds in a log stream that Infrahub does not write and
  cannot change, the stack MUST either stop sending that stream, or those lines, to Loki, or the docs
  MUST name it (FR-026). The audit records which of the two applies.
- **FR-023**: Each log line that the audit lists MUST be fixed where the line is written. Infrahub does
  not mask log lines ([INFP-742 spec](../infp-742-find-slow-component/spec.md), FR-013, clarification
  of 2026-10-19).
- **FR-024**: The masking of spans delivered by INFP-742 (its FR-012 and FR-013a) MUST hold for what
  the Grafana MCP server returns: a test MUST show that a span that carried a token and a user name
  reaches the AI assistant masked (D9 test).

#### Docs for connecting an AI assistant

- **FR-025**: [`observability-stack.mdx`](../../../docs/docs/deploy-manage/install-configure/install/observability-stack.mdx)
  MUST explain:
  - how to turn on the Grafana MCP server, set the token, change the allowed hosts and connect an AI
    assistant (D10);
  - how to reach the server from another computer: open the port to a network, SSH tunnel,
    `kubectl port-forward`, or a reverse proxy with TLS (FR-006);
  - how to turn on TLS with a certificate and a key, that TLS must be on whenever the port is open to
    a network, and that each AI assistant must trust the certificate (FR-006a);
  - how to change the token, and that the change needs a restart of the container;
  - that the default Grafana admin password must be changed when the server is turned on, and which
    setting the service account step reads it from.
- **FR-026**: The docs MUST say which data reaches the AI model provider: Infrahub masks tokens, user
  names, email addresses, client IP addresses and URL query strings in spans, and keeps Cypher text,
  URL paths and query names readable (D9). They MUST also name each log stream that the audit lists
  under FR-022a.
- **FR-027**: The Build with AI pages ([`index.mdx`](../../../docs/docs/overview/build-with-ai/index.mdx):
  "Where to start" table and MCP table; [`setup.mdx`](../../../docs/docs/overview/build-with-ai/setup.mdx):
  prerequisites; [`working-with-ai.mdx`](../../../docs/docs/overview/build-with-ai/working-with-ai.mdx))
  and [`faq.mdx`](../../../docs/docs/faq/faq.mdx) MUST link to the skill (design document, section 6).

### Key Entities

- **Grafana MCP server container**: a container in the observability stack that gives an AI assistant
  tools to read the stack's Grafana (and, from the release of story 4, to write dashboards, folders and
  annotations). Off by default. Has a published address, a list of
  allowed hosts and one shared token.
- **Token for AI assistants**: the value that each AI assistant sends to the Grafana MCP server. Set
  by the operator, no default value, shared with the users who diagnose the instance.
- **Grafana service account**: the Grafana account, and its token, that the container uses to reach
  Grafana. Created at installation (FR-009).
- **Diagnostic skill**: `infrahub-diagnosing-performance`, the instructions an AI assistant follows to
  diagnose a slow instance. Depends on Infrahub's metric names, span names and dashboard UIDs.
- **Diagnosis report**: the findings of one diagnosis. Names the slow component and, for each finding,
  the metric query, trace ID or log line it comes from.
- **Audit result**: the list of places where personal data or a secret reaches Loki, Tempo or
  Prometheus, with source, field and fix, or the docs entry for a stream that cannot be fixed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In Compose and in Helm, with the setting on and a token set, a person connects Claude
  Code to the stack's Grafana with one URL and one token, and no other step (D10 test).
- **SC-002**: With the setting off, 0 Grafana MCP server containers run. With the setting on and no
  token, the container does not start. Every request without the token or with a wrong token is
  rejected (D10 test).
- **SC-003**: For the eval fixtures of a known slow query, the skill names the slow query and its
  component, and gives the evidence for each finding (D8 test). The skill passes the eval threshold
  of `infrahub-skills` (today 3 trials and a 50 % pass rate); a stricter threshold for this skill is
  agreed with the repository owners if they accept one.
- **SC-004**: After a single sign-on login and requests that carry a token, a user name and an email
  address, 0 of these values appear in the traces, in any log stream in Loki and in the metric labels
  that the Grafana MCP server returns for that time window, apart from the streams that the docs name
  under FR-022a (D9 test).
- **SC-005**: During a diagnosis, the Grafana MCP server container opens 0 connections to hosts outside
  the operator's network.
- **SC-006**: In 1.13, asked for a view that the shipped dashboards do not have, the skill describes
  the query and the panel, and makes 0 changes in Grafana. In the later release of story 4, it builds
  a dashboard and offers to contribute it, and 0 issues or pull requests are created without the
  user's yes (D8 test).
- **SC-007**: Every log line that the log audit lists is fixed before the release, or, for a stream
  that Infrahub does not write, stopped or named in the docs (FR-022a).
- **SC-008**: After release, OpsMill support counts the slowness cases that arrive with a report from
  the skill, over the first two releases after 1.13. The measure needs no telemetry, because nothing
  leaves the operator's network (FR-008). No target is set: the first count is the baseline.

## Assumptions

- The skill lives in `opsmill/infrahub-skills`, the Compose files in this repository, and the Helm
  chart in [`opsmill/infrahub-helm`](https://github.com/opsmill/infrahub-helm). This spec covers all
  three. Each repository gets its own pull request.
- The container uses the [Grafana MCP server](https://github.com/grafana/mcp-grafana) (`mcp-grafana`
  v2.0.2) with the Streamable HTTP transport (D10).
- INFP-742 phases 1 to 3 are done: correct durations, one trace from a task to its queries, and
  `trace_id` in task worker logs. Its implementation commit `3f438ca96c` is in `develop`.
- The shared token is the default because it is the simplest setup for a first delivery. A random
  token generated at installation can come later if operators ask for it (D10).
- The Grafana Cloud hosted MCP server is out of scope: it works only with Grafana Cloud.
- An OpsMill MCP server for metrics, traces and logs is out of scope: it repeats the Grafana MCP
  server (D8).
- The Grafana MCP server is a new container image in Compose and Helm. It needs the engineering
  approval for new dependencies, which is not given yet.
- The audit (FR-022) covers the containers of the Compose project and the pods of the Helm chart. An
  operator's own Grafana can hold other data, which the operator is responsible for.

### Conditions for the 1.13 release

The card's goals make the release in 1.13 depend on four items, closed in the first weeks of 1.13:

- The log audit (FR-022).
- The agreement of the Solution Engineering and Architecture team to host the skill in
  `infrahub-skills`.
- The security review of the Grafana MCP server container, by Fatih Acar (date not set). In 1.13,
  anyone with the token can read all telemetry, and cannot change Grafana (FR-010). The later release
  of story 4 needs a new review of the write tools.
- The creation of the Grafana service account and its token at installation (FR-009).

## Sources

- [INFP-745](https://opsmill.atlassian.net/browse/INFP-745): the Jira idea.
- [Design doc: Diagnose a slow Infrahub instance](https://app.notion.com/p/opsmill/Diagnose-a-slow-Infrahub-instance-3f2228b8302581a08eeaf9fc23a7f2de):
  D8, D9, D10, section 6 and Appendix B.
- [INFP-742 spec](../infp-742-find-slow-component/spec.md): FR-012, FR-013, FR-013a and the
  clarification of 2026-10-19 on masking.
- [Review thread in Slack, 2026-10-08 and 2026-10-09](https://opsmillworkspace.slack.com/archives/C08075KCU3A/p1791550490171499?thread_ts=1791466634.093319&cid=C08075KCU3A).
- [Use of the Grafana MCP server inside OpsMill, Slack, 2026-08-07](https://opsmillworkspace.slack.com/archives/C07Q1AESZRR/p1786084324442399).
- [INFP-611](https://opsmill.atlassian.net/browse/INFP-611) and
  [INFP-488](https://opsmill.atlassian.net/browse/INFP-488).
