# Phase 0 Research: Multi-environment single-repo validation

All architectural unknowns were resolved during a prior design (grilling) session; this records the
decisions and the few items that remain *empirical verifications for the implementation phase*
rather than open design questions.

## Decision 1 — Two prongs, two existing harnesses

**Decision**: Deterministic mechanism tests in `backend/tests/integration/git/`; full-stack
demonstration in `backend/tests/integration_docker/`.
**Rationale**: The mechanism-level guarantees (branch mapping, divergent pull, non-ff push, filter
behaviour) are git-and-repo-object behaviours that need a real remote but not a worker pool — they
belong with `test_git_live_remote.py`, run fast, are deterministic, and fit CI. Only the true
multi-worker and multi-environment demonstrations need the full stack, which already has a home in
`integration_docker`.
**Alternatives considered**: A new top-level `tests/multi_env/` suite (rejected — duplicates harness
plumbing, violates Simplicity/FR-011); putting everything in `tests/e2e/` (rejected — that suite is
Playwright-coupled, single-stack, and shard-marker-gated).

## Decision 2 — Reproduce the multi-worker write-back defect deterministically only (clarified 2026-07-01)

**Decision**: A single deterministic check that reconstructs the failing worker-clone state. The
statistical full-stack demonstration was considered and **dropped** (clarification Q2=C) as too flaky
to gate on. `xfail(strict)`.
**Rationale**: The defect is intermittent in a live pool (depends on which worker handles the merge),
so a full-stack run risks passing by chance — and under `xfail(strict)` a chance pass becomes a false
"fixed" (XPASS) signal. The deterministic reconstruction pins the mechanism with zero flake and still
faithfully confirms the documented root cause, so the live-pool run adds cost and flake without a
better signal.
**Mechanism (confirmed by code)**: `InfrahubRepository.merge` → `push` → `repo.remotes.origin.push`
has no error handling (the `# TODO Catch potential exceptions`); a worker whose clone lacks a local
default branch pushes a missing refspec, which GitPython does not raise on. The deterministic check
constructs a clone with the local primary branch + `origin/<default>` only (no local `<default>`)
and asserts the push reports success while the remote tip does not advance.
**Alternatives considered**: Forcing the merge onto a specific worker (rejected — Prefect task
routing is not cleanly pinnable); statistical full-stack over N merges (rejected — XPASS flake);
loop-until-drop (rejected with the whole live-pool approach).

## Decision 3 — No multi-worker/cluster harness needed (clarified 2026-07-01)

**Decision**: Because the live-pool demonstration is dropped (Decision 2), **no test runs a
multi-worker pool**; the cluster deployment and `INFRAHUB_TESTING_TASK_WORKER_COUNT` are not used.
**Consequence**: The full-stack prong (`integration_docker`) is used only for US2, which needs two
*instances* but not multiple *workers* per instance. This removes the earlier open verification about
reaching the cluster worker-count knob from a test class.

## Decision 4 — `default_branch` / `ref` set via direct mutation, not by changing the shared helper

**Decision**: Register repos with explicit `CoreRepositoryCreate` (`default_branch`) and
`CoreReadOnlyRepositoryCreate` (`ref`) mutations in the test, rather than extending
`GitRepo.add_to_infrahub` (which currently sends only `name`+`location`).
**Rationale**: Keeps the change local to the tests (Simplicity); `test_git_live_remote.py` already
shows direct-mutation registration. `default_branch` must be set **at creation**, never
create-then-update (create-then-update strands a permanent phantom — a documented field trap).

## Decision 5 — Writable (bare) remote for write-back

**Decision**: The shared remote used by the development (read-write) instance must accept the
write-back push — provision it bare, or set `receive.denyCurrentBranch=updateInstead` on the remote
checkout.
**Rationale**: `GitRepo.init` creates a non-bare repo; pushing to its checked-out branch is rejected
by default, which would mask the real defect behind an unrelated rejection.
**Open verification**: confirm whether `remote_repos_dir` repos are bare under the testcontainers
harness; if not, configure the remote in test setup.

## Decision 6 — Determinism of sync/import/reimport

**Decision**: Drive state changes by explicit triggers and poll observable state:
- Read-only consumer promotion: `InfrahubReadOnlyRepositoryImportLastCommit` mutation (explicit,
  synchronous to enqueue), then poll the consumer's recorded `commit` until it equals the pushed SHA.
- Write-back: event-driven off the in-Infrahub merge; assert the remote tip via `git ls-remote` /
  the bare repo's ref.
- Development-instance feature-branch / default-branch import: relies on the periodic
  `sync_remote_repositories`; poll `client.branch.all()` and the recorded `commit`, never
  `sync_status`, never a fixed sleep.
**Rationale**: Matches the documented gotchas (status fields unreliable; branch/sync state only
settles after a post-activation periodic cycle; the merge return value and `BranchMerge` result are
not reliable success signals).

## Decision 7 — Two suspected defects are validated, then drafted (not pre-filed)

**Decision**: US4§1 (divergent pull leaves a poisoned worktree) and US5 (fetch-before-filter blast
radius) are written as `xfail(strict)` and only **after** they fail as predicted are issues drafted
— via the issue-reporting skill, one file per defect, for user review, never auto-submitted.
**Evidence supporting the prediction**: `pull` (base.py) raises on divergence but does not
`merge --abort`/reset, and `_raise_enriched_error_static` already handles the follow-up
`"because you have unmerged files"` state — implying the worktree is left conflicted. `fetch()` runs
before `get_filtered_remote_branches`, fetches all heads+tags with no refspec, and is outside the
per-branch try/except, so a fetch-time failure aborts the whole repo sync regardless of the filter.
**Open verification**: the exact fetch-time trigger (a force-pushed *branch* does NOT fail fetch;
clobbering/moved **tags** under `tags=True` are the likely trigger) must be confirmed empirically by
the US5 test before any issue is drafted.

## Open verifications carried into implementation

1. How to boot **two** `TestInfrahubDockerClient`-style stacks that bind-mount the **same** host
   remote dir (the accepted two-stack harness work for US2 — clarification Q1=B).
2. Whether `remote_repos_dir` repos are bare / how to make the write-back remote writable (Decision 5).
3. The precise fetch-failure trigger for US5 (Decision 7).

None of these block planning. Items previously listed here about cluster worker scaling and the
single-instance fallback are resolved by clarification (Decisions 2–3; two stacks are committed).
