# Implementation report: Phase 5 per-branch drift (T076 to T083, T085)

- Feature: repository commit visibility, User Story 3 (per-branch drift from the branch list)
- Spec directory: `dev/specs/ifc-3101-repo-commit-visibility`
- Branch: `pog-answer-per-branch-drift-ifc-3154`
- Base commit: `28e19ffae4`
- Head commit before this report: `e7bd42249b`
- Wall-clock: 2026-10-07T13:46Z to 2026-10-07T14:15Z, about 29 minutes
- Status: DONE. Every requested task is complete and every new or modified test has local-pass evidence.

Scope: only T076 to T083 and T085, as requested. T084 (the hand-off note on the IFC-3104 epic) is a task for a person and was not attempted.

## Chunk ledger

### Chunk 1: Phase 5 backend (T076, T077, T078, T079)

- Tasks: 4. Outcome: 4 done, 0 partial, 0 blocked.
- Commit: `a06e8b87b7`
- Decisions the subagent reported:
  - Added `backend/infrahub/git/state/branch_heads_wire.py`, which mirrors `commit_log_wire.py`. The wire row is named `GitBranchDriftRow`, because the domain dataclass already uses the name `BranchDriftRow`.
  - The warm-up for a repository that is not cloned yet pins to the first row that has a tracked commit, or to the first row when none has one. data-model.md did not specify this choice.
  - The drift resolver sends no worker request in two cases: when no row has a `git_ref`, or when the query selects none of `fetched_at`, `unavailable` and `edges`. Round 5 (`845f1f9d67`) replaced the second rule: the worker is called only when `fetched_at` or `unavailable` is selected, or `remote_head` or `condition` under `edges.node`.
  - `_measure_facts` now takes hashes and an `is_ancestor` callable, and skips the ancestry check when the head equals the imported commit. The branch-heads pass caches the imported-commit and ancestry lookups for the duration of one pass.
  - The 10 existing `test_drift_*` tests now take an `unavailable_reader` fixture, because the resolver now calls the reader. Their assertions are unchanged.
  - Regenerated `docs/docs/reference/message-bus-events.mdx`. `schema/schema.graphql` is unchanged.

### Chunk 2: Phase 5 tests and changelog (T080, T081, T082, T083)

- Tasks: 4. Outcome: 4 done, 0 partial, 0 blocked.
- Commit: `1cf60ac8c0`
- Decisions the subagent reported:
  - Fixed a defect in production code from chunk 1. A worker reply leaves out its null fields, but `GitBranchDriftRow` required `git_ref`, `tracked_commit` and `remote_head`. The API side therefore failed to parse any row that had no remote head (`NO_REMOTE`, `REF_MISSING`) or nothing tracked. The three fields now default to `None`. T080 failed before the fix and passes after it. A later review fix made `git_ref` required again on both drift row types, because every row the worker sends carries the ref from its request; `tracked_commit` and `remote_head` still default to `None`.
  - The changelog fragment is `changelog/+ifc-3101-branch-drift-query.added.md`, created with `towncrier create`. tasks.md named it without the `+` prefix. The other ifc-3101 fragments use the prefix, and a name without it renders as a broken issue link. The third local cubic round folded this fragment into `+ifc-3101-repository-commits-api.added.md` and deleted it, because the drift query is unreleased and both fragments would have appeared in the same release notes.
  - T080 tests "three behind" on 12 branches, not 200. T081 covers the 200-branch case with exactly one worker message, and its call phase takes 5.3 s.
  - The subagent ticked tasks.md with `perl -pi`, which breaks the rule against editing files from the shell. The orchestrator checked the diff: only the four checkboxes changed.

### Chunk 3: Phase 5 quickstart walk (T085)

- Tasks: 1. Outcome: 1 done, 0 partial, 0 blocked.
- Commit: `e7bd42249b`
- Differences between the docs and the code, all fixed in the docs:
  - Phase D and Phase A step 3 of quickstart.md said a read-only branch with nothing tracked reads as `NOT_TRACKED` from the graph alone. Such a branch is sent to the worker, reads `UNAVAILABLE` until the worker answers, then `NOT_TRACKED` (or `REF_MISSING` if its ref is gone). Only a branch with no ref reads `NOT_TRACKED` without the worker.
  - The query-count check runs at 5 and 20 branches under a lowered `query_size_limit`, not at 200 branches. Corrected in quickstart.md and plan.md. After the run, the user accepted the smaller check, and spec.md FR-004 and SC-005 were updated to match it. The single worker request is still checked at 200 branches.
  - data-model.md now names `GitBranchDriftRow` with its nullable fields, and lists the `branch_heads_wire` module.
  - `contracts/message_bus.md` now states:
    - the rule for which branch the warm-up pins to
    - that tag and commit-hash refs apply only to read-only repositories
    - the two cases in which the resolver sends no worker request
  - The Phase D test command now runs all three drift test suites.
- Steps not run: the live Phase D scenario needs a running Infrahub stack, which was not started. Component tests cover its assertions.

## Tasks not completed

None of the requested tasks. `T084` is still `[ ]`. It was excluded from this run because it is a hand-off note for a person to write.

## Local-pass evidence

| Test id | Type | Run command | Passed at (ISO 8601) | Environment context | Verbatim pass line |
|---------|------|-------------|----------------------|---------------------|--------------------|
| `backend/tests/component/message_bus/operations/git/test_branch_heads.py::test_only_the_branches_whose_remote_moved_read_as_behind` | component | `INFRAHUB_USE_TEST_CONTAINERS=true env -u INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES uv run pytest backend/tests/component/message_bus/operations/git/test_branch_heads.py backend/tests/component/graphql/queries/test_repository_git_state.py backend/tests/unit/git/state backend/tests/unit/message_bus -v -n 0` | 2026-10-07T14:06:27Z | testcontainers Neo4j, macOS, Python 3.14 | `... PASSED` / `97 passed, 16 warnings in 43.27s` |
| `backend/tests/component/message_bus/operations/git/test_branch_heads.py::test_each_read_write_row_is_classified_on_its_own` | component | same as above | 2026-10-07T14:06:27Z | same as above | `... PASSED` |
| `backend/tests/component/message_bus/operations/git/test_branch_heads.py::test_a_read_only_ref_deleted_upstream_reads_as_missing` | component | same as above | 2026-10-07T14:06:27Z | same as above | `... PASSED` |
| `backend/tests/component/message_bus/operations/git/test_branch_heads.py::test_a_worker_without_a_clone_starts_a_warm_up_pinned_to_a_tracked_branch` | component | same as above | 2026-10-07T14:06:27Z | same as above | `... PASSED` |
| `backend/tests/component/graphql/queries/test_repository_git_state.py::test_drift_reads_every_branch_in_one_worker_request` | component | same as above | 2026-10-07T14:06:27Z | same as above | `... PASSED` |
| `backend/tests/component/graphql/queries/test_repository_git_state.py::test_drift_keeps_every_row_when_no_worker_answers` | component | same as above | 2026-10-07T14:06:27Z | same as above | `... PASSED` |
| `backend/tests/component/graphql/queries/test_repository_git_state.py::test_drift_offers_no_filtering_ordering_or_counting` | component | same as above | 2026-10-07T14:06:27Z | same as above | `... PASSED` |
| `backend/tests/component/graphql/queries/test_repository_git_state.py::test_drift_*` (the 10 existing drift tests; only their fixture parameter changed) | component | `INFRAHUB_USE_TEST_CONTAINERS=true env -u INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES uv run pytest backend/tests/component/graphql/queries/test_repository_git_state.py backend/tests/component/graphql/auth/test_repository_git_state_permissions.py backend/tests/component/message_bus/operations/git/test_commit_log.py -q -n 0` | 2026-10-07T13:56:31Z | testcontainers Neo4j | `72 passed, 16 warnings in 58.84s` |
| `backend/tests/unit/message_bus/test_mappings.py` (adds `git.branch_heads.get` to `operations_without_flows`) | unit | `uv run pytest backend/tests/unit/message_bus/test_mappings.py backend/tests/unit/git/state -q -n 0` | 2026-10-07T13:56:27Z | n/a | `53 passed` |

The T085 walk re-ran the three drift suites (51 tests, including those above) at 2026-10-07T14:10:27Z on commit `1cf60ac8c0`, and all passed: `51 passed, 16 warnings in 56.93s`. No E2E tests were added.

## Review findings

The first review covered `28e19ffae4..HEAD`. It found no critical or high-severity issues, so no code changed during the run. The Status column shows what happened to each finding after the run, in the follow-up rounds described in "Follow-up review rounds".

| Severity | File | Finding | Status |
|----------|------|---------|--------|
| Medium | `backend/infrahub/graphql/queries/repository_git_state.py:502` | The drift resolver catches only `WorkerTimeoutError`. Any other worker failure, such as a damaged clone with no warm-up running, returns an `RPCError` that fails the whole query, so the graph rows are lost. spec.md FR-022 says the rows must render whenever the drift information is unavailable. `contracts/message_bus.md` names only the timeout. Fixing it needs a new `RepositoryGitUnavailableReason` value, which changes the GraphQL schema. | Accepted by the user for now |
| Medium | `backend/infrahub/graphql/queries/repository_git_state.py:487` | `edges` is in `DRIFT_GIT_FIELDS`, so a query that selects only graph fields under `edges` still sends a worker request and can wait until the timeout. No test checks the "no worker request" case for the drift query. | Fixed in `845f1f9d67`. An earlier version of this report marked it fixed in `b9c7ad4133`, which was wrong: that commit only tested queries that select no `edges` at all |
| Medium | `changelog/+ifc-3101-repository-commits-api.added.md:1` | The fragment still says the drift query reports the remote comparison "as unavailable for now". This contradicts the new fragment in the same release notes. | Fixed after the run: the clause is removed |
| Medium | `backend/infrahub/message_bus/messages/git_branch_heads_get.py:43` | The `http_code` field is never set or read. No field-parity test for `branch_heads_wire` mirrors `test_commit_log_wire.py`. | Fixed in `b9c7ad4133`: the field is removed; no parity test added |
| Medium | `backend/infrahub/git/state/bus_reader.py` | `BusRepositoryGitStateReader.branch_heads` has no unit test for the timeout it passes, for a failed reply, or for a contradictory reply. | Partly fixed in `b9c7ad4133`: a test for the contradictory reply added |
| Medium | `backend/tests/component/message_bus/operations/git/test_branch_heads.py` | Three cases have no test: a read-only ref that is a commit hash, a tracked commit the clone does not hold (`ORPHANED`), and a read-write repository that is not cloned and has nothing imported. | Partly fixed in `b9c7ad4133`: tests for the commit hash and the not-cloned case added; no `ORPHANED` test |
| Low | `backend/infrahub/git/base.py:567` (used at `log_reader.py:443`) | `name.replace("origin/", "")` removes every `origin/` in a branch name, not only the prefix. A branch such as `feat/origin/x` reads as `NO_REMOTE` in drift but resolves in the commit log. The defect is in older code. | Fixed for drift in `b9c7ad4133`: the drift read no longer uses this helper. The helper itself is unchanged, because repository sync uses it |
| Low | `backend/infrahub/git/state/log_reader.py:443` | Errors other than `GitCommandError` while listing remote branches reach the caller with their raw text instead of the safe message. | Deferred |
| Low | `backend/infrahub/git/state/log_reader.py:454` | `head_of` repeats the ref lookup order of `_resolve_head`, so the two can drift apart. | Deferred |
| Low | `backend/infrahub/git/state/log_reader.py:84-150` | The commit-log and branch-heads reads duplicate the code that builds the repository and the warm-up request. | Deferred |
| Low | `backend/infrahub/git/state/log_reader.py:270` | The `_READ_ONLY_COPY` message still mentions only the commit log. | Fixed in `b9c7ad4133` |
| Low | `git_branch_heads_get.py:30`, `models.py:180` | `git_ref` is optional on the reply row and the domain row, although the request always carries one. | Fixed in `b9c7ad4133`: required on both |
| Low | `test_branch_heads.py:233` | A `model_dump()` assertion repeats the equality check on the line above it. | Fixed in `64a4445` |
| Rejected | `backend/infrahub/git/state/log_reader.py:443` | The simplify review reported that `get_branches_from_remote()` opens a second `Repo` that is never closed. This is wrong: `get_git_repo_main` returns the cached `cache_repo`, which is the handle that `_read_and_close` closes. The drift read now reads `repo.remotes.origin.refs` directly. | Not a defect |

## Follow-up review rounds

After the run, the user asked for the review to be repeated against the parent branch, `origin/pog-repo-commit-visibility-ifc-3101...HEAD`, with fixes between rounds. No round found a critical or high issue.

- Round 2 led to `b9c7ad4133`:
  - the drift read now takes remote heads from `repo.remotes.origin.refs` and removes only the leading `origin/`
  - `http_code` is removed
  - `git_ref` is required on both drift row types
  - the `_READ_ONLY_COPY` text now covers both reads
  - new tests cover the skipped worker request when no `edges` are selected, a pinned commit hash, a read-write ref with a tag's name, a not-cloned repository with nothing imported, and a contradictory reply
  - Tests: `45 passed` (component, 2026-10-07T14:54:12Z) and `59 passed` (unit, 2026-10-07T14:55:13Z)
- Round 3 led to `64a4445`:
  - a remote ref whose commit is missing is skipped and logged, instead of failing the whole read; GitPython raises a plain `ValueError` for it
  - a new test checks that each worker answer is matched to its own branch, and asserts the whole payload, including `fetched_at`
  - the T077 wording in tasks.md now includes the commit-hash match
  - the stale test docstring and the repeated assertion are removed
  - Tests: `47 passed` (component, 2026-10-07T15:04:10Z) and `59 passed` (unit, 2026-10-07T15:05:07Z)
- Round 4 led to `255a07b`:
  - the warning for a skipped remote ref names the repository
  - the tag-skip comment, the `BranchDriftResult` docstring and the T027 text in tasks.md are corrected
  - Tests: `85 passed` (branch-heads and commit-log component tests and git-state unit tests, 2026-10-07T15:17:31Z)
- Round 5, a `/code-review` at `xhigh` against `28e19ffae4..HEAD`, led to `845f1f9d67` and one more commit:
  - FR-008: the drift query calls the worker only when `fetched_at` or `unavailable` is selected, or `remote_head` or `condition` under `edges.node`; a query for graph-side row columns alone no longer waits on a worker
  - a remote ref pointing at a tree or blob (GitPython raises `TypeError`) is skipped instead of failing the whole read
  - an annotated tag whose target commit is missing is skipped, so its row reads `REF_MISSING` instead of failing every row in the ancestry check
  - the per-pass ref lookup is cached
  - the ancestry check builds `Commit` objects from the hex hashes without a git lookup. As a side effect, a missing hash now fails the commit-log read as a `RepositoryError` rather than a `ValueError`; the read failed in that case before too
  - the user decided that a row keeps its remote head under `NOT_TRACKED` and `ORPHANED`, so the `RepositoryBranchDrift.remote_head` description now reads "Null when there is no remote counterpart". The schema, the frontend types and `contracts/repository_git_state.graphql` are updated. A consumer should read `condition`, not compare `remote_head` with `tracked_commit`, to decide whether a row has drifted
  - Tests: `79 passed` (component, 2026-10-07T15:51:19Z) and `59 passed` (unit, 2026-10-07T15:52:31Z)
- Round 6, a local cubic review following the `reviewing-local-changes` skill from PR #10715, with the backend, testing and frontend checklists, plus a `speckit-analyze` check of the spec documents:
  - the drift read now resolves only the refs the request names, by full ref name (`refs/remotes/origin/<ref>`, then `refs/tags/<ref>` for read-only), instead of every remote branch and every tag on each read; the skip rules are unchanged, and a new test checks packed refs
  - the `RepositoryBranchDrift.remote_head` description now also says it is null when `condition` is `UNAVAILABLE`
  - T083 names the shipped fragment, plan.md lists `branch_heads_wire.py`, and this report's repeated bullets and outdated gating rule are corrected
  - Tests: `40 passed` (branch-heads and commit-log component tests, 2026-10-07T16:11:15Z) and `48 passed` (git-state unit tests, 2026-10-07T16:12:01Z)
- Local cubic rounds 2 to 4 (`c60b9b6`, `2cff054`): the duplicate timeout fixture and bus double are removed, and the drift fragment is folded into `+ifc-3101-repository-commits-api.added.md`. Round 4 raised only the accepted FR-022 finding and a `git_ref` of `HEAD`, which is deferred below. The skill stops after four rounds.
- Deferred from rounds 2 to 6, as suggestions:
  - a `git_ref` of `HEAD` reads as having no remote in drift, while the commit log resolves `origin/HEAD` to the remote's default branch
  - a read-only branch tracking an annotated tag whose object is missing reads as `REF_MISSING` with no log line
  - the drift resolver catches only the timeout; a clone that outlasts the one-minute warm-up claim is a likely way to hit this (accepted by the user)
  - the commit log and drift resolve a ref differently when the remote has a tag named `origin/<branch>`
  - a drift query with a past `at` can skip a warm-up that a worker without a clone needs now
  - the domain drift row accepts combinations that contradict each other
  - repeated test setup (five reader-swap fixtures and two inline messages); the duplicate timeout fixture and bus double were removed in the second local cubic round

## Autonomous decisions

- Split Phase 5 into three chunks (backend, tests and changelog, quickstart walk), following the order the user gave.
- Ran the review aspects in three agents in parallel, not one after another, because they were read-only and could not conflict. The simplify review ran in report-only mode, so it changed no code.
- Reviewed this branch's own commits instead of the file list from `detect-changed-files.sh`. The script compares against `stable`, so it would have included hundreds of files from `develop`. The follow-up reviews compare against the parent branch, `origin/pog-repo-commit-visibility-ifc-3101`, which the user confirmed.
- Accepted the production fix made in chunk 2, because the test it unblocked showed the defect.
- Accepted the `perl -pi` edit to tasks.md without reverting it, after checking that it changed only the checkboxes.
- Deferred all medium findings. The skill requires fixes only for high severity. The `RPCError` finding also needs a GraphQL schema change, which AGENTS.md says to ask about first.

## Suggested next steps

1. Write the T084 hand-off note on the IFC-3104 epic. It should say that the Branches card decides drift from `condition`, since `remote_head` is also set for `NOT_TRACKED` and `ORPHANED` rows.
2. Raise the `origin/` handling in `get_branches_from_remote()` (`git/base.py:567`) as a separate change, since repository sync uses it.
3. Run `/pre-ci`, then open the PR for PR 10.
