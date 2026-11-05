---
description: "Task list for INFP-745: find the slow component of an Infrahub instance with an AI assistant"
---

# Tasks: Find the Slow Component of an Infrahub Instance with an AI Assistant

**Input**: Design documents from `dev/specs/infp-745-ai-diagnose-slowness/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included. The plan's "Testing" list asks for unit tests of the Compose files and the
entrypoint, a component test of the service account script, a unit test for each log fix, Helm
template tests, and `skillgrade` evals with four fixtures per rule.

**Organization**: Tasks are grouped by user story. Story 4 (build and contribute a dashboard) is not in
1.13, so it has no task here (spec, clarification of 2026-11-04).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: The user story of the task (US1, US2, US3)

## Path Conventions

The work spans three repositories (plan, "Structure Decision"). A path without a prefix is in
`opsmill/infrahub`. A path in another repository starts with its name:

- `infrahub-helm:` is `opsmill/infrahub-helm`, chart `charts/infrahub-observability/`;
- `infrahub-skills:` is `opsmill/infrahub-skills`.

Cite a place in a file by its function or symbol, never by a line number.

---

## Phase 1: Setup (approvals and open questions)

**Purpose**: Ask for the approvals that research R10 lists. They are release conditions or block a
merge, and the answers take time.

- [ ] T001 Ask the engineering approval for the new images `grafana/mcp-grafana:2.0.2` and the init image (root `AGENTS.md`, "Ask First"); record the answer in the R10 table of `dev/specs/infp-745-ai-diagnose-slowness/research.md`
- [ ] T002 [P] Ask the Solution Engineering and Architecture team whether `infrahub-skills` hosts the skill and whether a stricter eval threshold is acceptable (SC-003); record the answer in R10 of `dev/specs/infp-745-ai-diagnose-slowness/research.md` and in "Not decided yet" of `spec.md`
- [ ] T003 [P] Ask the owner of `infrahub.opsmill.io` whether the service changes the standalone Compose file and keeps the `profiles` key; record the answer in R1 and R10 of `dev/specs/infp-745-ai-diagnose-slowness/research.md`
- [ ] T004 [P] Agree the date of the security review of the Grafana MCP server container with Fatih Acar; record it in R10 of `research.md` and in "Conditions for the 1.13 release" of `dev/specs/infp-745-ai-diagnose-slowness/spec.md`
- [ ] T005 Choose the image of the service account script between `curlimages/curl` (read `id` and `key` with `sed`) and the Grafana image (research R5); write the image and its digest into the "Services" table of `dev/specs/infp-745-ai-diagnose-slowness/contracts/compose-settings.md` (depends on T001)

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: None. Each story starts from Phase 1. Story 2 needs story 1's Compose services to record
its fixtures (see "Dependencies").

---

## Phase 3: User Story 1 - Connect an AI assistant to the stack's Grafana (Priority: P1) 🎯 MVP

**Goal**: The operator turns on the Grafana MCP server with one setting and a token, in Compose and in
Helm, and a user connects Claude Code with one URL and that token (FR-001 to FR-010).

**Independent Test**: With the profile on and a token set, connect Claude Code to
`http://localhost:8100/mcp` and list the data sources `Prometheus (Local)`, `Tempo (Local)` and
`Loki (Local)`, without the skill ([quickstart.md](quickstart.md), checks 1 to 6).

### Checks before the Compose services are written

- [ ] T006 [US1] On a running Compose stack, compare no `restart` key and `restart: on-failure:1` for `infrahub-grafana-mcp` after a missing token and after a restart of Docker; record the choice and the reason under "Restart policy" in `dev/specs/infp-745-ai-diagnose-slowness/contracts/compose-settings.md`
- [ ] T007 [US1] Choose how Compose mounts the two TLS files only when `INFRAHUB_GRAFANA_MCP_TLS_CERT_FILE` and `INFRAHUB_GRAFANA_MCP_TLS_KEY_FILE` are set, and check on a running stack that the stack starts with the profile on and no TLS setting; record the choice under "TLS files" in `dev/specs/infp-745-ai-diagnose-slowness/contracts/compose-settings.md`

### Tests for User Story 1 (write first, check that they fail)

- [ ] T008 [P] [US1] Extend `backend/tests/unit/test_observability_compose.py`: services `infrahub-grafana-mcp` and `infrahub-grafana-mcp-init` only in profile `grafana-mcp`; port `${INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS:-127.0.0.1}:8100:8000`; the options and variables of the contract (`--transport streamable-http`, `--allowed-hosts`, `--usage-stats=disabled`, `DO_NOT_TRACK=1`, `--disable-write --disable-api`, `GRAFANA_URL`, `GRAFANA_SERVICE_ACCOUNT_TOKEN_FILE`, `INFRAHUB_GRAFANA_MCP_LISTEN_ADDRESS` in the environment); `depends_on` with `service_completed_successfully`; the restart value from T006; the image pinned by tag and digest; the Grafana admin variables; the standalone file keeps the `profiles` key of both services and loads with the profile on and no TLS setting
- [ ] T009 [P] [US1] Create `backend/tests/unit/test_grafana_mcp_entrypoint.py`: run `development/grafana-mcp/entrypoint.sh` with `/bin/sh` and a stub `mcp-grafana` on `PATH` that prints its arguments; check exit code 1 and the contract message for no token, for one TLS setting only, and for `0.0.0.0` without TLS; check that `127.0.0.1`, `127.0.0.5` and `::1` start without TLS; check that both TLS settings add `--server.tls-cert-file` and `--server.tls-key-file`; check that no output contains the token value
- [ ] T010 [P] [US1] Create `backend/tests/component/test_grafana_mcp_service_account.py`: with testcontainers, start Grafana 11.1.5 and 11.4.0, run `development/grafana-mcp/create-service-account.sh` twice, and check that one token named `infrahub-grafana-mcp` exists and answers `GET /api/user`, that the account has the Viewer role (also when it existed with Editor), and that a wrong admin password gives the contract message

### Implementation for User Story 1 in Compose (`opsmill/infrahub`)

- [ ] T011 [P] [US1] Create `development/grafana-mcp/entrypoint.sh`: the token check, the TLS pair check, the check that refuses a listen address outside `127.0.0.0/8` and `::1` without TLS, with the messages of `contracts/compose-settings.md`, then `exec mcp-grafana` with the options of the contract (FR-004, FR-006a)
- [ ] T012 [P] [US1] Create `development/grafana-mcp/create-service-account.sh` with the four steps of research R5: wait for `GET /api/health` up to 5 minutes, keep a token that still works, find or create the account `infrahub-grafana-mcp` with the Viewer role, replace its token and write it to the token file; messages from the contract, never the token value (FR-009)
- [ ] T013 [US1] Add `infrahub-grafana-mcp-init`, `infrahub-grafana-mcp`, the volume `grafana_mcp_token` and `GF_SECURITY_ADMIN_USER`/`GF_SECURITY_ADMIN_PASSWORD` from `INFRAHUB_GRAFANA_ADMIN_USER`/`INFRAHUB_GRAFANA_ADMIN_PASSWORD` to `development/docker-compose-observability.yml`, as `contracts/compose-settings.md` describes, with the restart policy from T006 and the TLS mount from T007 (depends on T005, T011, T012)
- [ ] T014 [US1] Change `convert` in `development/convert_compose_standalone.py` so that it keeps the `profiles` key of the services in the `grafana-mcp` profile (research R1)
- [ ] T015 [US1] Regenerate `development/docker-compose-observability-standalone.yml` with `development/convert_compose_standalone.py`, and run T008, T009 and T010 until they pass (depends on T013, T014)
- [ ] T016 [P] [US1] Add the changelog fragment `changelog/+grafana-mcp-server.added.md` for the new optional Grafana MCP server, with the `creating-changelog-entries` skill

### Implementation for User Story 1 in Helm (`opsmill/infrahub-helm`)

- [ ] T017 [US1] In kind, start `grafana/mcp-grafana:2.0.2` with the probe settings of `contracts/helm-values.md` (`/healthz` on `--healthz-address`), without and with a TLS Secret; record whether the probes pass and which scheme they need in `dev/specs/infp-745-ai-diagnose-slowness/contracts/helm-values.md`
- [ ] T018 [P] [US1] Add the `grafanaMcp.*` values of `contracts/helm-values.md` to `infrahub-helm: charts/infrahub-observability/values.yaml`, with the image digest
- [ ] T019 [P] [US1] Copy `development/grafana-mcp/create-service-account.sh` to `infrahub-helm: charts/infrahub-observability/files/grafana-mcp/create-service-account.sh`, as `files/datasources.yaml` is copied (depends on T012)
- [ ] T020 [US1] Create `infrahub-helm: charts/infrahub-observability/templates/grafana-mcp-deployment.yaml`: the same options as Compose; the caller token through `secretKeyRef`; the Grafana token as a file from the Job's Secret; the TLS Secret mounted read-only with the two `--server.tls-*` flags; the probes from T017; `required` on the token and `fail` when `service.type` is not `ClusterIP` and `tls.existingSecret` is empty, with the messages of the contract (depends on T017, T018)
- [ ] T021 [P] [US1] Create `infrahub-helm: charts/infrahub-observability/templates/grafana-mcp-service.yaml` and `infrahub-helm: charts/infrahub-observability/templates/grafana-mcp-secret.yaml` (Secret only when the token is given as a value) (depends on T018)
- [ ] T022 [US1] Create `infrahub-helm: charts/infrahub-observability/templates/grafana-mcp-sa-job.yaml`: the `post-install,post-upgrade` hook Job with delete policy `before-hook-creation,hook-succeeded`, its ServiceAccount, and a Role and RoleBinding limited to `get`, `create` and `update` on the one token Secret (depends on T019)
- [ ] T023 [US1] Add `helm template` and `helm lint` tests to `infrahub-helm` as that repository runs them: no object when `grafanaMcp.enabled` is false; install fails without a token; install fails with `service.type: LoadBalancer` and no `tls.existingSecret`; the TLS flags appear only with a TLS Secret (depends on T020, T021, T022)

### Validation of User Story 1

- [ ] T024 [US1] Run [quickstart.md](quickstart.md) checks 1 to 6 on a Compose stack and a kind cluster; record in `dev/specs/infp-745-ai-diagnose-slowness/research.md` R3 which MCP clients work, how Claude Code handles a self-signed certificate, and whether a renewed certificate needs a restart (depends on T015, T023)

**Checkpoint**: The Grafana MCP server runs in Compose and Helm, and Claude Code reads the stack's
data with one URL and one token.

---

## Phase 4: User Story 2 - Find why the instance is slow (Priority: P1)

**Goal**: The skill `infrahub-diagnosing-performance` runs the checks in a fixed order, names the slow
component and gives the evidence for each finding (FR-011 to FR-016, FR-017a, FR-019 to FR-021).

**Independent Test**: From recorded Grafana MCP server responses of a known slow query, the skill
names the slow query and its component, and passes the eval threshold of `infrahub-skills` (SC-003).

### Fixtures

- [ ] T025 [US2] On the Compose stack of story 1, make one query slow with a generator that sends many queries, and record the `mcp-grafana` responses for these cases: a normal run, no Tempo data source, data source UIDs other than the shipped ones, Infrahub 1.12, no trace sampled, and a question that the dashboards do not answer; store them in `infrahub-skills: graders/infrahub-diagnosing-performance/fixtures/` (depends on T015)
- [ ] T026 [US2] Review every fixture in `infrahub-skills: graders/infrahub-diagnosing-performance/fixtures/` for host names, account names, tokens and other values from the recording stack, and replace them before the commit (depends on T025)

### Tests for User Story 2 (rule = test: each rule ships with its grader, eval task and four fixtures)

- [ ] T027 [US2] Add the checks of the six rules of research R6 (`check-version-first`, `check-datasources-first`, `follow-check-order`, `report-evidence-per-finding`, `describe-missing-panel`, `no-generic-query-help`) to `infrahub-skills: graders/infrahub-diagnosing-performance/lib.py` and one `check_<rule>.py` each, following `dev/guidelines/rule-equals-test.md` of that repository (depends on T026)
- [ ] T028 [US2] For each rule, add four fixtures (compliant, compliant but written differently, violating, violating near-miss) and a grader test in `infrahub-skills: tests/graders/`, and add one task per rule to `infrahub-skills: eval.yaml` (depends on T027)

### Implementation for User Story 2 (`opsmill/infrahub-skills`)

- [ ] T029 [P] [US2] Write `infrahub-skills: skills/infrahub-diagnosing-performance/rules/check-version-first.md`: read `infrahub_info{version}` first, stop before 1.13 and say to upgrade (FR-021)
- [ ] T030 [P] [US2] Write `infrahub-skills: skills/infrahub-diagnosing-performance/rules/check-datasources-first.md`: list Prometheus, Tempo and Loki data sources by type, never by UID, and name a missing one with the checks it stops (FR-013)
- [ ] T031 [P] [US2] Write `infrahub-skills: skills/infrahub-diagnosing-performance/rules/follow-check-order.md`: version, data sources, durations, component, trace, logs, with the metrics and spans of research R7 (FR-014)
- [ ] T032 [P] [US2] Write `infrahub-skills: skills/infrahub-diagnosing-performance/rules/report-evidence-per-finding.md`: each finding has a metric query and value, a trace ID, or a log line with its time (FR-015)
- [ ] T033 [P] [US2] Write `infrahub-skills: skills/infrahub-diagnosing-performance/rules/describe-missing-panel.md`: when the dashboards do not answer, describe the query, the panel type and the data source, and change nothing in Grafana (FR-017a)
- [ ] T034 [P] [US2] Write `infrahub-skills: skills/infrahub-diagnosing-performance/rules/no-generic-query-help.md`: send general PromQL and TraceQL questions to `grafana/skills` (FR-012)
- [ ] T035 [US2] Write `infrahub-skills: skills/infrahub-diagnosing-performance/SKILL.md` (front matter with `TRIGGER when:` and `DO NOT TRIGGER when:` naming `infrahub-analyzing-diagnostics`), `examples.md`, `reference.md` (research R7 table, the report format of `contracts/diagnosis-report.md`, the next step when no trace was sampled) and `rules/_sections.md` (depends on T029 to T034)
- [ ] T036 [P] [US2] Add the new skill under `DO NOT TRIGGER when:` in `infrahub-skills: skills/infrahub-analyzing-diagnostics/SKILL.md` (FR-019)
- [ ] T037 [US2] Regenerate `infrahub-skills: evaluations/*.json`, run the evals of the new skill as that repository's `dev/guides/getting-started.md` describes, and record the pass rate (SC-003) (depends on T028, T035, T036)

### Implementation for User Story 2 (`opsmill/infrahub`)

- [ ] T038 [P] [US2] Add the rule to `development/grafana/AGENTS.md`: a change that renames a metric, a span or a dashboard UID updates `infrahub-diagnosing-performance` in `infrahub-skills` in the same change (FR-020)
- [ ] T039 [P] [US2] Add a section about renaming to `dev/knowledge/backend/observability.md`: the skill reads metric names, span names and dashboard UIDs, and which ones (FR-020)

### Validation of User Story 2

- [ ] T040 [US2] Run [quickstart.md](quickstart.md) checks 7 and 8 with the skill installed from the `infrahub-skills` branch (depends on T037)

**Checkpoint**: The skill writes a report that names the slow component with evidence, and changes
nothing in Grafana.

---

## Phase 5: User Story 3 - Keep personal data away from the AI model provider (Priority: P1)

**Goal**: The audit lists each place where a token, a password, an email address, a user name, a client
IP address or a URL query string reaches Loki, Tempo or Prometheus, and each finding is fixed, dropped
or named in the docs (FR-022 to FR-024, FR-022a).

**Independent Test**: After a single sign-on login and requests that carry a token, a user name and an
email address, no response of the Grafana MCP server for that time window contains these values
(SC-004, [quickstart.md](quickstart.md) check 9).

### Audit

- [ ] T041 [US3] Create `dev/specs/infp-745-ai-diagnose-slowness/log-audit.md` with the fields of the "Log audit result" in `data-model.md`, and copy the confirmed, possible and clean rows of research R8 into it
- [ ] T042 [US3] On a running instance, check each possible finding of research R8 (`validate_auth_response` and `safe_get_response_body` in `backend/infrahub/auth/auth.py`, a repository location with credentials through `RepositoryInvalidBranchError` and `_raise_enriched_error_static`, the webhook payload lines in `backend/infrahub/webhook/tasks/process.py`, `prepare_retry` in the SDK), and the paths that log an exception message with `exc_info`; mark each row confirmed or clean in `log-audit.md` (depends on T041)
- [ ] T043 [P] [US3] Audit every other log stream in Loki by container in Compose (Neo4j, RabbitMQ, Redis, the Prefect server and its database, Grafana, and `infrahub-grafana-mcp`: caller token, Grafana token, queries), and the flow run parameters that the Prefect server stores; record each finding in `dev/specs/infp-745-ai-diagnose-slowness/log-audit.md` (depends on T015, T041)
- [ ] T044 [P] [US3] Audit the labels of the metrics in Prometheus and the resource attributes of traces in Tempo; record each finding in `dev/specs/infp-745-ai-diagnose-slowness/log-audit.md` (depends on T041)
- [ ] T045 [P] [US3] Check which pods the Alloy of `infrahub-helm: charts/infrahub-observability` collects, and record the list in `dev/specs/infp-745-ai-diagnose-slowness/log-audit.md` (depends on T041)

### Tests for User Story 3 (write first, check that they fail)

- [ ] T046 [P] [US3] In `backend/tests/unit/webhook/test_log_formatter.py`, test that `WebhookLogFormatter.outgoing_request` and `WebhookLogFormatter.delivery_succeeded` write the URL without its query string
- [ ] T047 [P] [US3] In `backend/tests/unit/services/adapters/http/test_httpx.py`, test that the log lines of `HttpxAdapter._request` and the messages of `HTTPServerTimeoutError`, `HTTPServerSSLError` and `HTTPServerError` contain the URL without its query string
- [ ] T048 [P] [US3] Create `backend/tests/unit/auth/test_google_group_lookup.py`: `get_groups_from_provider` for Google sends the email address as a request parameter, and the URL that the adapter logs on failure does not contain it
- [ ] T049 [P] [US3] Check that the tests of `MaskingSpanExporter` show a span with a token and a user name exported masked; if not, add that case next to them (FR-024)

### Implementation for User Story 3 (`opsmill/infrahub`)

- [ ] T050 [P] [US3] Remove the query string from the URL in `WebhookLogFormatter.outgoing_request` and `WebhookLogFormatter.delivery_succeeded` in `backend/infrahub/webhook/log_formatter.py` (depends on T046)
- [ ] T051 [P] [US3] Remove the query string from the URL in the log lines and exception messages of `HttpxAdapter._request` in `backend/infrahub/services/adapters/http/httpx.py` (depends on T047)
- [ ] T052 [P] [US3] Send the email address as a request parameter in `get_groups_from_provider` in `backend/infrahub/auth/auth.py` (depends on T048)
- [ ] T053 [US3] For each row that T042 confirms, add a failing unit test next to the module and fix the line where it is written; record the fix in `log-audit.md` (FR-023) (depends on T042)
- [ ] T054 [US3] For each value found in a stream that Infrahub does not write, add an Alloy `drop` rule to `development/alloy/config.alloy`, or mark the stream for the docs (FR-026); record which one in `log-audit.md` (FR-022a) (depends on T043, T044)
- [ ] T055 [US3] Add the same `drop` rules to the Alloy configuration of `infrahub-helm: charts/infrahub-observability` (depends on T045, T054)
- [ ] T056 [P] [US3] Add the changelog fragment `changelog/+log-query-string.security.md` for the URL query strings and the email address removed from logs, with the `creating-changelog-entries` skill (depends on T050 to T053)

### Validation of User Story 3

- [ ] T057 [US3] Run [quickstart.md](quickstart.md) check 9, and check that each confirmed row of `log-audit.md` has a fix with a passing test, a `drop` rule, or a docs entry (SC-004, SC-007) (depends on T053, T054, T055)

**Checkpoint**: No token, user name or email address that Infrahub writes reaches the AI assistant,
apart from the streams that the docs name.

---

## Phase 6: Polish & cross-cutting concerns

**Purpose**: Docs, checks across the three repositories and the release conditions.

- [ ] T058 [P] Add a section "Connect an AI assistant" to `docs/docs/deploy-manage/install-configure/install/observability-stack.mdx` with every item of FR-025 (turn on, token, allowed hosts, the four network settings as one block, TLS and the refusal without TLS, CA trust, certificate renewal, token change, Grafana admin password) and of FR-026 (what reaches the AI model provider, the streams of `log-audit.md` under FR-022a), with the `writing-infrahub-docs` skill (depends on T024, T057)
- [ ] T059 [P] Link the skill from `docs/docs/overview/build-with-ai/index.mdx` ("Where to start" table and MCP table), `docs/docs/overview/build-with-ai/setup.mdx` (prerequisites), `docs/docs/overview/build-with-ai/working-with-ai.mdx` and `docs/docs/faq/faq.mdx` (FR-027); merge only when the skill is published (depends on T037)
- [ ] T060 Run `uv run invoke format`, `uv run invoke lint`, `uv run ruff check . --exclude python_sdk`, `uv run ruff format --check --exclude python_sdk .`, `uv run invoke docs.lint` and `uv run invoke docs.validate`, then remind Daniel to run `/pre-ci`
- [ ] T061 Grep `dev/specs/infp-745-ai-diagnose-slowness/` for each value that implementation decided or changed (restart policy, TLS mount, init image, probe scheme, eval pass rate) and update every file that repeats it
- [ ] T062 Run [quickstart.md](quickstart.md) check 10 (automated checks) in `opsmill/infrahub` and `infrahub-skills`
- [ ] T063 Hand the finished container to Fatih Acar for the security review, and record the result in "Conditions for the 1.13 release" of `dev/specs/infp-745-ai-diagnose-slowness/spec.md` (depends on T004, T024)

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: starts at once. T005 needs T001. The other approvals do not block code, but
  they are release conditions or block a merge (research R10).
- **Foundational (Phase 2)**: no task.
- **User Story 1 (Phase 3)**: starts after T005 for the Compose service (T013). The checks, tests and
  scripts (T006 to T012) can start at once.
- **User Story 2 (Phase 4)**: the fixtures (T025) need the Compose services of story 1 (T015). The
  rules (T029 to T034) and the `opsmill/infrahub` rule and knowledge tasks (T038, T039) can start at
  once.
- **User Story 3 (Phase 5)**: independent of stories 1 and 2, except T043, which reads the Grafana MCP
  server's own logs (T015). The log fixes (T046 to T052) can start at once.
- **Polish (Phase 6)**: T058 needs stories 1 and 3; T059 needs the published skill.

### Order of the pull requests (plan, "Structure Decision")

1. `opsmill/infrahub`: Compose services and log fixes (stories 1 and 3). The docs pages (T058, T059)
   go in a later pull request, merged only when the skill is published.
2. `opsmill/infrahub-helm`: T017 to T023, T055.
3. `opsmill/infrahub-skills`: T025 to T037.

### Within each story

- Tests before the implementation they check, and they fail first.
- In story 1: the checks on a running stack (T006, T007, T017) before the service or template they
  decide.
- In story 2: rule = test; a rule, its grader and its four fixtures land in the same change.

### Parallel opportunities

- T002, T003, T004 in Phase 1.
- T008, T009, T010, T011, T012 in story 1 (different files).
- T018, T019, T021 in Helm once T017 is done.
- T029 to T034 (one rule file each), and T036, T038, T039 in story 2.
- T043, T044, T045, and T046 to T052, in story 3.
- Story 3 can run beside story 1 from the start.

---

## Parallel Example: User Story 1

```text
Task: "Extend backend/tests/unit/test_observability_compose.py (T008)"
Task: "Create backend/tests/unit/test_grafana_mcp_entrypoint.py (T009)"
Task: "Create backend/tests/component/test_grafana_mcp_service_account.py (T010)"
Task: "Create development/grafana-mcp/entrypoint.sh (T011)"
Task: "Create development/grafana-mcp/create-service-account.sh (T012)"
```

## Parallel Example: User Story 2

```text
Task: "Write rules/check-version-first.md (T029)"
Task: "Write rules/check-datasources-first.md (T030)"
Task: "Write rules/follow-check-order.md (T031)"
Task: "Write rules/report-evidence-per-finding.md (T032)"
Task: "Write rules/describe-missing-panel.md (T033)"
Task: "Write rules/no-generic-query-help.md (T034)"
```

## Parallel Example: User Story 3

```text
Task: "Test the webhook log formatter (T046)"
Task: "Test the HTTP adapter (T047)"
Task: "Test the Google group lookup (T048)"
Task: "Check the span masking test (T049)"
```

---

## Implementation Strategy

### First increment (User Story 1)

1. Phase 1: ask the approvals, choose the init image.
2. Phase 3: Compose first (T006 to T016), then Helm (T017 to T023).
3. Validate with quickstart checks 1 to 6 (T024). An operator can then connect any AI assistant to the
   stack's Grafana, without the skill.

### Incremental delivery

1. Story 1: the Grafana MCP server, connected with one URL and one token.
2. Story 3, in parallel: the audit and the log fixes. It is a release condition, so 1.13 does not ship
   the server without it.
3. Story 2: the skill, once fixtures can be recorded from story 1.
4. Polish: docs, checks, security review.

The 1.13 release needs all four conditions of the spec: the audit (story 3), the agreement of the
`infrahub-skills` owners (T002), the security review (T063), and the creation of the service account
at installation (T012, T022).

Story 4 (build and contribute a dashboard) is not in 1.13. Its tasks are written when that release is
planned: the dashboard, folder and annotation write tools with the Editor role, a new security review,
and the rule `ask-before-contributing`.

---

## Notes

- [P] tasks touch different files and depend on no unfinished task.
- Commit after each task or group of tasks.
- Stop at each checkpoint and validate the story on its own.
