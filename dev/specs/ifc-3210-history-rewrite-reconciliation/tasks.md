---

description: "Task list for Git history-rewrite reconciliation (IFC-3210)"
---

# Tasks: Git history-rewrite reconciliation

**Input**: Design documents from `dev/specs/ifc-3210-history-rewrite-reconciliation/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/)

**Branch**: `history-rewrite-reconciliation-ifc-3210`, based on
`origin/pog-fix-merge-push-ordering-IFC-1449`

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
| **PR #10465 merged into `develop` and forward-merged** | Phase 5 in full, the reset inside the sync-path task in Phase 3, and the widened broadcast in Phase 4. | Patrick Ogenstad |
| **Schema and GraphQL sign-off** ("Ask First" under `AGENTS.md`) | Phase 6 | A maintainer |
| **The FR-014 consumer confirmed** | Phase 7 | Patrick Ogenstad |
| **Merge order agreed against PR #10542** | Phase 5 | Patrick Ogenstad |
| **Whether to wait for PR #10669** | Phase 8, and only which file it attaches to | Patrick Ogenstad |

---

## Phase 1: Setup

**Purpose**: prepare the worktree so the tests can run at all.

- [ ] T001 Initialise the submodules in this worktree and reinstall the SDK in editable mode, so
      `backend/tests/` can import `infrahub_sdk`. Run `git submodule update --init --recursive`
      then `uv sync --all-groups`.
- [ ] T002 Confirm the test environment is clean: unset every `INFRAHUB_*` variable inherited from
      the dev shell, then set `INFRAHUB_USE_TEST_CONTAINERS=1`. A leftover
      `INFRAHUB_USE_TEST_CONTAINERS=false` sends the suite at an external Neo4j. See
      [quickstart.md](quickstart.md).
- [ ] T003 [P] Create the package `backend/infrahub/git/divergence/` with an empty `__init__.py`.
- [ ] T004 [P] Create the test package `backend/tests/unit/git/divergence/` with an empty
      `__init__.py`.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: the classification every user story reads. Slice A of the plan.

**Blocks**: every phase from 3 onwards.

- [ ] T005 [P] Define `RefClassification` and `RefDivergence` in
      `backend/infrahub/git/divergence/models.py`, per
      [data-model.md](data-model.md), "New in-process types". `RefClassification` is a `StrEnum`
      with `UNCHANGED`, `FAST_FORWARD`, `LOCAL_AHEAD`, `REWRITE`, `RETARGET` and `REMOTE_ABSENT`.
      `RefDivergence` holds a nullable `remote_head` and enforces the three validation rules in
      that section.
- [ ] T006 [P] Define `ReconciledBranch` in `backend/infrahub/git/divergence/models.py`. It carries
      the Infrahub branch name, the branch UUID, the commit, and an optional `RefDivergence`.
- [ ] T007 Write the ancestry gateway in `backend/infrahub/git/divergence/gateway.py`. It exposes
      `is_ancestor` as a `Protocol` plus a GitPython implementation over `Repo.is_ancestor`. Every
      git failure leaves as a `RepositoryError`, so the detector imports no git library. Mirror the
      shape of `backend/infrahub/git/refs_check/gateway.py` from PR #10669.
- [ ] T008 Write `RemoteDivergenceDetector.classify` in
      `backend/infrahub/git/divergence/detector.py`, per
      [contracts/internal-interfaces.md](contracts/internal-interfaces.md) section 1. It takes
      `target_changed` from its caller and never reads the cache itself.
- [ ] T009 [P] Write unit tests for the detector in
      `backend/tests/unit/git/divergence/test_detector.py`. Cover every row of the contract table.
      The negative cases carry the most weight: a fast-forward, a deliberate re-target, a branch
      that is only ahead of its remote, and an absent remote ref must all come out clean. The
      locally-ahead case is the one that would discard an unpushed commit if it were wrong, so
      assert it names `LOCAL_AHEAD` and not `REWRITE`. No database.
- [ ] T010 [P] Write unit tests for the models in
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

- [ ] T011 [US1] Add a force-push helper to
      `backend/tests/integration/git/test_git_live_remote.py`, beside the existing
      `_push_commit_to_remote` and the two hook helpers, which all live in that module and not in
      `conftest.py`. It builds a divergent history inside the Gogs container and pushes it with
      `--force`.
- [ ] T012 [P] [US1] Add a fixture that creates a Gogs repository with a tracked non-default branch
      already imported, in `backend/tests/integration/git/conftest.py`. The rewrite tests all start
      from that state.

### Implementation

- [ ] T013 [US1] Classify the staging-mode trunk pull too, in
      `backend/infrahub/git/repository.py::InfrahubRepository._collect_staging_imports`. It calls
      `self.pull(branch_name=self.default_branch)` outside the `ACTIVE` loop, so a rewritten trunk
      on a staging repository would be neither classified nor recorded, and before T034 would still
      fail with the old message. No spec file mentioned this path before this task.
- [ ] T014 [US1] Pass the per-branch graph commits into
      `backend/infrahub/git/repository.py::InfrahubRepository.collect_pending_imports`.
      `sync_repository_from_origin` already holds them on `RepositoryData.branches`, loaded once per
      cycle by `get_repositories_commit_per_branch`. The collector has no graph read of its own, and
      `get_commit_value` reads git rather than the graph, so without this the classifier has no
      input (FR-001b).
- [ ] T015 [US1] Classify the `updated_branches` list in `collect_pending_imports`, after `fetch()`
      and before the per-branch `pull()`, **using the graph commit** as `imported_commit` and never
      the local worktree head. Keep the existing per-branch failure isolation: a branch that fails
      classification joins `failed_imports` and the cycle continues. See
      [contracts/internal-interfaces.md](contracts/internal-interfaces.md) section 1, "Two
      comparisons, not one".
- [ ] T016 [US1] Reset a `REWRITE` branch to the remote head in `collect_pending_imports` instead of
      pulling it, then record the commit and pin the commit worktree exactly as the fast-forward
      path already does. Reset on `REWRITE` **and on `RETARGET`**: both leave the branch on a
      history the remote no longer has, and both must end on the remote head. Only `REWRITE` goes
      on to the recorder. A `LOCAL_AHEAD` or `REMOTE_ABSENT` branch keeps today's behaviour and is
      never reset. See the decision table in
      [contracts/internal-interfaces.md](contracts/internal-interfaces.md) section 1.
      **This reset is gated on PR #10465** for the same reason T034 is: a branch that is both ahead
      locally and rewritten remotely classifies `REWRITE`, and resetting it discards the unpushed
      merge commit. The rest of T015 to T023 is not gated.
- [ ] T017 [US1] Return `ReconciledBranch` entries from `collect_pending_imports`, so the syncer and
      then the broadcast can name every branch the cycle advanced.
- [ ] T018 [US1] Give the divergent-branches case its own message in
      `backend/infrahub/git/base.py::InfrahubRepositoryBase._raise_enriched_error_static`. It names
      a divergent history and does not use the word "conflict" (FR-003, FR-017).
- [ ] T019 [US1] Log each reconciliation in `collect_pending_imports` with the repository, the
      branch, the discarded commit and the new commit (FR-019).

### Tests

- [ ] T020 [US1] Rename `backend/tests/component/git/test_git_repository.py::test_pull_branch_conflict`
      and change it to assert the corrected message: a diverged pull names a divergent history and
      never says "conflict" (FR-003, FR-017). **Do not** assert that `pull` resets the branch here.
      That behaviour is built in Phase 5 and is gated on #10465, so asserting it in Phase 3 fails.
      The reset assertion belongs to the Phase 5 component test, which is its only home.
- [ ] T021 [P] [US1] Leave the `"Need to specify how to reconcile"` parameter in
      `backend/tests/integration/git/test_repository.py::test_repository_operational_status`
      **unchanged**. It is the stderr the test injects into `GitCommandError`, not a message the
      test asserts, and git still emits that text. Replacing it with Infrahub's new wording would
      make the classifier fall through to its generic branch, which still yields `ERROR`, so the
      test would keep passing while no longer exercising the divergent-branches case at all.
      Instead, add an assertion that the resulting message does not contain the word "conflict"
      (FR-003, SC-003).
- [ ] T022 [US1] Add a live-remote test in
      `backend/tests/integration/git/test_git_live_remote.py`: a rewritten non-default branch
      reconciles and re-imports, and the repository reports healthy.
- [ ] T023 [US1] Add a live-remote test asserting a fast-forward still fast-forwards and writes
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

- [ ] T024 [US3] Add the optional `branches` field and its `BranchCommitPair` model to
      `backend/infrahub/message_bus/messages/refresh_git_fetch.py`, per
      [data-model.md](data-model.md), "Message change". A coalesced message still populates the
      required single-branch fields from its first pair.
- [ ] T025 [US3] Read the list in
      `backend/infrahub/message_bus/operations/git/repository.py::fetch`. Reset every pair inside
      one lock acquisition and one fetch. Fall back to the single-branch fields when `branches` is
      absent. Log a failed pair with its branch and carry on with the rest.
- [ ] T026 [US3] Return a `SyncOutcome` from `backend/infrahub/git/sync.py::RepositorySyncer.sync`
      instead of raising. It carries the reconciled branches and the failures, per
      [contracts/internal-interfaces.md](contracts/internal-interfaces.md) section 4.
- [ ] T027 [US3] Broadcast before the raise in
      `backend/infrahub/git/tasks.py::sync_repository_from_origin`. Send one coalesced
      `RefreshGitFetch` covering every reconciled branch, then raise for the failures. Send nothing
      when the cycle advanced no branch.
- [ ] T028 [US3] Log a failed trunk reconciliation at error level and record it against the
      repository in `sync_repository_from_origin`, and do not retry it inside the same cycle
      (FR-018). Do **not** let it propagate: `sync_remote_repositories` loops over every repository
      with no per-repository `try`, so a raise would abort the cycle for every repository after it.
- [ ] T029 [US3] Wrap the per-repository call in
      `backend/infrahub/git/tasks.py::sync_remote_repositories` in its own `try`, so no failure in
      one repository can stop the others (FR-018a). This guard is missing today, independently of
      this feature.
- [ ] T030 [US3] Make the `fetch` handler's collaborators injectable before testing it. It reads
      the module-global `lock.registry` and calls `get_initialized_repo(get_client())`, neither of
      which a database-free, mock-free unit test can substitute.
- [ ] T031 [P] [US3] Unit-test the handler fan-out in
      `backend/tests/unit/message_bus/test_refresh_git_fetch_fanout.py`: N pairs are reset inside
      one lock acquisition and one fetch. Use a fake lock registry, not a mock.
- [ ] T032 [US3] Component-test that `RepositorySyncer.sync` returns its outcome rather than
      raising, in `backend/tests/component/git/test_sync_repository.py`.
- [ ] T033 [US3] Add a live-remote test in
      `backend/tests/integration/git/test_git_live_remote.py`: a repository with one failing branch
      and one healthy branch still broadcasts for the healthy one, and a second worker converges on
      it.

**Checkpoint**: SC-005 holds. One developer's rebase is no longer a repository-wide event.

---

## Phase 5: User Story 2 — every worker converges, including one that heard nothing (P1)

**Goal**: every worker enforces reset-on-divergence on its own clone, so convergence does not
depend on a broadcast.

**Independent test**: reconcile a branch on one worker while a second receives no broadcast. Make
the second advance that branch worktree. It ends on the remote head, writes no commit to the graph,
and emits no report.

**Maps to**: FR-005, FR-007, SC-004.

> **Gated on PR #10465.** Do not start T034–T042 until the writeback ordering fix has merged into
> `develop` and this branch has been forward-merged. Without it, an unconditional reset can
> silently discard a merge commit that exists on one worker only.
>
> **Also check the merge order against PR #10542**, which rewrites `backend/infrahub/git/base.py`
> heavily. Landing #10542 first removes the trunk fallback this phase would otherwise inherit.

- [ ] T034 [US2] Reset on divergence in `backend/infrahub/git/base.py::InfrahubRepositoryBase.pull`,
      before the `origin.pull` call, per
      [contracts/internal-interfaces.md](contracts/internal-interfaces.md) section 3. The reset
      honours `update_commit_value` the same way the pull does.
- [ ] T035 [US2] Confirm by inspection that the pull path holds no reference to the recorder, so
      FR-007 holds by construction rather than by a runtime check. Record the finding in the task's
      commit message.
- [ ] T036 [US2] Guard **both sides** of the merge path (FR-005a, FR-005b): fetch, then run the
      ancestry check on the **source** branch and on the **destination** branch in
      `backend/infrahub/git/tasks.py::merge_git_repository` before calling `repo.merge`. Reset
      either worktree when neither head is an ancestor of the other.
      The source side is the dangerous one. `merge` reads the commit it merges from the local source
      ref via `get_commit_value(..., remote=False)`, and nothing fetches first, so a worker holding
      a stale source branch merges the pre-rewrite history into the trunk and **pushes it**. That
      puts discarded commits back on the remote for everyone. A rewrite that removed a leaked
      credential would restore it.
- [ ] T037 [P] [US2] Add a live-remote test in
      `backend/tests/integration/git/test_git_live_remote.py`: a worker whose destination worktree
      holds a discarded history does not merge onto it.
- [ ] T038 [US2] Add a live-remote test for the source side, in the same file: a worker holding a
      stale **source** branch does not merge the pre-rewrite history into the trunk, and the
      discarded commits do not reappear on the remote after the merge. This is the security-relevant
      half of FR-005a.
- [ ] T039 [US2] Add a live-remote test that a worker which missed the broadcast resets and records
      nothing, while the graph already holds the remote commit (FR-001c). This is the case that
      decides whether the classification reads the graph or the worktree.
- [ ] T040 [P] [US2] Component-test the reset in
      `backend/tests/component/git/test_git_repository.py`: a diverged branch worktree is reset to
      the remote head by `pull`, and nothing is raised.
- [ ] T041 [US2] Add a live-remote test in
      `backend/tests/integration/git/test_git_live_remote.py`: a worker that received no broadcast
      converges on first contact, writes no commit to the graph and emits no report.
- [ ] T042 [P] [US2] Add a live-remote test that a worker which has never seen the repository
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

- [ ] T043 [US1] Declare the four attributes on `CoreGenericRepository` in
      `backend/infrahub/core/schema/definitions/core/repository.py`:
      `last_rewrite_previous_commit` (`Text`), `last_rewrite_commit` (`Text`), `last_rewrite_at`
      (`DateTime`) and `rewrite_count` (`Number`). All optional, no default, all
      `BranchSupportType.LOCAL`. Do not override them on `CoreRepository` or
      `CoreReadOnlyRepository`.
- [ ] T044 [US1] Regenerate the generated files and commit them:
      `uv run invoke backend.generate`, `uv run invoke schema.generate-graphqlschema`,
      `uv run invoke schema.generate-jsonschema`, `uv run invoke docs.generate`, and
      `cd frontend/app && pnpm codegen`. CI fails when any of them is stale.
- [ ] T045 [US1] Write `HistoryRewriteRecorder` in
      `backend/infrahub/git/divergence/recorder.py`, per
      [contracts/internal-interfaces.md](contracts/internal-interfaces.md) section 2. Take its two
      collaborators as constructor-injected protocols, `RepositoryRecordStore` and
      `RewriteEventEmitter`, so the unit tests of T049 need no database and no mocks
      (`.agents/rules/backend-component-design.md`). The recorder itself imports neither the SDK
      nor the event service, and it never reads the cache.
- [ ] T046 [US1] Isolate the record write per branch, the way the other per-branch git failures
      already are. `collect_pending_imports` lets graph errors propagate, so an SDK error from the
      store would otherwise abort collection for every branch and skip the broadcast. A failed
      record joins `failed_imports` and the cycle continues.
- [ ] T047 [US1] Call the recorder from
      `backend/infrahub/git/repository.py::InfrahubRepository.collect_pending_imports`, immediately
      after the reconciled commit is written for that branch, inside the collection lock hold. The
      count increment is safe there because it is inside a lock hold; what is unsafe is a call
      placed *between* the two acquisitions. Do **not** move it after `apply_branch_import`: the
      commit is already written by then, so a failed import would leave the next cycle classifying
      `UNCHANGED` and the rewrite would never be recorded at all. See
      [contracts/internal-interfaces.md](contracts/internal-interfaces.md) section 2, "Where it is
      called".
- [ ] T048 [US1] Write the production `RepositoryRecordStore` in
      `backend/infrahub/git/divergence/store.py`, backed by the SDK node API. It reads
      `rewrite_count` and writes the four attributes in one call, so the `python_sdk` submodule
      needs no change.
- [ ] T049 [P] [US1] Unit-test the recorder in
      `backend/tests/unit/git/divergence/test_recorder.py` against in-memory ports: last-write-wins,
      the increment from absent to 1 and 1 to 2, a `RETARGET`, a `LOCAL_AHEAD` and a
      `REMOTE_ABSENT` each writing nothing, and a rejected divergence whose two commits are equal.
      No database, no mocks.
- [ ] T050 [US1] Component-test the read inheritance in
      `backend/tests/component/git/test_repository_rewrite_branch_safety.py`: a branch created
      after the default branch was reconciled reads the default branch's four values, and its own
      first reconciliation increments the count it inherited. This is what LOCAL does, and the
      test exists so nobody meets it in production. See [data-model.md](data-model.md), "What LOCAL
      does not do".
- [ ] T051 [US1] Add the branch-safety test, in the same file as T050, in
      `backend/tests/component/git/test_repository_rewrite_branch_safety.py`: the four attributes
      appear in no branch diff on `CoreRepository` or `CoreReadOnlyRepository`, and merging a
      branch that carries a record does not carry it to the destination. The constitution's
      branch-safe principle requires this to be asserted rather than inferred from the declaration.
- [ ] T052 [US1] Add a live-remote test asserting the record's contents after a rewrite, in
      `backend/tests/integration/git/test_git_live_remote.py`.

**Checkpoint**: SC-006 holds for the stored state. The human-facing view is INFP-671's.

---

## Phase 7: User Story 4 — a rewritten trunk is reconciled and announced (P2)

**Goal**: a rewrite of the configured default branch reconciles identically and emits exactly one
outbound signal.

**Independent test**: rewrite the trunk of a tracked repository on a live remote. Run several
cycles. Exactly one record, exactly one signal, and a healthy repository.

**Maps to**: FR-014, SC-002.

> **Gated on the FR-014 consumer being confirmed.** The design says the webhook subsystem. See
> [research.md](research.md) R8. Patrick may prefer a built-in notification surface, or deferring
> the signal to INFP-671.

- [ ] T053 [US4] Add `RepositoryHistoryRewrittenEvent` to
      `backend/infrahub/events/repository_action.py` and export it from
      `backend/infrahub/events/__init__.py`, per [data-model.md](data-model.md), "New event".
- [ ] T054 [US4] Add the matching member to
      `backend/infrahub/core/constants/__init__.py::EventType`. That is what puts it in the
      `event_type` enum of `CoreStandardWebhook` and `CoreCustomWebhook`, which is the consumer.
- [ ] T055 [US4] Emit the event from `HistoryRewriteRecorder` in
      `backend/infrahub/git/divergence/recorder.py`, after a successful record, and only when the
      reconciled branch is the repository's configured default branch.
- [ ] T056 [US4] Regenerate the events reference documentation with `uv run invoke docs.generate`
      and commit it.
- [ ] T057 [P] [US4] Unit-test the emission rule in
      `backend/tests/unit/git/divergence/test_recorder.py`: the trunk emits exactly one event, and
      any other branch emits none.
- [ ] T058 [US4] Add a live-remote test in
      `backend/tests/integration/git/test_git_live_remote.py`: a rewritten trunk produces exactly
      one record and exactly one signal **across several synchronisation cycles**. One cycle is not
      enough, because a single-cycle test would pass while the exactly-once property is broken.
- [ ] T059 [US4] Add a live-remote test that wires a webhook to the new event and asserts exactly
      one delivery per rewrite, in `backend/tests/integration/git/test_git_live_remote.py`. This
      test is what holds the wiring, so the event cannot become a dead one.

**Checkpoint**: SC-002 holds.

---

## Phase 8: User Story 5 — a read-only repository records the lineage break (P2)

**Goal**: a read-only repository whose tracked ref resolves to a non-descendant commit records the
break and is never reset.

**Independent test**: force-move a tag on a live remote that a read-only repository tracks. Update
the commit. The import happened, the record was written, and no reset ran.

**Maps to**: FR-009.

> **Attachment point depends on PR #10669.** If it has merged, attach to
> `backend/infrahub/git/refs_check/checker.py::ReadOnlyRepositoryRefsChecker._detect_movements`,
> whose `RefMovement` already carries the two commits the ancestry test needs. If it has not,
> attach to
> `backend/infrahub/git/repository.py::InfrahubReadOnlyRepository.update_latest_commit`. The record
> and the precondition are identical either way. See [research.md](research.md) R10.

- [ ] T060 [US5] Classify the resolved commit against the imported one at the attachment point
      chosen above, and call the recorder on a `REWRITE`. Perform no reset (FR-009).
- [ ] T061 [US5] Confirm the import path is unchanged: detection changes what is recorded, never
      what is imported.
- [ ] T062 [P] [US5] Component-test the read-only classification in
      `backend/tests/component/git/test_readonly_rewrite.py`.
- [ ] T063 [US5] Add a live-remote test in
      `backend/tests/integration/git/test_git_live_remote.py`, which is where the Gogs harness and
      `readonly_sync_dataset` live: a **force-pushed branch** tracked by a read-only repository
      writes the record and performs no reset. Do not use a moved tag: neither read-only fetch path
      force-updates an existing tag, so no lineage break would be seen. IFC-2874 fixes that flag and
      is out of scope. `test_readonly_repository.py` has no live remote.

**Checkpoint**: the quietest repository type is no longer the least honest one.

---

## Phase 9: User Story 6 — a deliberate change of target is not a rewrite (P2)

**Goal**: re-pointing a repository at a different branch, tag or commit records nothing.

**Independent test**: change a read-only repository's tracked ref to a different tag, and edit a
read-write repository's configured default branch. Neither writes a record.

**Maps to**: FR-002, SC-007.

- [ ] T064 [US6] Write the suppression marker's read and write in
      `backend/infrahub/git/divergence/suppression.py`, per [data-model.md](data-model.md),
      "Cache key". The read is destructive: it reads and deletes in one step.
- [ ] T065 [US6] Write the marker from
      `backend/infrahub/graphql/mutations/repository.py::InfrahubRepositoryMutation.mutate_update`
      when `CoreReadOnlyRepository.ref` changes **or when only `commit` changes**. It already
      computes both comparisons. SC-007 covers re-pointing to "a different branch, tag or commit",
      and the mutation submits the pull and the import on a commit-only change too, so leaving that
      out records a false rewrite. The write lands after the update succeeds and **before** either
      workflow is submitted, or the import can beat it and record a spurious rewrite.
- [ ] T066 [US6] Add the `default_branch` comparison to the same method for `CoreRepository`, and
      write the marker for Infrahub's default branch. **This comparison does not exist yet**: the
      method returns to `super().mutate_update` immediately for any kind other than read-only, so
      the comparison goes before that early return.
- [ ] T067 [US6] Submit the repository sync from the same mutation, right after the marker is
      written. Without it nothing reads the marker: a `default_branch` edit moves no git ref, so
      `compare_local_remote` reports nothing and the trunk is not classified until the new target
      next moves on the remote — by which time the marker has expired and the edit is recorded as
      a rewrite. The read-only branch of the method already submits its own workflows this way.
- [ ] T068 [US6] Consume the marker at classification time, in the two components that call the
      detector: `collect_pending_imports` for read-write, and the read-only detection point of
      T060. Pass the result as `target_changed`. The recorder must **not** read the cache: it
      returns early on any classification other than `REWRITE`, so a marker read there would never
      be consumed on a `RETARGET` and would go on to suppress the next genuine rewrite.
- [ ] T069 [P] [US6] Unit-test the suppression in
      `backend/tests/unit/git/divergence/test_suppression.py`: a present marker yields
      `target_changed` true and is gone afterwards, and an absent marker yields false. Both
      directions are asserted, so the behaviour is stated rather than assumed. Assert the marker is
      consumed exactly once, which is what stops it suppressing a later genuine rewrite.
- [ ] T070 [US6] Component-test the mutation's ordering in
      `backend/tests/component/graphql/mutations/test_repository.py`: the marker exists before the
      workflows are submitted.
- [ ] T071 [US6] Add a live-remote test in
      `backend/tests/integration/git/test_git_live_remote.py`, beside the other live-remote tests:
      changing the tracked ref to a different branch records nothing.

**Checkpoint**: SC-007 holds. Routine re-pointing produces no noise.

---

## Phase 10: Documentation and polish

**Purpose**: correct what is wrong in the knowledge docs today, and describe what shipped.

- [ ] T072 [P] Correct the branch-support table in
      `dev/knowledge/backend/git-integration.md`, "Repository state and branch support". It says
      `commit`, `sync_status` and `internal_status` are LOCAL. On `CoreReadOnlyRepository`, `commit`
      and `ref` are AWARE, so they do reach branch diffs and merges.
- [ ] T073 State in `dev/knowledge/backend/git-integration.md`, "How the workers converge",
      that the periodic sync's broadcast covered only the trunk or the staging branch and that a
      failed branch suppressed it, and that this feature changes both.
- [ ] T074 [P] Correct the "Key Files" table in
      `dev/knowledge/backend/merge-failure-recovery.md`. It attributes the merge-start logic to
      `core/branch/tasks.py::_do_merge_branch`. That logic now lives in
      `core/merge/orchestrator.py`. Check the surrounding prose for the same claim.
- [ ] T075 Rewrite the **one** "Volatile section" note in
      `dev/knowledge/backend/git-integration.md` that describes this feature as planned, the one
      under "How git errors are classified". It now describes what shipped: the ancestry detection,
      the pull-path reset, the widened broadcast and the record. Leave the other three alone: they
      cover the trunk fallback (PR #10542), the persisted writeback state (IFC-3220) and
      push-before-graph-write (PR #10465). Rewriting those would claim three other fixes shipped.
- [ ] T076 [P] Document the two limitations under `docs/docs/git-integration/`, which is the
      published section. Do not edit `docs/archive/topics/repository.mdx`: neither
      `docusaurus.config.ts` nor `sidebars.ts` references it, so an edit there ships nothing. The
      two limitations are: rewriting
      history means content at discarded commits can no longer be reliably re-derived, and schema
      already applied to a branch is not rewound.
- [ ] T077 [P] Document the accepted failure mode of the suppression marker in
      `dev/knowledge/backend/git-sync.md`: a cache flush between the re-target mutation and the
      reconciliation writes one spurious record and leaves the count one too high. The
      reconciliation itself is identical either way.
- [ ] T078 Add a towncrier changelog fragment under `changelog/`. This is a user-visible change.
      Use the `creating-changelog-entries` skill. Filename: the convention is a bare GitHub issue
      number when the release note should link that issue, and a `+slug` otherwise. The epic lists
      #6299 under "Advances", not "Closes", so a slug is the safer default. Confirm with Patrick
      whether this closes #6299; if it does, the stem is `6299`.
- [ ] T079 Add the end-to-end scenario under `tests/e2e/`: a developer rebases a branch Infrahub
      tracks and force-pushes it. The branch keeps synchronising, its imported objects match the
      rewritten history, and the repository reports healthy throughout. The constitution requires
      an E2E test for a user-facing feature, and the PRD names this scenario. Run it with `--pdb`
      while developing it; a failure then freezes the session with the stack and every fixture
      alive.
- [ ] T080 Run `/pre-ci`. It covers the whole-repository `ruff check . --exclude python_sdk` and
      `ruff format --check` that `invoke lint` misses, plus `docs.validate` for the generated
      documentation. CI fails on any of them.
- [ ] T081 Print `/review-pr <n>` and wait for the verdict before the PR leaves draft. A session
      that wrote the code cannot review it.

---

## Dependencies

```text
Phase 1 (Setup)
  └─> Phase 2 (Foundational: the classifier)
        ├─> Phase 3 (US1: reconcile in the sync path)
        │     ├─> Phase 4 (US3: broadcast every branch, before the raise)
        │     └─> Phase 6 (US1: record)  [needs schema sign-off]
        │           ├─> Phase 7 (US4: the trunk signal)  [needs the consumer confirmed]
        │           ├─> Phase 8 (US5: read-only)
        │           └─> Phase 9 (US6: re-target suppression)
        └─> Phase 5 (US2: self-heal in the pull path)  [GATED on PR #10465]

Phase 10 (Documentation) follows whatever has landed.
```

### What waits for PR #10465

**Every step that resets a worktree.** That is the whole of Phase 5, the reset inside the
sync-path task in Phase 3, and the widened broadcast in Phase 4, which makes the convergence
handler reset every branch on every other worker rather than only the trunk. Everything else can be
written, reviewed and merged before the writeback ordering fix lands.

The reason is narrow and must not be relaxed. On `develop`, a repository merge writes the commit to
the graph before it pushes, so a rejected push leaves a merge commit on one worker's disk and
nowhere else. A reset onto the remote head discards it silently. #10465 reorders that. This branch
is rebased onto `develop`, so it carries the old ordering too; the gate is about the reconciliation
not reaching a deployment that still has it.

**Both reset sites carry that hazard, not just the pull path.** An earlier draft of this plan gated
only Phase 5, which was wrong: T016 resets a branch in the sync path for exactly the same reason.

The `LOCAL_AHEAD` classification narrows the hole a long way. The ordinary shape of a rejected push
is a branch merely ahead of its remote, and that classifies `LOCAL_AHEAD`, which resets nothing.
What is left is the branch that is **both** ahead locally and rewritten remotely: neither commit is
an ancestor of the other, the classification is `REWRITE`, and the reset discards the unpushed
commit. Rare, but real, and the reason the gate survives.

T011's force-push helper is not gated. The Gogs harness and `_push_commit_to_remote` are on
`develop` already. Only the two `pre-receive` hook helpers come from #10465, and no task here
needs them. T015 (classify) and T017 to T023 are not gated either; only the
reset in T016 is.

### What waits for a person

| Tasks | Waiting on | Who |
|---|---|---|
| Every reset: Phase 5, the sync-path reset in Phase 3, the widened broadcast in Phase 4 | PR #10465 merged, and the merge order agreed against PR #10542 | Patrick Ogenstad |
| Phase 6 | Schema and GraphQL sign-off | A maintainer |
| Phase 7 | The FR-014 consumer confirmed | Patrick Ogenstad |
| Phase 8 | Whether to wait for PR #10669 to merge | Patrick Ogenstad |

---

## Parallel opportunities

| Phase | Tasks that can run together |
|---|---|
| 1 | T003, T004 |
| 2 | T005, T006 then T009, T010 |
| 3 | T012 with T011; T021 with T020. T022 and T023 both write `test_git_live_remote.py`, so they are sequential. |
| 4 | T031 alone, once T024 and T025 are done |
| 5 | T040 and T042 |
| 6 | T049 alone, once T045 and T048 are done. T050 and T051 both write `test_repository_rewrite_branch_safety.py`, so they are sequential. |
| 7 | T057 alone, once T055 is done |
| 8 | T062 alone, once T060 is done |
| 9 | T069 alone, once T064 is done |
| 10 | T074, T076, T077. T072 and T073 both edit `git-integration.md`, so they are sequential. |

---

## Implementation strategy

**Minimum viable increment**: Phases 1, 2 and 3, **and it needs PR #10465**. Those phases fix the
reported bug: a rewritten non-default branch stops being stuck, stops being described as a conflict,
and returns to a healthy state with no user action. They ship without the schema change and without
the signal, but the step that actually reconciles the branch is a reset, and every reset is gated.

An earlier draft claimed this increment shipped without #10465. It cannot: drop the reset and
nothing is reconciled. What *can* ship before #10465 is the classification and the corrected error
message, which stop the wrong "conflict" wording and the status flap without changing any
worktree.

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
| 2 Foundational | 6 |
| 3 US1 reconcile | 13 |
| 4 US3 broadcast | 10 |
| 5 US2 self-heal | 9 |
| 6 US1 record | 10 |
| 7 US4 trunk signal | 7 |
| 8 US5 read-only | 4 |
| 9 US6 re-target | 8 |
| 10 Documentation and polish | 10 |
| **Total** | **81** |
