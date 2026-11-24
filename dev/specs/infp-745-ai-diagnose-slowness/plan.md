# Implementation Plan: Find the Slow Component of an Infrahub Instance with an AI Assistant

**Branch**: `dp-20261104-ai-diagnose-slowness-infp-745` | **Date**: 2026-11-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/infp-745-ai-diagnose-slowness/spec.md`

## Summary

An operator asks their AI assistant why an Infrahub instance is slow, and gets a report that names
the slow component with its evidence (Jira [INFP-745](https://opsmill.atlassian.net/browse/INFP-745),
phase 7 of the design document). The work has three parts, in three repositories:

- **The Grafana MCP server in the stack.** Two services in a Compose profile, `grafana-mcp`, off by
  default: the server itself, and a one-time container that creates its Grafana service account and
  token. The same in the `infrahub-observability` Helm chart, with a hook Job. The server refuses to
  start without the token that AI assistants send, sends no usage statistics, and keeps no write tool
  in 1.13 ([research.md](research.md) R1 to R5). Building dashboards (story 4) comes in a later
  release.
- **The skill** `infrahub-diagnosing-performance` in `opsmill/infrahub-skills`: version check, data
  source check, durations, component, trace, logs, report with evidence, and a description of the
  missing panel when the dashboards do not answer (FR-017a). Each rule has
  a grader and four fixtures (R6, R7).
- **The audit and its fixes** in this repository (phase 1, FR-022, FR-022a): finish the audit of
  Infrahub's own log lines that the first pass started (R8), and fix each confirmed line where it is
  written; audit every other log stream in Loki, the metric labels in Prometheus, the resource
  attributes of traces and the server's own logs; drop or document the values found in streams that
  Infrahub does not write; record the result in `log-audit.md`.

Docs: a section in `observability-stack.mdx`, the Build with AI pages and the FAQ.

## Technical Context

**Language/Version**: YAML (Compose, Helm templates), POSIX `sh` (entrypoint check and init script),
Python 3.14 (backend log fixes, the standalone converter and its unit tests), Markdown (skill, docs).

**Primary Dependencies**: `grafana/mcp-grafana:2.0.2` (new image); Grafana 11.4.0 (Compose) and
11.1.5 (Helm, chart `grafana` 8.5.0), unchanged. The init script uses the Grafana image of the stack
(R5), so it adds no new image. The design document chose the `mcp-grafana` container (D10, status
"Approved"), so no image needs the engineering approval for new dependencies (R10).
The new image is pinned by tag and by digest, because a tag can be moved.

**Storage**: A named Compose volume and a Kubernetes Secret for the Grafana service account token. No
database change.

**Testing**:

- `backend/tests/unit/test_observability_compose.py`: the two services, the profile, the variables and
  the standalone file. Also:
  - the standalone file loads with the profile on and no TLS setting (the optional TLS mount does not
    break the start);
  - the entrypoint with no TLS setting, with both, and with one only;
  - the entrypoint with a non-loopback listen address and no TLS setting, which exits with code 1.
- Backend unit tests for each log fix (`backend/tests/unit/`).
- A component test with testcontainers that starts Grafana 11.1.5 and 11.4.0, runs the service
  account script twice, and checks that one token exists and still works (`backend/tests/component/`).
- `helm template` and `helm lint` tests in `infrahub-helm`, as that repository runs them.
- `skillgrade` evals with four fixtures per rule in `infrahub-skills`. Before the fixtures are
  committed to that public repository, they are reviewed for host names, account names, tokens and
  other values from the recording stack.
- The manual checks in [quickstart.md](quickstart.md) on a Compose stack and a kind cluster.

**Target Platform**: Docker Compose and Kubernetes (Helm). AI assistants on the user's computer that
speak MCP over Streamable HTTP, such as Claude Code.

**Project Type**: Shipped deployment configuration, a backend change to log lines, and a skill.

**Performance Goals**: None set by the spec. The server adds no work to Infrahub; it reads Grafana.

**Constraints**:

- With the profile off, no new container is created (FR-001).
- The server listens on `127.0.0.1` by default (Compose) or on a `ClusterIP` Service (Helm). One
  setting opens it to a network (FR-006), and the server serves HTTPS when it gets a certificate and a
  key (FR-006a). In Compose, the server does not start on a non-loopback address without TLS; in
  Helm, the chart refuses a `LoadBalancer` or `NodePort` Service without TLS.
- No new outbound connection from the operator's network (FR-008).
- The skill finds data sources by type, never by UID (FR-013).

**Scale/Scope**: In this repository: 2 Compose services, 1 converter change, about 6 backend files for
log fixes, 4 docs pages, 1 `AGENTS.md` rule. In `infrahub-helm`: about 6 templates and the values. In
`infrahub-skills`: 1 skill with 6 rules, their graders and 24 fixtures.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Schema-Driven Integrity | Pass | No schema change. The standalone Compose file is regenerated with `convert_compose_standalone.py`, never edited. |
| II. Branch-Safe by Default | Pass | No database query. The server reads Grafana, not Infrahub. |
| III. Type Safety & Explicit Contracts | Pass | Log fixes keep type hints. The settings, values and report format are in [contracts/](contracts/) before implementation. |
| IV. Test Discipline | Pass with one exception | Unit tests for the Compose files and the log fixes; evals for the skill. No pytest-playwright test: the feature has no web interface page. See Complexity Tracking. |
| V. Query Performance & Efficiency | Pass | No Cypher query. |
| VI. Security & Input Boundaries | Pass, pending one approval | The server requires a token with no default (FR-003 to FR-005); in 1.13 no write tool is kept, with a Viewer service account (FR-010, R4); no usage statistics. The new image is chosen by D10 of the approved design document. The container needs a security review (R10), which is not done yet and is a release condition in the spec. |
| VII. Simplicity & Maintainability | Pass | Reuses the Compose profile and one-time container patterns of the stack, and the hook Job pattern of `infrahub-helm`. No new backend abstraction: each log line is fixed where it is written. |
| Ask First (root `AGENTS.md`) | Pass | New dependency: `grafana/mcp-grafana`, chosen by D10 of the approved design document. The init script uses the Grafana image of the stack (R5), so it adds no new image and needs no approval. |

Re-check after Phase 1 design: no change. The contracts add no API to Infrahub.

## Project Structure

### Documentation (this feature)

```text
specs/infp-745-ai-diagnose-slowness/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── compose-settings.md
│   ├── helm-values.md
│   └── diagnosis-report.md
├── log-audit.md         # Written by the log audit task (FR-022)
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code

This repository (`opsmill/infrahub`):

```text
development/
├── docker-compose-observability.yml             # New services infrahub-grafana-mcp and infrahub-grafana-mcp-init, profile grafana-mcp, volume grafana_mcp_token (FR-001 to FR-009)
├── grafana-mcp/
│   ├── entrypoint.sh                            # New: token check, then exec mcp-grafana (FR-004)
│   └── create-service-account.sh                # New: init script, shared with the Helm chart (FR-009)
├── alloy/config.alloy                           # drop rules for third-party log lines, if the audit needs them (FR-022a)
├── convert_compose_standalone.py                # Keeps the profiles key of the grafana-mcp services (R1)
├── docker-compose-observability-standalone.yml  # Regenerated
└── grafana/AGENTS.md                            # Rule: a rename updates the skill (FR-020)

backend/infrahub/
├── webhook/log_formatter.py                     # URL without query string (R8)
├── services/adapters/http/httpx.py              # URL without query string in logs and exceptions (R8)
├── auth/auth.py                                 # Email as a request parameter; possible fixes after the runtime check (R8)
└── git/ ...                                     # Credentials removed from the location, if the runtime check confirms it (R8)

backend/tests/unit/
├── test_observability_compose.py                # Profile, variables, entrypoint, standalone file
└── ...                                          # One test per log fix, next to the module it tests

backend/tests/component/
└── test_grafana_mcp_service_account.py          # Init script on Grafana 11.1.5 and 11.4.0, run twice

docs/docs/
├── deploy-manage/install-configure/install/observability-stack.mdx   # Connect an AI assistant (FR-025, FR-026)
├── overview/build-with-ai/{index,setup,working-with-ai}.mdx          # Links to the skill (FR-027)
└── faq/faq.mdx                                                       # Entry for the skill (FR-027)

dev/knowledge/backend/observability.md            # Renaming section: the skill depends on names (FR-020)
changelog/                                        # Fragments: the new services (added), the log fixes (security)
```

`opsmill/infrahub-helm`, chart `charts/infrahub-observability/`:

```text
values.yaml                                  # grafanaMcp.* (see contracts/helm-values.md)
templates/grafana-mcp-deployment.yaml        # Deployment, required token, file-mounted Grafana token
templates/grafana-mcp-service.yaml
templates/grafana-mcp-secret.yaml            # Only when the token is given as a value
templates/grafana-mcp-sa-job.yaml            # post-install,post-upgrade hook Job, ServiceAccount, Role, RoleBinding
files/grafana-mcp/create-service-account.sh  # Copied from this repository, as files/datasources.yaml is
```

`opsmill/infrahub-skills`:

```text
skills/infrahub-diagnosing-performance/
├── SKILL.md, examples.md, reference.md
└── rules/                                    # The six rules of research.md R6
graders/infrahub-diagnosing-performance/      # lib.py, check_*.py
tests/graders/                                # Grader tests
eval.yaml, evaluations/*.json                 # Eval tasks and their regenerated JSON
skills/infrahub-analyzing-diagnostics/SKILL.md   # DO NOT TRIGGER: the new skill (FR-019)
```

**Structure Decision**: Three repositories, one pull request each, in this order: this repository
(Compose, log fixes, docs), then `infrahub-helm`, then `infrahub-skills`. The skill's fixtures are
recorded from the Compose stack, so the Compose change comes first. The docs link to the skill, so the
docs pull request is merged only when the skill is published.

## Phases of the work

1. **Audit and fixes** (this repository). Release condition.
   - Finish the audit of Infrahub's own log lines from R8, including the runtime checks, and fix each
     confirmed line where it is written.
   - Audit every other log stream in Loki, by container, the metric labels in Prometheus, the
     resource attributes of traces and the Grafana MCP server's own logs (FR-022).
   - For each value found in a stream that Infrahub does not write: an Alloy `drop` rule in
     `development/alloy/config.alloy` and in the Helm chart's Alloy, or an entry in the docs
     (FR-022a).
   - Record everything in `log-audit.md`.
2. **Compose services.** First task, on a running stack, recorded in
   [contracts/compose-settings.md](contracts/compose-settings.md):
   - check how the two restart options behave after a missing token and after a Docker restart;
   - choose how to mount the TLS files only when they are set, and check that the stack starts with
     the profile on and no TLS setting.

   Then: profile, entrypoint check,
   init container, Grafana admin variables, converter, tests, standalone file.
3. **Helm chart** (`infrahub-helm`). First task: start the image in kind with the probe settings of
   [contracts/helm-values.md](contracts/helm-values.md) and confirm that the probes pass. Then the
   templates.
4. **Skill** (`infrahub-skills`). Fixtures recorded from phase 2.
5. **Docs and rules.** `observability-stack.mdx`, Build with AI pages, FAQ, `development/grafana/AGENTS.md`,
   `observability.md`.

Phases 1 and 2 can run in parallel. Phase 4 needs phase 2.

## Decisions made during planning

- **Write tools** (R4): in 1.13, no write tool, with a Viewer service account, instead of all write
  tools as D10 says. Story 4 (building dashboards) moves to a later release, which keeps only the
  dashboard, folder and annotation write tools with an Editor service account. Decided by Daniel on
  2026-11-04; FR-010, FR-017, FR-017a, FR-018 and SC-006 of the spec were changed to match.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| No pytest-playwright E2E test (Principle IV) | The feature has no page in the Infrahub web interface. Its user interface is an AI assistant and Grafana. | An E2E test of the web interface would test nothing that this feature changes. The quickstart checks and the skill evals cover the user flow. |
| A shell entrypoint around `mcp-grafana` | `mcp-grafana` 2.0.2 starts without authentication when no token is set (R2). | Compose `${VAR:?}` breaks every stack that does not use the server; waiting for the upstream change has no date. |
