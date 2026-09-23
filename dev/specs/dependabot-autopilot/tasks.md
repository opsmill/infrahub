---

description: "Task list for the dependency-bump autopilot"
---

# Tasks: Dependency-bump autopilot

**Input**: Design documents from `dev/specs/dependabot-autopilot/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included; every decision rule gets a unit test written before its implementation.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated on its own.

**Governance**: This feature crosses the AGENTS.md "Ask First" gates for CI/CD workflow changes and authentication/authorization changes (plan.md, Constitution Check). Get explicit sign-off before T024 (the first workflow able to write) is merged, and before the GitHub App is created (T039).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 (verdict and merge), US2 (tech-debt items), US3 (digest)
- Package root: `.github/scripts/dependabot_autopilot/` (abbreviated `PKG/` below); tests in `PKG/tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: De-risk the gh-aw dependency, vendor the skill, scaffold the package and its CI job.

- [X] T001 Spike on the pinned gh-aw compiler (the version in `.github/workflows/bug-agent-review.lock.yml`'s header): compile a throwaway workflow using `on.bots: ["dependabot[bot]"]` and a `safe-outputs.jobs` custom job with one string input; do not commit the throwaway. Record the outcome in `dev/specs/dependabot-autopilot/research.md` under R1 (supported, or fallback per plan.md "gh-aw feature spike first")
- [X] T002 [P] Vendor the `analyzing-dependency-bumps` skill from `opsmill/opsmill-skills` (`opsmill-dev/skills/analyzing-dependency-bumps/SKILL.md`) into `.agents/skills/analyzing-dependency-bumps/SKILL.md` and add its entry, with `computedHash`, to `skills-lock.json` in the same shape as the `grilling-ideas` entry
- [X] T003 [P] Create the package skeleton: `PKG/__init__.py`, `PKG/__main__.py` (argparse with subcommands `invalidate`, `evaluate`, `sweep`, `file-opportunities`, `digest`, each exiting 0 with "not implemented"), `PKG/tests/__init__.py`, and `PKG/tests/conftest.py` that puts `.github/scripts` on `sys.path`
- [X] T004 [P] Add labels `autopilot/safe`, `autopilot/needs-code-changes`, `autopilot/review-required`, `autopilot/hold` with descriptions from `data-model.md` to `.github/labels.yml`
- [X] T005 Add a `dependabot_autopilot_files` filter (`.github/scripts/dependabot_autopilot/**`, `.github/workflows/dependabot-autopilot-*`) to `.github/file-filters.yml` and a `dependabot-autopilot-tests` job to `.github/workflows/ci.yml` gated on it, running `uv run pytest .github/scripts/dependabot_autopilot/tests`

**Checkpoint**: `uv run pytest .github/scripts/dependabot_autopilot/tests` collects zero tests without error; `uv run ruff check .github/scripts` and `uv run ty check .github/scripts` pass.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The verdict contract, the I/O ports and the GitHub adapter that every story uses.

- [X] T006 Define `PKG/ports.py`: frozen dataclasses for `PullRequest`, `Review`, `WorkflowRun`, `CheckRun`, `CommitStatus`, `ChangedFile`, and `Protocol`s `GitHubPort` (read PR, list reviews, list workflow runs / check runs / statuses for a SHA, read file at ref, list changed files, upsert marker comment, set labels, submit/dismiss review, request reviewers, merge with head-SHA match, download artifact of a run), `JiraPort` (search by label, create issue, add comment), `SlackPort` (post message)
- [X] T007 Write in-memory fakes of the three ports in `PKG/tests/fakes.py`, recording every write call for assertions
- [X] T008 [P] Write `PKG/tests/test_report.py`: a valid report parses; each schema rule in `contracts/verdict.schema.json` rejected (wrong `schema_version`, bad `head_sha`, unknown verdict, empty `packages`, `needs-code-changes` package without impacts, bad opportunity `key`, `report_markdown` over 60,000 chars, file over 256 KB); `sanitize_report_markdown` neutralizes `@user` / `@org/team`, strips every HTML comment including a forged `<!-- dependabot-autopilot -->`, and wraps the text in a `<details>` block labelled as agent output
- [X] T009 Implement `PKG/report.py`: frozen dataclasses `VerdictReport`, `PackageFinding`, `Impact`, `Opportunity`; `load_report(path)` reading only `verdict.json` from a given directory with the 256 KB limit and hand-written validation raising `ReportError`; `sanitize_report_markdown(text)` (makes T008 pass)
- [X] T010 [P] Record real API JSON fixtures in `PKG/tests/fixtures/` (reviews, `actions/runs?head_sha=`, `check-runs`, combined `status`, PR files) from a recent Dependabot PR such as #10689, with tokens and personal data removed
- [X] T011 Write `PKG/tests/test_adapters.py` asserting the `gh`-CLI GitHub adapter parses each fixture into the `ports.py` dataclasses (status/conclusion values, `commit_id` on reviews, reviewer login, app slug on check runs), with the subprocess runner injected
- [X] T012 Implement the GitHub adapter `GhCliGitHub` in `PKG/adapters.py` over an injectable `gh api` runner, including pagination and `gh pr merge --squash --match-head-commit` (makes T011 pass)

**Checkpoint**: report parsing, sanitization and adapter parsing are green; no story work has started.

---

## Phase 3: User Story 1 - Verdict and automatic merge (Priority: P1) 🎯 MVP

**Goal**: Every Dependabot PR gets an analysed verdict on its head commit; `safe` plus green CI merges, `needs code changes` blocks, `review required` escalates (FR-001..FR-010, FR-015..FR-019, FR-021).

**Independent Test**: quickstart.md Q2–Q7 (shadow mode, stale approval, pending then green, red CI, new package, human hold).

### Tests for User Story 1

- [X] T013 [P] [US1] Write `PKG/tests/test_checks.py`: `evaluate_ci(runs, check_runs, statuses, own_workflows)` returns `green` only when everything is completed with `success`/`skipped`/`neutral`; `pending` on any queued/in-progress run, pending status, or no CI run at all; `red` on `failure`/`cancelled`/`timed_out`/`action_required`/`stale`; the autopilot's own workflow runs and `github-actions` check runs are excluded
- [X] T014 [P] [US1] Write `PKG/tests/test_lockfiles.py` with small `uv.lock`, `pnpm-lock.yaml` (v9 `packages:` keys with and without scopes) and `package-lock.json` (`node_modules/…` keys) fixture pairs: `added_packages(path, base_text, head_text)` returns only names new at head; version-only changes return nothing; unknown lockfile paths are ignored
- [X] T015 [P] [US1] Write `PKG/tests/test_codeowners.py` against a copy of `.github/CODEOWNERS`: `uv.lock` → `@opsmill/backend`; `.github/workflows/ci.yml` → no owner → fallback; last matching rule wins; comment and blank lines ignored
- [X] T016 [P] [US1] Write `PKG/tests/test_decision.py`: strictness order across packages and overall verdict; missing, malformed and stale (`head_sha` ≠ PR head) reports → `review-required` with reason; analysis still running → pending; no analysis run 60 minutes after head push → `review-required` "analysis did not run"; added lockfile package → `review-required` naming the package; CI red → `review-required`; `safe` + green + merge switch `on` + no hold + no human `CHANGES_REQUESTED` → action `approve-and-merge`; switch `off` → `label-only`; `autopilot/hold` or a human change request → no approve/merge; closed or merged PR → no action
- [X] T017 [US1] Write `PKG/tests/test_evaluate_flow.py` driving `evaluate` and `invalidate` through the fakes: one marker comment edited in place across runs; exactly one `autopilot/*` verdict label; `REQUEST_CHANGES` review listing each impact as `path:line` for `needs-code-changes`; reviewer requests sent once per head SHA to owners or the fallback; approve then merge with the analysed SHA; running `evaluate` twice on the same head produces no extra writes; `invalidate` dismisses only App approvals whose `commit_id` ≠ head; a PR not authored by `dependabot[bot]` or not based on `stable` gets no writes

### Implementation for User Story 1

- [X] T018 [P] [US1] Implement `PKG/checks.py` (`CiState`, `evaluate_ci`) (makes T013 pass)
- [X] T019 [P] [US1] Implement `PKG/lockfiles.py` (`added_packages` for the three formats, PyYAML for pnpm) (makes T014 pass)
- [X] T020 [P] [US1] Implement `PKG/codeowners.py` (`owners_for(paths, codeowners_text)` with GitHub glob semantics, last rule wins) (makes T015 pass)
- [X] T021 [US1] Implement `PKG/decision.py` (`Verdict` enum with strictness order, `Decision` frozen dataclass with `effective_verdict`, `reasons`, `ci_state`, `action`; `decide(...)` pure function) (makes T016 pass)
- [X] T022 [US1] Implement the `evaluate`, `invalidate` and `sweep` subcommands in `PKG/__main__.py`: resolve the PR and its verdict artifact (from the triggering run, or the latest analysis run for the head SHA), compute changed lockfiles' added packages via `read file at ref` for base and head, call `decide`, then apply comment/labels/review/reviewer requests/approve/merge; configuration from environment variables named in `data-model.md` Configuration (makes T017 pass)
- [X] T023 [US1] Write `.github/workflows/dependabot-autopilot-analyze.md` per `contracts/workflows.md` (trigger, `bots`, read-only permissions, `ANTHROPIC_API_KEY`, network ecosystems, 20-minute timeout, `emit_verdict` custom safe-output job uploading `dependabot-autopilot-verdict`, or the T001 fallback); the prompt applies the vendored skill, requires exactly one `emit_verdict` call conforming to `contracts/verdict.schema.json`, and requires `review-required` whenever evidence is missing. Compile with the pinned compiler and commit `.github/workflows/dependabot-autopilot-analyze.lock.yml`
- [X] T024 [US1] Write `.github/workflows/dependabot-autopilot-act.yml` per `contracts/workflows.md`: triggers (`workflow_run` requested/completed of the analysis, completed of `CI`, 30-minute schedule, `workflow_dispatch` with `pr_number`), job-level actor filter for `workflow_run`, concurrency `dependabot-autopilot-<pr>`, `GITHUB_TOKEN` `contents: read` + `actions: read`, App token via `actions/create-github-app-token` pinned by SHA, artifact download into `${{ runner.temp }}/verdict-<run_id>`, `uv run --no-project --with "pyyaml>=6,<7" python -m dependabot_autopilot …` from `.github/scripts`, `invalidate` on `requested`, `evaluate` otherwise, `sweep` on schedule, and an `if: failure()` step escalating the PR
- [X] T025 [US1] Add `cooldown: default-days: 3` to the `github-actions` entry of `.github/dependabot.yml` after confirming the option is valid for that ecosystem; if it is not, record it in research.md R15 and add the release-age cap to `PKG/decision.py` with a test in `PKG/tests/test_decision.py`
- [X] T026 [US1] Run `actionlint` and `zizmor` (with `.github/zizmor.yml`) on the two new workflows and fix every finding

**Checkpoint**: US1 is complete in shadow mode (`DEPENDABOT_AUTOPILOT_MERGE=off`): verdicts, labels, reviews and escalations work; merges wait for the switch.

---

## Phase 4: User Story 2 - Tech-debt items from opportunities (Priority: P2)

**Goal**: Opportunities become deduplicated Jira items with rubric priority; a Jira outage never affects the PR (FR-011..FR-013, FR-020).

**Independent Test**: quickstart.md Q8 (same artifact filed twice → one issue, one comment).

### Tests for User Story 2

- [X] T027 [P] [US2] Write `PKG/tests/test_opportunities.py`: `dedup_label(key)` equals `dbap-` + first 12 hex of sha256; rubric (`security`/`deprecation-deadline` → High, `performance`/`simplification` with ≥ 1 code ref → Medium, same without code refs → Low, `other` → Low); issue payload has summary `[<package>] <title>`, labels `tech-debt`, `dependabot-autopilot`, the dedup label, no assignee, PR link and code refs in the description; `file_opportunities` creates on no match, comments on match, skips every opportunity when the effective verdict is `needs-code-changes`, and reports Jira errors without raising
- [X] T028 [P] [US2] Extend `PKG/tests/test_adapters.py` with recorded Jira fixtures (`/rest/api/3/search/jql` response, create response) for the Jira adapter

### Implementation for User Story 2

- [X] T029 [US2] Implement `PKG/opportunities.py` (`dedup_label`, `priority_for`, `issue_payload` with an ADF description, `file_opportunities`) (makes T027 pass)
- [X] T030 [US2] Implement the Jira adapter `JiraRest` in `PKG/adapters.py` (basic auth, `search/jql` with `labels = "<dbap>" AND statusCategory != Done`, create, comment) (makes T028 pass)
- [X] T031 [US2] Implement the `file-opportunities` subcommand in `PKG/__main__.py` and add a separate `file-opportunities` job with `continue-on-error: true` after the evaluate job in `.github/workflows/dependabot-autopilot-act.yml`, using `JIRA_*` secrets and `DEPENDABOT_AUTOPILOT_JIRA_*` variables

**Checkpoint**: US2 works independently of the merge switch; a Jira failure leaves the PR's verdict and labels unchanged.

---

## Phase 5: User Story 3 - Weekly #release-radar digest (Priority: P3)

**Goal**: One weekly message listing High and Medium items updated in the last 7 days; nothing in an empty week (FR-014).

**Independent Test**: quickstart.md Q9.

- [X] T032 [P] [US3] Write `PKG/tests/test_digest.py`: `render_digest(items)` lists High before Medium with links, returns `None` for an empty list; the digest command posts once when there are items and never when there are none
- [X] T033 [US3] Implement `PKG/digest.py`, the `SlackWebhook` adapter in `PKG/adapters.py`, and the `digest` subcommand in `PKG/__main__.py` querying `labels = dependabot-autopilot AND priority in (High, Medium) AND updated >= -7d` (makes T032 pass)
- [X] T034 [US3] Write `.github/workflows/dependabot-autopilot-digest.yml` (Monday 09:30 UTC schedule, `workflow_dispatch`, `JIRA_*` and `SLACK_RELEASE_RADAR_WEBHOOK_URL` secrets, read-only `GITHUB_TOKEN`) and run `actionlint` and `zizmor` on it

**Checkpoint**: all three stories are implemented.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T035 [P] Write `dev/guides/dependabot-autopilot.md`: what the autopilot does, labels, the merge switch and `autopilot/hold`, rollback, required secrets (including that `ANTHROPIC_API_KEY` must be a Dependabot secret) and variables, the shadow-mode exit criteria and rollback trigger from plan.md Rollout, and the exact `gh` and JQL queries measuring SC-001..SC-004; link it from `dev/README.md`
- [X] T036 [P] Add the three workflows to the relevant table in `dev/knowledge/` if one lists CI workflows (check `dev/knowledge/` for a CI or GitHub Actions page first; skip if none exists) (skipped: no CI workflow page in dev/knowledge/)
- [X] T037 Run the `/pre-ci` checks for the changed areas (ruff whole-repo, `ty check .`, yamllint, markdown lint, `gh aw compile` drift, the new pytest job) and fix every failure
- [X] T038 Confirm no changelog fragment is needed: the change is internal CI automation with no user-visible effect on Infrahub (AGENTS.md changelog rule)
- [ ] T039 After governance sign-off: create the `opsmill-dependabot-autopilot` GitHub App, install it on `opsmill/infrahub`, store secrets and variables per `data-model.md` Configuration with `DEPENDABOT_AUTOPILOT_MERGE=off`, then run quickstart.md Q1 in a sandbox repository and record the result in research.md R3
- [ ] T040 Run quickstart.md Q2–Q9 on live Dependabot PRs and fixtures; start the two-week shadow period; Q10 (switching merges on) is a separate decision after the exit criteria are met

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 first; T002–T005 in parallel.
- **Foundational (Phase 2)**: after Phase 1; T006 → T007; T008 ‖ T010; T009 after T008; T011 after T010 and T006; T012 after T011.
- **US1 (Phase 3)**: after Phase 2. Tests T013–T016 in parallel, T017 after T006/T007; implementations T018–T020 in parallel, T021 after T016, T022 after T017–T021; T023 after T001 and T002; T024 after T022; T025 independent; T026 after T023 and T024.
- **US2 (Phase 4)**: after Phase 2 and T022 (it reuses the artifact resolution); independent of the merge switch.
- **US3 (Phase 5)**: after T030 (Jira adapter).
- **Polish (Phase 6)**: after the stories it documents; T039 needs governance sign-off; T040 needs T039.

### Parallel Examples

```text
Phase 1:  T002 | T003 | T004            (after T001)
Phase 2:  T008 | T010
US1 tests: T013 | T014 | T015 | T016
US1 impl:  T018 | T019 | T020
US2:       T027 | T028
Polish:    T035 | T036
```

## Implementation Strategy

### MVP (User Story 1 only)

1. Phases 1–2, then Phase 3.
2. Merge with `DEPENDABOT_AUTOPILOT_MERGE=off`; run T039–T040 for US1 scenarios.
3. Two weeks of shadow verdicts; switch merges on only when the plan's exit criteria hold.

### Incremental Delivery

1. US1 (shadow) → US1 (merges on) delivers SC-001 and SC-002.
2. US2 adds tracked opportunities (SC-004).
3. US3 adds the digest.

Each story ships as its own PR against `stable` if preferred; the workflows must reach the default branch for `workflow_run` and `schedule` triggers to fire.
