# Implementation Plan: Multi-environment single-repo validation (Approach A)

**Branch**: `multi-env-repo-tests` | **Date**: 2026-06-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/001-multi-env-repo-tests/spec.md`

## Summary

Add automated tests that lock the working contract of the multi-environment single-repo pattern
(Approach A — read-only consumers) and reproduce the open multi-worker write-back defect (#9568),
plus two suspected unfiled defects surfaced by reading the git-integration code (divergent-pull
worktree poisoning; the branch filter not bounding fetch-time failures).

Technical approach is two-pronged, mirroring existing harnesses (no new framework):

- **Deterministic prong** — `backend/tests/integration/git/` (mirrors `test_git_live_remote.py`):
  real local Git remote + real `InfrahubRepository`/`client`/`db`, no container stack. Hosts every
  mechanism-level guarantee and defect reproduction, including the **sole** #9568 reproduction (by
  reconstructing the failing worker-clone state — no live worker pool). Runs in CI. Defect
  reproductions are `xfail(strict)`.
- **Full-stack prong** — `backend/tests/integration_docker/` (mirrors `test_propose_change_repository.py`
  / `test_repositories.py`, base class `TestInfrahubDockerClient`): full testcontainers stack, used
  **only** for the faithful Approach-A demonstration (US2) as **two separate instances sharing one
  remote**. Heavier; opt-in / excluded from the default CI run.

**Clarified (2026-07-01):** US2 uses two real instances (separate stacks), not a single-instance/two-
repo form. The full-stack multi-worker write-back demonstration (former US1§2) is **dropped** as too
flaky to gate on; #9568 is covered solely by the deterministic prong. Consequently **no
multi-worker/cluster harness is needed anywhere**.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: pytest 9.0, GitPython (`git`), `infrahub_sdk.testing` (`TestInfrahubDockerClient`, `GitRepo`, `GitRepoType`), `infrahub_testcontainers` (compose harness), Prefect (flow execution)
**Storage**: Neo4j (graph) + local Git remote provisioned per test; full-stack prong adds the testcontainers stack (DB, task-manager, workers)
**Testing**: `backend/tests/integration/git/` (in-process server + real remote) and `backend/tests/integration_docker/` (full distributed stack, testcontainers)
**Target Platform**: Linux/macOS dev + CI runners (Docker required for the full-stack prong)
**Project Type**: Backend test suite (no product code change in scope)
**Performance Goals**: Deterministic prong within the normal integration-test budget; full-stack prong opt-in, no default-CI budget impact
**Constraints**: Zero flake on deterministic checks; assert on authoritative branch list / recorded commit, never on `sync_status` or merge return value; trigger-and-poll, never fixed sleeps
**Scale/Scope**: Approach A only; one development instance + one read-only consumer (two environments; staging≈prod not separately modelled); multi-worker dev intentionally enabled

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

This feature adds **tests only**; no schema, query, API, or UI surface. Frontend principles do not
apply (no UI). Relevant gates:

| Principle | Status | Notes |
|---|---|---|
| IV. Test Discipline | PASS | Uses the prescribed levels: `tests/integration/` (real remote, in-process) and `tests/integration_docker/` (full distributed stack) — the latter is exactly the constitution's home for "features involving … schema migrations / triggered actions / distributed behaviour". Adapter/protocol over mocking: no mocks introduced; real Git remote and real stack are used. Test files mirror source structure (`infrahub/git/*` → `tests/.../git/*`). Existing schema fixtures reused (`SchemaCarPerson` / `car-dealership` repo fixtures). |
| VII. Simplicity & Maintainability | PASS | No new framework or dependency; reuses `TestInfrahubDockerClient`, `GitRepo`, and the `test_git_live_remote.py` pattern. One new harness capability is accepted in-scope by clarification: two stacks sharing one remote (see Complexity Tracking). Dropping the flaky full-stack multi-worker demo keeps the suite lean. |
| II. Branch-Safe by Default | PASS (subject-of-test) | The behaviour under test *is* branch/merge behaviour across the git-integration boundary; merge and branch-mapping semantics are asserted explicitly, satisfying "merge behavior … MUST be specified and tested". |
| I / III / V / VI | N/A | No schema writes, typed query results, new Cypher, or input boundaries are introduced by test code. Tests must still use keyword arguments and type hints per house style. |

**Code-doc-style gate (repo rule):** issue IDs (#9568 etc.) appear in the spec/plan but MUST NOT
appear in test names, docstrings, or comments. Defect-tracking is expressed via behaviour-named
`xfail(strict, reason=...)` markers whose reason describes the behaviour, not the ticket.

No violations. Gate passes.

## Project Structure

### Documentation (this feature)

```text
specs/001-multi-env-repo-tests/
├── plan.md              # This file
├── spec.md              # Feature spec
├── research.md          # Phase 0 — decisions + open verifications
├── data-model.md        # Phase 1 — test topology + defect-state model
├── quickstart.md        # Phase 1 — how to run each suite
├── contracts/
│   └── behavioural-contract.md   # Phase 1 — assertion matrix per user story
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 — created by /speckit-tasks (NOT here)
```

### Source Code (repository root)

```text
backend/tests/integration/git/
├── test_git_live_remote.py          # EXISTING — pattern to mirror
└── test_multi_env_writeback.py      # NEW — deterministic prong:
                                     #   US1§1 non-importer-clone write-back drop (xfail)
                                     #   US3   non-main default import, no phantom (green)
                                     #   US4§1 divergent-pull worktree poisoning (xfail)
                                     #   US4§2 non-ff write-back drop (xfail)
                                     #   US4§3 in-merge conflict surfaced + aborted (green)
                                     #   US4§4 per-branch failure isolation (green)
                                     #   US5   fetch-before-filter blast radius (xfail) + filter excludes branch (green)

backend/tests/integration_docker/
├── test_propose_change_repository.py  # EXISTING — pattern to mirror
├── test_repositories.py               # EXISTING — pattern to mirror
└── test_multi_env_approach_a.py       # NEW — full-stack prong (opt-in marker):
                                       #   US2   read-only consumer isolation + promotion-via-reimport
                                       #         (TWO separate instances sharing one remote)

backend/tests/helpers/  (only if a shared helper serves ≥2 callers — see Simplicity gate)
```

**Structure Decision**: Mirror the two existing git-test harnesses rather than create a new suite.
The deterministic prong lives beside `test_git_live_remote.py` in `backend/tests/integration/git/`;
the full-stack prong lives beside the existing repository/proposed-change docker tests in
`backend/tests/integration_docker/`. This honours FR-011 and the Simplicity principle and reuses
`TestInfrahubDockerClient` + `GitRepo` verbatim where possible.

## Complexity Tracking

| Accepted complexity | Why it is needed | Approach |
|---|---|---|
| Two testcontainers stacks sharing one remote | **Clarified in-scope (2026-07-01):** US2 requires two real instances; single-instance/two-repo is rejected | Boot two `TestInfrahubDockerClient`-style stacks, each bind-mounting the **same** host remote dir. Second-stack + shared-mount wiring is the primary new harness work; verify in implementation. |
| Extending `GitRepo.add_to_infrahub` to set `default_branch`/`ref` | `GitRepo` currently sends only `name`+`location` | Issue the `CoreRepositoryCreate`/`CoreReadOnlyRepositoryCreate` mutation directly (as `test_git_live_remote.py` already does for some cases) instead of modifying the shared SDK helper. |
| Bare remote for write-back push | `GitRepo.init` creates a non-bare repo; pushing to its checked-out branch is rejected | Configure the remote to accept the write-back (bare clone or `receive.denyCurrentBranch=updateInstead`) in the test setup; decided in research.md. |
