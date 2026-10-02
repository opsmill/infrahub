---

description: "Task list for Git history-rewrite reconciliation (IFC-3210)"
---

# Tasks: Git history-rewrite reconciliation

**Input**: Design documents from `dev/specs/ifc-3210-history-rewrite-reconciliation/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/)

**Branch**: `history-rewrite-reconciliation-ifc-3210`, branched from `develop`.

**Tests**: included. The constitution requires them, and the PRD names the test set.

**Organization**: grouped by user story, so each story can be implemented, tested and delivered on
its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel with the other `[P]` tasks in the same phase. Different files, no
  dependency on an incomplete task.
- **[Story]**: which user story the task belongs to.
- Every task names its file. A site inside a file is named by its enclosing symbol, never by a line
  number.

## Gates before any code is written

| Gate | Blocks | Who |
|---|---|---|
| **Schema and GraphQL sign-off** ("Ask First" under `AGENTS.md`) | Phase 6 | A maintainer |
| **The FR-014 consumer confirmed** | Phase 7 | Patrick Ogenstad |
| **Merge order agreed against PR #10542** | Phase 5 | Patrick Ogenstad |
| **Whether to wait for PR #10669 to reach `develop`** | Phase 8, and only which file it attaches to | Patrick Ogenstad |

---

## Phase 1: Setup

**Purpose**: prepare the worktree so the tests can run at all.

- [x] T001 Initialise the submodules in this worktree and reinstall the SDK in editable mode, so
      `backend/tests/` can import `infrahub_sdk`. Run `git submodule update --init --recursive`
      then `uv sync --all-groups`.
- [x] T002 Confirm the test environment is clean: unset every `INFRAHUB_*` variable inherited from
      the dev shell, then set `INFRAHUB_USE_TEST_CONTAINERS=1`. A leftover
      `INFRAHUB_USE_TEST_CONTAINERS=false` sends the suite at an external Neo4j. See
      [quickstart.md](quickstart.md).
- [x] T003 [P] Create the package `backend/infrahub/git/divergence/` with an empty `__init__.py`.
- [x] T004 [P] Create the test package `backend/tests/unit/git/divergence/` with an empty
      `__init__.py`.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: the classification every user story reads. Slice A of the plan.

**Blocks**: every phase from 3 onwards.

- [x] T005 [P] Define `RefClassification` and `RefDivergence` in
      `backend/infrahub/git/divergence/models.py`, per
      [data-model.md](data-model.md), "New in-process types". `RefClassification` is a `StrEnum`
      with `UNCHANGED`, `FAST_FORWARD`, `REWRITE`, `RETARGET` and `REMOTE_ABSENT`.
      `RefDivergence` holds a nullable `remote_head` and enforces the three validation rules in
      that section.
- [x] T006 [P] Define `ReconciledBranch` in `backend/infrahub/git/divergence/models.py`. It carries
      the Infrahub branch name, the branch UUID, the commit, and an optional `RefDivergence`.
- [x] T007 Write the ancestry gateway in `backend/infrahub/git/divergence/gateway.py`. It exposes
      `is_ancestor` and `has_commit` as a `Protocol`, plus a GitPython implementation over
      `Repo.is_ancestor`. Every git failure leaves as a `RepositoryError`, so the detector imports no
      git library. Bind the implementation to one repository at construction, so neither call takes
      a repository argument and the `Protocol` names no git type.
- [x] T008 Make `has_commit` distinguish a missing object from a failed git call. Without it both
      arrive as `RepositoryError`, so a garbage-collected commit raises on every cycle and the
      branch never classifies. The absent-object rows of the contract table depend on this.
- [x] T009 Write `RemoteDivergenceDetector.classify` in
      `backend/infrahub/git/divergence/detector.py`, per
      [contracts/internal-interfaces.md](contracts/internal-interfaces.md) section 1. It takes
      `target_changed` from its caller and never reads the cache itself.
- [x] T010 [P] Write unit tests for the detector in
      `backend/tests/unit/git/divergence/test_detector.py`. Cover every row of the contract table.
      The negative cases carry the most weight: a fast-forward, a deliberate re-target and an
      absent remote ref must all come out clean. Cover the rewound remote too: a remote head that
      is an ancestor of the imported commit names `REWRITE`, and `RETARGET` when the target
      changed. No database.
- [x] T011 [P] Write unit tests for the models in
      `backend/tests/unit/git/divergence/test_models.py`. Assert that a `REWRITE` without an
      `imported_commit` is rejected.

**Checkpoint**: the classifier answers correctly and runs in seconds without a database.

---

## Phase 3: User Story 1 — a rewritten branch reconciles itself (P1)

**Goal**: the next synchronisation cycle resets a rewritten branch to the remote, re-imports it,
and raises nothing.

**Independent test**: push a branch to a live remote, let Infrahub import it, rewrite the history on
the remote, force-push, and run one cycle. The branch commit in the graph matches the new remote
head, the imported objects match the rewritten tree, and the repository reports healthy.

**Maps to**: FR-001, FR-003, FR-004, FR-017, SC-001, SC-003.

### Test harness

- [ ] T012 [US1] Add a force-push helper to
      `backend/tests/integration/git/test_git_live_remote.py`, beside the existing
      `_push_commit_to_remote`, which lives in that module and not in `conftest.py`. It builds a
      divergent history inside the Gogs container and pushes it with `--force`.
- [ ] T013 [P] [US1] Add a fixture that creates a Gogs repository with a tracked non-default branch
      already imported, in `backend/tests/integration/git/conftest.py`. The rewrite tests all start
      from that state.

### Implementation

- [ ] T014 [US1] Classify the staging-mode trunk pull too, in
      `backend/infrahub/git/repository.py::InfrahubRepository._collect_staging_imports`. It calls
      `self.pull(branch_name=self.default_branch)` outside the `ACTIVE` loop, so a rewritten trunk
      on a staging repository would be neither classified nor recorded, and before T041 would still
      fail with the old message.
- [ ] T015 [US1] Thread the per-branch graph commits down to
      `backend/infrahub/git/repository.py::InfrahubRepository.collect_pending_imports`. They are
      loaded once per cycle by `get_repositories_commit_per_branch` and live on
      `RepositoryData.branches` in `sync_remote_repositories`. Neither
      `sync_repository_from_origin` nor the subflow below it,
      `sync_git_repo_with_origin_and_tag_on_failure`, receives them today, so passing them through
      both is part of this task. The collector has no graph read of its own, and `get_commit_value`
      reads git rather than the graph, so without this the classifier has no input (FR-001b).
- [ ] T016 [US1] Build the candidate set in `collect_pending_imports` as the **union** of two
      comparisons: the branches `compare_local_remote` returns (local head against remote head), and
      the branches whose **graph commit** differs from the remote head. `compare_local_remote` alone
      misses a `default_branch` edit, which moves no ref, and misses a worker whose graph already
      matches the remote.
- [ ] T017 [US1] Classify each candidate after `fetch()` and before the per-branch `pull()`,
      **using the graph commit** as `imported_commit` and never the local worktree head. Keep the
      existing per-branch failure isolation: a branch that fails classification joins
      `failed_imports` and the cycle continues. See
      [contracts/internal-interfaces.md](contracts/internal-interfaces.md) section 1, "Two
      comparisons, not one".
- [ ] T018 [US1] Decide the reset in `collect_pending_imports` from **this worker's worktree
      against the remote head**, not from the classification. Reset when neither is an ancestor of
      the other. Pull as today when the worktree is behind. Do nothing when the worktree is ahead,
      or when the remote carries no such ref.
      **When the worktree already equals the remote head but the graph commit does not, write the
      commit and queue the import anyway.** Do not fall through to `pull` for this: it returns early
      at `if commit_after == commit_before: return True`, before `update_commit_value`, so a
      worktree that did not move writes nothing and imports nothing. Miss this and the graph never
      catches up, so a `default_branch` edit records a rewrite and fires the trunk event on every
      cycle after the first.
      Then record the commit and pin the commit worktree as the fast-forward path already does.
      This is what repairs a worker whose graph already equals the remote while its own worktree is
      stale (FR-001c). Keying the reset on the classification would leave that worker on the
      discarded history, flagged by `compare_local_remote` every cycle and repaired by nothing,
      because the `pull` fix of T041 is never reached on this path.
      The record follows the classification instead, and only `REWRITE` reaches the recorder. See
      the two tables in
      [contracts/internal-interfaces.md](contracts/internal-interfaces.md) section 1.
      A branch that is both ahead locally and rewritten remotely classifies `REWRITE`, and the
      reset moves it to the remote head. That is safe: `merge` pushes before it records and resets
      the destination on failure, so no merge commit survives on one worker alone.
- [ ] T019 [US1] Make `backend/infrahub/git/tasks.py::git_branch_create` write the new branch's
      commit to the graph after it creates and pushes the branch. It never does today, and `commit`
      is LOCAL, so the branch inherits the trunk's value at the fork point. The classifier then
      compares a branch's remote head against a trunk commit that has nothing to do with it, which
      can classify a healthy branch `REWRITE`. It also makes the "no recorded commit means
      `FAST_FORWARD`" rule in the contract dead code, because an inherited value is always present.
      **No backfill is needed for branches created before this lands.** Their first synchronisation
      writes the real commit through the ordinary import path, so the inherited value survives only
      until the branch next moves. A migration would race that write for no gain.
- [ ] T020 [US1] Return `ReconciledBranch` entries from `collect_pending_imports`, so the syncer and
      then the broadcast can name every branch the cycle advanced.
- [ ] T021 [US1] Give the divergent-branches case its own message in
      `backend/infrahub/git/base.py::InfrahubRepositoryBase._raise_enriched_error_static`. It names
      a divergent history and does not use the word "conflict" (FR-003, FR-017).
- [ ] T022 [US1] Log each reconciliation in `collect_pending_imports` with the repository, the
      branch, the discarded commit and the new commit (FR-019).

### Tests

- [ ] T023 [US1] Rename `backend/tests/component/git/test_git_repository.py::test_pull_branch_conflict`
      and change it to assert the corrected message: a diverged pull names a divergent history and
      never says "conflict" (FR-003, FR-017). **Do not** assert that `pull` resets the branch here.
      That behaviour is built in Phase 5, so asserting it in Phase 3 fails.
      The reset assertion belongs to the Phase 5 component test, which is its only home.
- [ ] T024 [P] [US1] Leave the `"Need to specify how to reconcile"` parameter in
      `backend/tests/integration/git/test_repository.py::test_repository_operational_status`
      **unchanged**. It is the stderr the test injects into `GitCommandError`, not a message the
      test asserts, and git still emits that text. Replacing it with Infrahub's new wording would
      make the classifier fall through to its generic branch, which still yields `ERROR`, so the
      test would keep passing while no longer exercising the divergent-branches case at all.
      Instead, add an assertion that the resulting message does not contain the word "conflict"
      (FR-003, SC-003).
- [ ] T025 [US1] Component-test the reconciliation log line (FR-019): it names the repository, the
      branch, the discarded commit and the new commit. Until INFP-671 ships a view, this line is the
      only way an operator learns a reconciliation happened, so nothing else holds it.
- [ ] T026 [US1] Add a live-remote test in
      `backend/tests/integration/git/test_git_live_remote.py`: a rewritten non-default branch
      reconciles and re-imports, and the repository reports healthy.
- [ ] T027 [US1] Add a live-remote test asserting a fast-forward still fast-forwards and writes
      no record, in `backend/tests/integration/git/test_git_live_remote.py`.

**Checkpoint**: a rewritten non-default branch is healthy again with no user action. SC-001 and
SC-003 hold.

---

## Phase 4: User Story 3 — one rewritten branch never blocks the others (P1)

**Goal**: a failed branch no longer suppresses the convergence broadcast for the healthy ones, and
the broadcast covers every branch the cycle advanced.

**Independent test**: make one branch of a repository fail during a cycle. The broadcast for the
healthy branch is still sent, and a second worker converges on it.

**Maps to**: FR-006, SC-005. Depends on Phase 3 for `ReconciledBranch`.

- [ ] T028 [US3] Add the optional `branches` field and its `BranchCommitPair` model to
      `backend/infrahub/message_bus/messages/refresh_git_fetch.py`, per
      [data-model.md](data-model.md), "Message change". A coalesced message still populates the
      required single-branch fields from its first pair.
- [ ] T029 [US3] Add a model validator to `RefreshGitFetch` asserting that
      `infrahub_branch_name`, `infrahub_branch_id` and `commit` equal the first entry of `branches`
      whenever `branches` is set. A worker on the previous code reads only the single-branch fields,
      so a mismatch converges it onto a branch the message was not about. PR #10669 is no precedent
      here: it sends one message per moved ref and adds no field, so this coalescing is new.
- [ ] T030 [US3] Read the list in
      `backend/infrahub/message_bus/operations/git/repository.py::fetch`. Reset every pair inside
      one lock acquisition and one fetch. Fall back to the single-branch fields when `branches` is
      absent. Log a failed pair with its branch and carry on with the rest.
- [ ] T031 [US3] Return a `SyncOutcome` from `backend/infrahub/git/sync.py::RepositorySyncer.sync`
      instead of raising. It carries the reconciled branches and the failures, per
      [contracts/internal-interfaces.md](contracts/internal-interfaces.md) section 4.
      **Update its other two callers in the same change**, or the API change loses behaviour that
      exists today. `git/tasks.py::sync_git_repo_with_origin_and_tag_on_failure` tags a failure from
      its `except`, which the return no longer reaches, and `git/tasks.py::add_git_repository` calls
      `sync` directly and would ignore a failed initial import in silence. Both must read the
      returned failures and act on them.
- [ ] T032 [US3] Broadcast before the raise in
      `backend/infrahub/git/tasks.py::sync_repository_from_origin`. Send one coalesced
      `RefreshGitFetch` covering every reconciled branch, then re-raise the failures of branches
      **other than** the configured default branch, which keeps today's failure tagging working.
      A failed default branch never leaves this flow: T033 owns it.
      **Keep sending the trunk message every cycle, even when no branch advanced.** That message is
      what heals a worker which missed an earlier broadcast, and its replacement is the pull-path
      reset in Phase 5. Dropping it here would leave a gap with no self-heal on either side.
- [ ] T033 [US3] Log a failed trunk reconciliation at error level and record it against the
      repository in `sync_repository_from_origin`, and do not retry it inside the same cycle
      (FR-018). Do **not** let it propagate: `sync_remote_repositories` loops over every repository
      with no per-repository `try`, so a raise would abort the cycle for every repository after it.
- [ ] T034 [US3] Wrap the per-repository call in
      `backend/infrahub/git/tasks.py::sync_remote_repositories` in its own `try`, so no failure in
      one repository can stop the others (FR-018a). This guard is missing today, independently of
      this feature.
- [ ] T035 [US3] Make the `fetch` handler's collaborators injectable before testing it. It reads
      the module-global `lock.registry` and calls `get_initialized_repo(get_client())`, neither of
      which a database-free, mock-free unit test can substitute.
- [ ] T036 [US3] Component-test that a failed trunk reconciliation is logged at error level and
      recorded against the repository, and that it does **not** propagate out of
      `sync_repository_from_origin` (FR-018).
- [ ] T037 [US3] Component-test that one repository failing does not stop the repositories after it
      in the same cycle (FR-018a). `sync_remote_repositories` has no per-repository guard today, so
      this test holds the one this phase adds. It is the repository-level version of the outage US3
      removes at branch level.
- [ ] T038 [P] [US3] Unit-test the handler fan-out in
      `backend/tests/unit/message_bus/test_refresh_git_fetch_fanout.py`: N pairs are reset inside
      one lock acquisition and one fetch. Use a fake lock registry, not a mock.
- [ ] T039 [US3] Component-test that `RepositorySyncer.sync` returns its outcome rather than
      raising, in `backend/tests/component/git/test_sync_repository.py`.
- [ ] T040 [US3] Add a live-remote test in
      `backend/tests/integration/git/test_git_live_remote.py`: a repository with one failing branch
      and one healthy branch still broadcasts for the healthy one, and a second worker converges on
      it.
      **This test needs the widened broadcast of T030, for the same reason T026 does.** The second
      worker converges on a branch that is not the trunk, which only the widened broadcast
      delivers.

**Checkpoint**: SC-005 holds. One developer's rebase is no longer a repository-wide event.

---

## Phase 5: User Story 2 — every worker converges, including one that heard nothing (P1)

**Goal**: every worker enforces reset-on-divergence on its own clone, so convergence does not
depend on a broadcast.

**Independent test**: reconcile a branch on one worker while a second receives no broadcast. Make
the second advance that branch worktree. It ends on the remote head, writes no rewrite record and
emits no signal.

**Maps to**: FR-005, FR-007, SC-004.

> **Check the merge order against PR #10542**, which rewrites `backend/infrahub/git/base.py`
> heavily. Landing #10542 first removes the trunk fallback this phase would otherwise inherit.

- [ ] T041 [US2] Reset on divergence in `backend/infrahub/git/base.py::InfrahubRepositoryBase.pull`,
      before the `origin.pull` call, per
      [contracts/internal-interfaces.md](contracts/internal-interfaces.md) section 3. The reset
      honours `update_commit_value` the same way the pull does.
- [ ] T042 [US2] Update the component test T023 rewrote, in
      `backend/tests/component/git/test_git_repository.py`. T023 leaves it asserting the corrected
      message on a diverged pull, which is right while `pull` still raises. This task makes `pull`
      reset instead, so the test now asserts the reset and that nothing is raised. Without it the
      test fails the moment this task lands.
- [ ] T043 [US2] Confirm by inspection that the pull path holds no reference to the recorder, so
      FR-007 holds by construction rather than by a runtime check. Record the finding in the task's
      commit message.
- [ ] T044 [US2] Guard **both sides** of the merge path (FR-005a, FR-005b, FR-005c): in
      `backend/infrahub/git/tasks.py::merge_git_repository`, fetch and compare the **source** branch
      and the **destination** branch against the remote before calling `repo.merge`. When either has
      diverged, compare the graph commit for that branch too. Refuse only when the **graph commit**
      is also stale, which is the case where merging would hide an unrecorded rewrite. When the
      graph already matches the remote and only this clone is behind, reset the worktree and merge:
      nothing is lost, and refusing there would refuse again on every retry, because the cron heals
      whichever worker runs it rather than the one the merge lands on. A refusal raises a typed
      error naming a divergent remote history.
      **In that refusing case, do not reset and merge instead.** `merge` pushes the merge commit
      before it records it on the destination, so a reset-then-merge puts the merge commit on the
      remote and in the graph. The next cycle then finds the graph and the remote in agreement,
      classifies `UNCHANGED`, and the rewrite is never recorded, never signalled and never
      re-imported. Resetting the source is worse: it merges objects the graph never imported.
      The source side is the dangerous one either way. `merge` reads the commit it merges from the
      local source ref via `get_commit_value(..., remote=False)`, and nothing fetches first, so a
      worker holding a stale source branch would merge the pre-rewrite history into the trunk and
      **push it**. A rewrite that removed a leaked credential would restore it.
- [ ] T045 [US2] Add the typed error for a divergent remote history to
      `backend/infrahub/exceptions.py` and map it in the error classifier, so the merge failure
      names the real cause and never says "conflict" (FR-003, FR-017).
- [ ] T046 [P] [US2] Add a live-remote test in
      `backend/tests/integration/git/test_git_live_remote.py`: a worker whose destination worktree
      holds a discarded history refuses the merge instead of merging onto it.
- [ ] T047 [US2] Add a live-remote test for the source side, in the same file: a worker holding a
      stale **source** branch refuses the merge, and the discarded commits do not reappear on the
      remote. This is the security-relevant half of FR-005a.
- [ ] T048 [US2] Add a live-remote test that the refused merge leaves the rewrite recordable: after
      the refusal, the next synchronisation cycle reconciles the branch, writes the record and fires
      the trunk signal. This is what a reset-then-merge would have destroyed (FR-005c).
- [ ] T049 [US2] Add a live-remote test that a worker which missed the broadcast resets and records
      nothing, while the graph already holds the remote commit (FR-001c). This is the case that
      decides whether the classification reads the graph or the worktree.
- [ ] T050 [P] [US2] Component-test the reset in
      `backend/tests/component/git/test_git_repository.py`: a diverged branch worktree is reset to
      the remote head by `pull`, and nothing is raised.
- [ ] T051 [US2] Add a live-remote test in
      `backend/tests/integration/git/test_git_live_remote.py`: a worker that received no broadcast
      converges on first contact, writes no rewrite record and emits no signal.
- [ ] T052 [P] [US2] Add a live-remote test that a worker which has never seen the repository
      clones fresh and needs no reset, in
      `backend/tests/integration/git/test_git_live_remote.py`.

**Checkpoint**: SC-004 holds. Convergence no longer depends on who was listening.

---

## Phase 6: User Story 1, recording (P1)

**Goal**: the reconciliation is recorded as four branch-local attributes on the repository generic.

**Maps to**: FR-010, FR-011, FR-012, FR-013, SC-006.

> **Gated on schema and GraphQL sign-off.** Both are "Ask First" changes under `AGENTS.md`. The
> design is complete in [data-model.md](data-model.md) and
> [contracts/repository_rewrite.graphql](contracts/repository_rewrite.graphql).

- [ ] T053 [US1] Declare the four attributes on `CoreGenericRepository` in
      `backend/infrahub/core/schema/definitions/core/repository.py`:
      `last_rewrite_previous_commit` (`Text`), `last_rewrite_commit` (`Text`), `last_rewrite_at`
      (`DateTime`) and `rewrite_count` (`Number`). All optional, no default, all
      `BranchSupportType.LOCAL`. Do not override them on `CoreRepository` or
      `CoreReadOnlyRepository`.
- [ ] T054 [US1] Regenerate the generated files for the four attributes and commit them:
      `uv run invoke backend.generate`, `uv run invoke schema.generate-graphqlschema`,
      `uv run invoke schema.generate-jsonschema`, `uv run invoke docs.generate`, and
      `cd frontend/app && pnpm codegen`. CI fails when any of them is stale.
      Phase 7 adds an `EventType` member, which feeds the webhook `event_type` enum and makes these
      same files stale again. That phase regenerates them a second time.
- [ ] T055 [US1] Write `HistoryRewriteRecorder` in
      `backend/infrahub/git/divergence/recorder.py`, per
      [contracts/internal-interfaces.md](contracts/internal-interfaces.md) section 2. Take its two
      collaborators as constructor-injected protocols, `RepositoryRecordStore` and
      `RewriteEventEmitter`, so the unit tests of T059 need no database and no mocks
      (`.agents/rules/backend-component-design.md`). The recorder itself imports neither the SDK
      nor the event service, and it never reads the cache.
- [ ] T056 [US1] Isolate the record write per branch, the way the other per-branch git failures
      already are. `collect_pending_imports` lets graph errors propagate, so an SDK error from the
      store would otherwise abort collection for every branch and skip the broadcast. A failed
      record joins `failed_imports` and the cycle continues.
- [ ] T057 [US1] Call the recorder from
      `backend/infrahub/git/repository.py::InfrahubRepository.collect_pending_imports`, immediately
      after the reconciled commit is written for that branch, inside the collection lock hold. The
      count increment is safe there because it is inside a lock hold; what is unsafe is a call
      placed *between* the two acquisitions. Do **not** move it after `apply_branch_import`: the
      commit is already written by then, so a failed import would leave the next cycle classifying
      `UNCHANGED` and the rewrite would never be recorded at all. See
      [contracts/internal-interfaces.md](contracts/internal-interfaces.md) section 2, "Where it is
      called".
- [ ] T058 [US1] Write the production `RepositoryRecordStore` in
      `backend/infrahub/git/divergence/store.py`, backed by the SDK node API. It reads
      `rewrite_count` and writes the four attributes in one call, so the `python_sdk` submodule
      needs no change.
- [ ] T059 [P] [US1] Unit-test the recorder in
      `backend/tests/unit/git/divergence/test_recorder.py` against in-memory ports: last-write-wins,
      the increment from absent to 1 and 1 to 2, a `RETARGET`, a `FAST_FORWARD` and a
      `REMOTE_ABSENT` each writing nothing, and a rejected divergence whose two commits are equal.
      No database, no mocks.
- [ ] T060 [US1] Component-test the read inheritance in
      `backend/tests/component/git/test_repository_rewrite_branch_safety.py`: a branch created
      after the default branch was reconciled reads the default branch's four values, and its own
      first reconciliation increments the count it inherited. This is what LOCAL does, and the
      test exists so nobody meets it in production. See [data-model.md](data-model.md), "What LOCAL
      does not do".
- [ ] T061 [US1] Add the branch-safety test, in the same file as T060, in
      `backend/tests/component/git/test_repository_rewrite_branch_safety.py`: the four attributes
      appear in no branch diff on `CoreRepository` or `CoreReadOnlyRepository`, and merging a
      branch that carries a record does not carry it to the destination. The constitution's
      branch-safe principle requires this to be asserted rather than inferred from the declaration.
- [ ] T062 [US1] Assert that `sync_status` is unchanged by a reconciliation (FR-013). The record is
      four attributes of its own, and folding any of it into the synchronisation status would take
      that status away from INFP-671, which is free to redefine it.
- [ ] T063 [US1] Add a live-remote test asserting the record's contents after a rewrite, in
      `backend/tests/integration/git/test_git_live_remote.py`.

**Checkpoint**: SC-006 holds for the stored state. The human-facing view is INFP-671's.

---

## Phase 7: User Story 4 — a rewritten trunk is reconciled and announced (P2)

**Goal**: a rewrite of the configured default branch reconciles identically and emits at most one
outbound signal, never more.

**Independent test**: rewrite the trunk of a tracked repository on a live remote. Run several
cycles. The record written once, the signal emitted once, never twice, and a healthy repository.

**Maps to**: FR-014, SC-002.

> **Gated on the FR-014 consumer being confirmed.** The design says the webhook subsystem. See
> [research.md](research.md) R8. Patrick may prefer a built-in notification surface, or deferring
> the signal to INFP-671.

- [ ] T064 [US4] Add `RepositoryHistoryRewrittenEvent` to
      `backend/infrahub/events/repository_action.py` and export it from
      `backend/infrahub/events/__init__.py`, per [data-model.md](data-model.md), "New event".
- [ ] T065 [US4] Add the matching member to
      `backend/infrahub/core/constants/__init__.py::EventType`. That is what puts it in the
      `event_type` enum of `CoreStandardWebhook` and `CoreCustomWebhook`, which is the consumer.
      **This is itself a schema change.** `EventType.available_types()` feeds that enum, so the
      generated schema, the GraphQL schema and the frontend types all go stale the moment it lands.
- [ ] T066 [US4] Regenerate after the member lands, not before:
      `uv run invoke backend.generate`, `uv run invoke schema.generate-graphqlschema`,
      `uv run invoke schema.generate-jsonschema`, `uv run invoke docs.generate`, and
      `cd frontend/app && pnpm codegen`. Running the regen in Phase 6 and then adding the member
      here ships a stale schema.
- [ ] T067 [US4] Emit the event from `HistoryRewriteRecorder` in
      `backend/infrahub/git/divergence/recorder.py`, after a successful record, and only when the
      reconciled branch is the repository's configured default branch.
- [ ] T068 [US4] Confirm the events reference documentation regenerated by T066 is committed.
- [ ] T069 [P] [US4] Unit-test the emission rule in
      `backend/tests/unit/git/divergence/test_recorder.py`: the trunk emits the event once, and any
      other branch emits none.
- [ ] T070 [US4] Add a live-remote test in
      `backend/tests/integration/git/test_git_live_remote.py`: a rewritten trunk produces exactly
      at most one record and at most one signal **across several synchronisation cycles**, never two. One cycle is not
      enough, because a single-cycle test would pass while the exactly-once property is broken.
- [ ] T071 [US4] Add a live-remote test that wires a webhook to the new event and asserts exactly
      one delivery per rewrite, in `backend/tests/integration/git/test_git_live_remote.py`. This
      test is what holds the wiring, so the event cannot become a dead one.

**Checkpoint**: SC-002 holds.

---

## Phase 8: User Story 5 — a read-only repository records the lineage break (P2)

**Goal**: a read-only repository whose tracked ref resolves to a non-descendant commit records the
break and is never reset.

**Independent test**: force-push a **branch** on a live remote that a read-only repository tracks.
Update the commit. The import happened, the record was written, and no reset ran. A moved tag
cannot be used: the read-only fetch omits `--force`, so git rejects the tag update and exits 1,
which fails the fetch instead of producing a lineage break.

**Maps to**: FR-009.

**Depends on Phase 9's in-band flag.** The flow this phase classifies in is submitted by two
different mutations, one of which is a deliberate re-point, so the flag has to exist before the
classification can tell them apart.

> **Attachment point depends on PR #10669 reaching `develop`.** It is merged, but into
> `pog-repo-commit-visibility-ifc-3101`, which has not landed. If it is on `develop`, attach to
> `backend/infrahub/git/refs_check/checker.py::ReadOnlyRepositoryRefsChecker._detect_movements`,
> whose `RefMovement` already carries the two commits the ancestry test needs. If it has not,
> attach to
> `backend/infrahub/git/repository.py::InfrahubReadOnlyRepository.update_latest_commit`. The record
> and the precondition are identical either way. See [research.md](research.md) R10.

- [ ] T072 [US5] Classify the resolved commit against the graph commit in
      `backend/infrahub/git/tasks.py::import_read_only_repository_last_commit`, and call the
      recorder on a `REWRITE`. Perform no reset (FR-009).
      **Take `target_changed` from the model, never from the fact that this flow is running.** Two
      mutations submit it: `ReadOnlyRepositoryImportLastCommit` for an ordinary pick-up, and
      `InfrahubRepositoryMutation.mutate_update` on every `ref` or `commit` change, which is a
      deliberate re-point. See the table in
      [contracts/internal-interfaces.md](contracts/internal-interfaces.md) section 7.
      **The in-band flag in Phase 9 is a prerequisite for this task**, not a follow-up. Landing the
      classification first records a false rewrite on every read-only re-point.
- [ ] T073 [US5] Confirm the import path is unchanged: detection changes what is recorded, never
      what is imported.
- [ ] T074 [P] [US5] Component-test the read-only classification in
      `backend/tests/component/git/test_readonly_rewrite.py`.
- [ ] T075 [US5] Read the previously imported commit from the graph **inside the repository lock**,
      in `backend/infrahub/git/tasks.py::import_read_only_repository_last_commit`, which already
      takes that lock around `update_latest_commit`. Do not read it in the mutation and carry it on
      the model: that read is outside the lock, so two queued runs both carry the same old commit,
      both classify `REWRITE` and both record, and the count rises twice for one rewrite.
- [ ] T076 [US5] Add a live-remote test in
      `backend/tests/integration/git/test_git_live_remote.py`, which is where the Gogs harness and
      `readonly_sync_dataset` live: a **force-pushed branch** tracked by a read-only repository
      writes the record and performs no reset. Do not use a moved tag: the read-only fetch omits
      `--force`, so git rejects the update with "would clobber existing tag" and exits 1. That fails
      the fetch rather than producing a lineage break. IFC-2874 fixes the flag and is out of scope.
      `test_readonly_repository.py` has no live remote.

**Checkpoint**: the quietest repository type is no longer the least honest one.

---

## Phase 9: User Story 6 — a deliberate change of target is not a rewrite (P2)

**Goal**: re-pointing a repository at a different branch, tag or commit records nothing.

**Independent test**: change a read-only repository's tracked ref to a different tag, and edit a
read-write repository's configured default branch. Neither writes a record.

**Maps to**: FR-002, SC-007.

- [ ] T077 [US6] Write the suppression marker's read and write in
      `backend/infrahub/git/divergence/suppression.py`, per [data-model.md](data-model.md),
      "Cache key". Reading and deleting are separate steps: the delete happens only after the
      commit write for that branch succeeds.
- [ ] T078 [US6] Set the in-band `target_changed` flag from
      `backend/infrahub/graphql/mutations/repository.py::InfrahubRepositoryMutation.mutate_update`
      when `CoreReadOnlyRepository.ref` changes **or when only `commit` changes**. It already
      computes both comparisons. SC-007 covers re-pointing to "a different branch, tag or commit",
      so leaving the commit-only case out records a false rewrite. Read-only repositories write no
      cache marker.
- [ ] T079 [US6] Add the `default_branch` comparison to the same method for `CoreRepository`, and
      write the marker for Infrahub's default branch. **This comparison does not exist yet**: the
      method returns to `super().mutate_update` immediately for any kind other than read-only, so
      the comparison goes before that early return.
- [ ] T080 [US6] Carry the read-only re-target **in band** instead of through the cache: add an
      explicit `target_changed` flag to `GitRepositoryPullReadOnly` and
      `GitReadOnlyRepositoryImportCommit`, set from the comparison the mutation already computes.
      That removes the marker from the read-only path entirely, with no expiry and no timing
      question. The cache marker then covers read-write repositories only.
      Do **not** try to submit a per-repository sync to make the read-write marker readable. There
      is no such workflow: `GIT_REPOSITORIES_SYNC` is one cron flow over every repository, with
      `concurrency_limit=1` and `CANCEL_NEW`. The widened candidate set of T016 is what makes it
      readable, within one cycle.
- [ ] T081 [US6] Sweep any marker still held for a repository when the cycle finishes with it. A
      re-point can leave the graph commit and the worktree both equal to the remote head, so the
      branch enters no candidate set and nothing reads the marker. Left in place it would turn a
      genuine trunk rewrite into a `RETARGET` for the rest of its hour: reset, no record, no trunk
      webhook. The sweep bounds every marker to one cycle.
- [ ] T082 [US6] Read the marker at classification time, and delete it only after the commit write
      for that branch succeeds, in the two components that call the
      detector: `collect_pending_imports` reads the cache marker for read-write, and the read-only
      detection point of T072 reads the in-band flag from its workflow model. Pass either as
      `target_changed`. The recorder must **not** read the cache: it
      returns early on any classification other than `REWRITE`, so a marker read there would never
      be consumed on a `RETARGET` and would go on to suppress the next genuine rewrite.
- [ ] T083 [P] [US6] Unit-test the suppression in
      `backend/tests/unit/git/divergence/test_suppression.py`: a present marker yields
      `target_changed` true and is gone afterwards, and an absent marker yields false. Both
      directions are asserted, so the behaviour is stated rather than assumed. Assert the marker is
      consumed exactly once, which is what stops it suppressing a later genuine rewrite.
- [ ] T084 [US6] Component-test both re-point paths in
      `backend/tests/component/graphql/mutations/test_repository.py`: a `CoreRepository`
      `default_branch` edit writes the cache marker before the workflows are submitted, and a
      read-only `ref` or `commit` change sets `target_changed` on the workflow model and writes no
      marker.
- [ ] T085 [US6] Add a **multi-cycle** live-remote test for a `default_branch` edit: change the
      configured default branch, then run several synchronisation cycles. Assert that no record is
      written and no trunk event fires on **any** cycle, not only the first. One cycle passes while
      the bug is present: the marker suppresses cycle 1, and cycles 2 onward are what record a false
      rewrite and fire a false trunk webhook once a minute.
- [ ] T086 [US6] Add a live-remote test in
      `backend/tests/integration/git/test_git_live_remote.py`, beside the other live-remote tests:
      changing the tracked ref to a different branch records nothing.

**Checkpoint**: SC-007 holds. Routine re-pointing produces no noise.

---

## Phase 10: Documentation and polish

**Purpose**: correct what is wrong in the knowledge docs today, and describe what shipped.

- [ ] T087 State in `dev/knowledge/backend/git-integration.md`, "How the workers converge",
      that the periodic sync's broadcast covered only the trunk or the staging branch and that a
      failed branch suppressed it, and that this feature changes both.
- [ ] T088 [P] Correct the "Key Files" table in
      `dev/knowledge/backend/merge-failure-recovery.md`. It attributes the merge-start logic to
      `core/branch/tasks.py::_do_merge_branch`. That logic now lives in
      `core/merge/orchestrator.py`. Check the surrounding prose for the same claim.
- [ ] T089 Rewrite **two** of the four "Volatile section" notes in
      `dev/knowledge/backend/git-integration.md`. The one under "How git errors are classified"
      describes this feature as planned; it now describes what shipped: the ancestry detection, the
      pull-path reset, the widened broadcast and the record. The one on the merge ordering
      describes push-before-graph-write as intended, and IFC-1449 shipped it, so the section it
      sits in, "The writeback direction has no reconciliation", is stale around it. Correct the
      note and that section together. Its first bullet still states that
      `InfrahubRepository.merge` writes the new commit to the graph before pushing. Its third
      bullet, "Re-running the merge no-ops", still describes a local merge commit that stays on
      disk after a rejected push, which the reset now removes, so a retry re-derives the merge and
      reaches the push again. The paragraph below the bullets still claims a merge commit "exists
      on exactly one worker's disk". Leave the second bullet, "Nothing ever re-pushes", as it is.
      Leave the other two volatile notes alone: they cover the trunk fallback (PR #10542) and the
      persisted writeback state (IFC-3220). Rewriting those would claim two other fixes shipped.
      Correct the Known limitation in the same file as well, the one that says a branch left ahead
      of its remote is re-reported every cycle because `pull()` returns `True` with no change. The
      reset now reads the worktree against the remote head and does nothing when the remote head is
      an ancestor of the worktree, so that branch is no longer pulled and the once-a-minute log
      line stops.
- [ ] T090 [P] Document the two limitations under `docs/docs/git-integration/`, which is the
      published section. Do not edit `docs/archive/topics/repository.mdx`: neither
      `docusaurus.config.ts` nor `sidebars.ts` references it, so an edit there ships nothing. The
      two limitations are: rewriting
      history means content at discarded commits can no longer be reliably re-derived, and schema
      already applied to a branch is not rewound.
- [ ] T091 [P] Document the accepted failure mode of the suppression marker in
      `dev/knowledge/backend/git-sync.md`: a cache flush between the re-target mutation and the
      reconciliation records the re-point as a rewrite, leaves the count one too high, and **fires
      the trunk webhook**, so a subscriber sees a security-remediation notice for an ordinary
      configuration change. The reconciliation itself is identical either way.
- [ ] T092 Add a towncrier changelog fragment under `changelog/`. This is a user-visible change.
      Use the `creating-changelog-entries` skill. Filename: the convention is a bare GitHub issue
      number when the release note should link that issue, and a `+slug` otherwise. The epic lists
      #6299 under "Advances", not "Closes", so a slug is the safer default. Confirm with Patrick
      whether this closes #6299; if it does, the stem is `6299`.
- [ ] T093 Add the end-to-end scenario under `tests/e2e/`: a developer rebases a branch Infrahub
      tracks and force-pushes it. The branch keeps synchronising, its imported objects match the
      rewritten history, and the repository reports healthy throughout. The constitution requires
      an E2E test for a user-facing feature, and the PRD names this scenario. Run it with `--pdb`
      while developing it; a failure then freezes the session with the stack and every fixture
      alive.
- [ ] T094 Test that Infrahub never force-pushes (FR-008). Assert that no call site under
      `backend/infrahub/git/` passes a force flag to a push, and add a live-remote test that
      reconciling a rewritten branch leaves the remote head untouched. Reconciliation is inbound
      only, and nothing held that requirement before this task.
- [ ] T095 Run `/pre-ci`. It covers the whole-repository `ruff check . --exclude python_sdk` and
      `ruff format --check` that `invoke lint` misses, plus `docs.validate` for the generated
      documentation. CI fails on any of them.
- [ ] T096 Get an independent review before the PR leaves draft. A session that wrote the code
      cannot review it: it knows the intent, so it confirms its own assumptions instead of testing
      them.

---

## Dependencies

```text
Phase 1 (Setup)
  └─> Phase 2 (Foundational: the classifier)
        ├─> Phase 3 (US1: reconcile in the sync path)
        │     ├─> Phase 4 (US3: broadcast every branch, before the raise)
        │     └─> Phase 6 (US1: record)  [needs schema sign-off]
        │           ├─> Phase 7 (US4: the trunk signal)  [needs the consumer confirmed]
        │           └─> Phase 9 (US6: re-target suppression)
        │                 └─> Phase 8 (US5: read-only)  [needs Phase 9's in-band flag]
        └─> Phase 5 (US2: self-heal in the pull path)

Phase 10 (Documentation) follows whatever has landed.
```

### Why every reset here is safe

**Every step in this plan that resets a worktree.** That is the whole of Phase 5, the reset inside
the sync-path task in Phase 3, and the widened broadcast in Phase 4, which makes the convergence
handler reset every branch on every other worker rather than only the trunk.

The one state that would make such a reset lossy is a merge commit that exists on a single worker's
disk and nowhere else. `InfrahubRepository.merge` no longer leaves it: it pushes the merge commit,
records it second, and resets the destination worktree to its pre-merge commit when either step
fails. A rejected push leaves the destination either at its pre-merge state, where a later attempt
re-derives the merge, or trailing the remote, which the periodic synchronisation repairs. That
ordering arrived with IFC-1449.

The reset rule still earns its place. It reads this worker's worktree against the remote head and
does nothing when the remote head is an ancestor of the worktree, so a branch merely ahead of its
remote resets nothing, whatever put it there. Treat that row as a correctness rule in the reset,
not as cover for the merge path.

The Gogs harness, `_push_commit_to_remote` and the two `pre-receive` hook helpers are already on
`develop`. The force-push helper is not. T012 adds it.

Inside Phase 3, T016 (build the candidate set), T017 (classify), T020 and T021 to T024 change no
worktree. T026 asserts that a rewritten branch reconciles, which only T018 delivers, so it moves
with T018 rather than shipping with the rest of the phase.

### What waits for a person

| Tasks | Waiting on | Who |
|---|---|---|
| Phase 5 | The merge order agreed against PR #10542 | Patrick Ogenstad |
| Phase 6 | Schema and GraphQL sign-off | A maintainer |
| Phase 7 | The FR-014 consumer confirmed | Patrick Ogenstad |
| Phase 8 | Whether to wait for PR #10669 to reach `develop` | Patrick Ogenstad |

---

## Parallel opportunities

| Phase | Tasks that can run together |
|---|---|
| 1 | T003, T004 |
| 2 | T005, T006 then T010, T011 |
| 3 | T013 with T012; T024 with T023. T026 and T027 both write `test_git_live_remote.py`, so they are sequential. |
| 4 | T038 alone, once T028 and T030 are done |
| 5 | T050 and T052 |
| 6 | T059 alone, once T055 and T058 are done. T060 and T061 both write `test_repository_rewrite_branch_safety.py`, so they are sequential. |
| 7 | T069 alone, once T067 is done |
| 8 | T074 alone, once T072 is done |
| 9 | T083 alone, once T077 is done |
| 10 | T088, T090, T091. The two tasks editing `git-integration.md` are sequential. |

---

## Implementation strategy

**Minimum viable increment**: Phases 1, 2 and 3. Those phases fix the
reported bug: a rewritten non-default branch stops being stuck, stops being described as a conflict,
and returns to a healthy state with no user action. They ship without the schema change and
without the signal.

**Second increment**: Phase 4. It removes the outage half of the bug, where one branch's failure
stops every other branch converging. It also needs no schema change.

**Third increment**: Phase 6, once the schema is signed off. Until then the reconciliation works but
leaves no trace.

**Then**: Phases 5, 7, 8 and 9 in any order, each behind its own gate.

**Test discipline**: every test here uses testcontainers. The classifier and the recorder are
unit-testable without a database, which is what makes the no-mocking rule practical. The negative
cases carry as much weight as the positive ones: a fast-forward and a deliberate re-target must
both come out clean.

---

## Task count

| Phase | Tasks |
|---|---|
| 1 Setup | 4 |
| 2 Foundational | 7 |
| 3 US1 reconcile | 16 |
| 4 US3 broadcast | 13 |
| 5 US2 self-heal | 12 |
| 6 US1 record | 11 |
| 7 US4 trunk signal | 8 |
| 8 US5 read-only | 5 |
| 9 US6 re-target | 10 |
| 10 Documentation and polish | 10 |
| **Total** | **96** |
