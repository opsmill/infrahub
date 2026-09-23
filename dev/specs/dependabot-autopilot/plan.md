# Implementation Plan: Dependency-bump autopilot

**Branch**: `dependabot-autopilot` | **Date**: 2026-09-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `dev/specs/dependabot-autopilot/spec.md`

## Summary

Run the existing dependency-bump analysis automatically on every Dependabot PR and act on its verdict. An agentic workflow analyses the PR with read-only rights and emits a structured verdict artifact. A deterministic workflow, running in the trusted `workflow_run` context under a dedicated GitHub App, recomputes the effective verdict (strictest per package, fail closed, new lockfile packages capped), checks that every CI signal on the head commit is green, posts the report, and approves and squash-merges pinned to the analysed commit. The same package files deduplicated Jira tech-debt items and posts a weekly #release-radar digest. Merges ship disabled (shadow mode) behind a repository variable. See [research.md](research.md) R1–R14.

## Technical Context

**Language/Version**: Python 3.14 (runner-provided through `uv`), GitHub Actions YAML, gh-aw Markdown workflow compiled with the repository's pinned compiler (v0.81.x)

**Primary Dependencies**: Python stdlib and PyYAML (`>=6,<7`, same range as the root `pyproject.toml`); `gh` CLI on runners; `actions/create-github-app-token` for the App token; gh-aw with `engine: claude`

**Storage**: None. State lives on GitHub (labels, one marker comment, reviews), in a 7-day workflow artifact, and in Jira issues

**Testing**: pytest unit tests for the decision logic with in-memory fakes behind protocols; `actionlint`, `zizmor` (existing `.github/zizmor.yml`), `gh aw compile` drift check; live validation per [quickstart.md](quickstart.md)

**Target Platform**: GitHub-hosted `ubuntu-latest` runners

**Project Type**: CI automation (workflows plus a small Python package), no product code

**Performance Goals**: Act job completes in under 60 seconds; analysis in under 20 minutes (timeout); merge follows the last green check within one event or at most 30 minutes (sweep)

**Constraints**: No PR code checked out or executed in any job holding write credentials; no Actions secret copied into Dependabot secrets except `ANTHROPIC_API_KEY`; no change to `stable` branch rules

**Scale/Scope**: About 4 Dependabot PRs a week (48 in 90 days: 26 GitHub Actions, 14 npm, 8 uv)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Applies | Status |
|---|---|---|
| I. Schema-Driven Integrity | No product data touched | Pass (N/A) |
| II. Branch-Safe by Default | No database queries | Pass (N/A) |
| III. Type Safety & Explicit Contracts | Act package fully typed; frozen dataclasses for Report/Decision; verdict contract defined before implementation ([contracts/verdict.schema.json](contracts/verdict.schema.json)) | Pass |
| IV. Test Discipline | Unit tests for every decision rule; I/O behind protocols with fakes rather than mocks; no product feature, so no E2E test; live validation in quickstart | Pass |
| V. Query Performance | No database | Pass (N/A) |
| VI. Security & Input Boundaries | Agent output treated as untrusted input and validated; write credentials only in `workflow_run`; no PR code executed; new lockfile packages never auto-merge; no secrets committed | Pass |
| VII. Simplicity & Maintainability | Reuses the vendored skill and gh-aw; stdlib plus an existing dependency; no new service. Three workflows are the minimum for three triggers with different trust levels | Pass |
| Security Requirements: dependency additions require review | Enforced deterministically (research R7) | Pass |
| Code Quality Gates before merge | Enforced by the CI evaluation (research R5) because `stable` has no required checks | Pass |

**Governance gates (AGENTS.md "Ask First")**: CI/CD workflow changes, **crossed** (three new workflows, one CI job, label additions); Authentication/authorization changes, **crossed** (new GitHub App with write access, Jira/Slack credentials). Both need explicit sign-off before implementation. No database, GraphQL or dependency gate is crossed.

**Post-design re-check**: unchanged; the design introduced no violation. Complexity Tracking stays empty.

## Project Structure

### Documentation (this feature)

```text
dev/specs/dependabot-autopilot/
├── spec.md
├── plan.md              # this file
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── verdict.schema.json
│   └── workflows.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks output
```

### Source Code (repository root)

```text
.agents/skills/analyzing-dependency-bumps/SKILL.md     # vendored from opsmill/opsmill-skills
skills-lock.json                                       # + analyzing-dependency-bumps entry

.github/workflows/
├── dependabot-autopilot-analyze.md                    # gh-aw source (untrusted, read-only)
├── dependabot-autopilot-analyze.lock.yml              # compiled, committed
├── dependabot-autopilot-act.yml                       # deterministic, App token
├── dependabot-autopilot-digest.yml                    # weekly Slack digest
└── ci.yml                                             # + dependabot-autopilot-tests job (file-filtered)
.github/file-filters.yml                               # + dependabot_autopilot_files filter
.github/labels.yml                                     # + autopilot/* labels

.github/scripts/dependabot_autopilot/
├── __init__.py
├── __main__.py        # CLI: invalidate | evaluate | sweep | file-opportunities | digest
├── report.py          # parse + validate verdict.json into frozen dataclasses (stdlib validation of the schema)
├── decision.py        # effective verdict, strictness order, downgrade reasons, action selection
├── checks.py          # classify workflow runs / check runs / statuses into green|pending|red
├── lockfiles.py       # package-set extraction for uv.lock, pnpm-lock.yaml, package-lock.json
├── codeowners.py      # CODEOWNERS matching (last rule wins) + fallback
├── opportunities.py   # dedup key, dbap label, rubric priority, Jira payloads
├── digest.py          # digest message rendering
├── ports.py           # GitHubPort, JiraPort, SlackPort protocols
├── adapters.py        # gh CLI / urllib implementations of the ports
└── tests/
    ├── fakes.py
    ├── test_report.py
    ├── test_decision.py
    ├── test_checks.py
    ├── test_lockfiles.py
    ├── test_codeowners.py
    ├── test_opportunities.py
    ├── test_digest.py
    └── test_evaluate_flow.py   # end-to-end evaluate/invalidate against fakes

dev/guides/dependabot-autopilot.md                     # operating guide: switches, labels, rollback
```

**Structure Decision**: Deterministic code sits under `.github/scripts/` next to the workflows that run it, outside `backend/` and `tasks/` so it ships with no Infrahub dependency and is not imported by invoke. Whole-repo `ruff check .` and `ty check .` in `ci.yml::python-lint` already cover it; a new file-filtered CI job runs its tests.

## Design notes

- **Analysis workflow prompt** instructs the agent to apply `analyzing-dependency-bumps` to the PR, then call `emit_verdict` once with JSON matching the schema; it states that the report posting and every action are performed elsewhere, and that any doubt must yield `review-required`. The skill file itself is not modified.
- **Validation without `jsonschema`**: `report.py` validates the contract by hand while building dataclasses; any violation yields `ReportError`, which `decision.py` maps to `review-required` with the reason "malformed report".
- **Artifact lookup**: on `workflow_run` of the analysis, the act job downloads `dependabot-autopilot-verdict` from that run; on `CI` completion or sweep it takes the most recent successful analysis run for the head SHA via the Actions API. No artifact → `review-required` only once the analysis run for that SHA has completed; while it is still running, the Decision is `pending`.
- **Merge**: `gh pr review --approve` then `gh pr merge --squash --match-head-commit <sha>`; failure of the merge call (head moved, conflict) is logged on the comment and left for the next event.
- **Owner notification**: review requests to CODEOWNERS teams for changed files, else `DEPENDABOT_AUTOPILOT_FALLBACK_REVIEWER`; sent once per head SHA.
- **Reports are not trusted for SHA**: `head_sha` in the artifact must match both the triggering run and the live PR head, otherwise the report is stale.

## Rollout

1. Merge with `DEPENDABOT_AUTOPILOT_MERGE=off` (shadow). Run quickstart Q1 in a sandbox before anything else.
2. Two weeks of shadow verdicts; compare against human decisions on the same PRs.
3. Switch `DEPENDABOT_AUTOPILOT_MERGE=on`; track SC-001..SC-004 from PR and Jira history.

The workflows must be on `stable` (the default branch) for `workflow_run` and `schedule` triggers to fire, so the feature branch targets `stable`.

## Complexity Tracking

No violations.
