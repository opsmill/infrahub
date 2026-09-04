# Tasks: Git Repository Commit Visibility

**Input**: Design documents from `dev/specs/ifc-3101-repo-commit-visibility/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/)
**Jira**: [IFC-3101](https://opsmill.atlassian.net/browse/IFC-3101)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel with the other `[P]` tasks in the same block (different files, no
  dependency on an incomplete task)
- **[Story]**: the user story the task serves (US1, US2, US3). Setup, foundational and polish tasks
  carry no story label
- Every task names the exact file it touches. Sites inside a file are named by symbol, never by line
  number

## Tests

Tests are in scope and are not optional here. Every functional requirement in spec.md carries a
`_Verify_` clause, and Constitution IV (Test Discipline) is a gate the plan passes on the strength of
the suites listed in its Source Code tree. Test tasks sit in the block that owns the code they pin,
so a block is never "done" with its behaviour unpinned.

Repo rules that shape every test task below, so they are not repeated per task:

- No `unittest.mock`, `MagicMock` or `patch`. Inject a recording or failing double instead
  (`.agents/rules/testing-python.md`)
- Parametrised cases use the dataclass pattern with `name` as the first field
- No FR ids, task ids or Jira ids in source, test names, docstrings or comments
  (`.agents/rules/code-doc-style.md`). They belong in the commit message, the PR body, the changelog
  fragment and this file
- Do not test the framework: no enum value round-trips, no Pydantic `ge=` constraint tests, no
  env-var plumbing tests

## SOLID guardrails for this feature

These are the design constraints the phases below are built around. They come from
`.agents/rules/backend-component-design.md` and the plan's Constitution Check, and they are the
reason the task order is what it is.

| Principle | How it lands here |
| --- | --- |
| Single responsibility | Five separated concerns: pure classification (`git/state/classification.py`, no I/O), the graph read (`RepositoryBranchValuesQuery`, one statement, no policy), the git read (`git/state/log_reader.py`, the only module that touches a clone, with both handlers shallow over it), the resolvers (permission, branch resolution, argument validation, selection gating), and the refs check (scheduling and convergence). No module does two of these |
| Open/closed | The refs check has one shared per-repository body; the scheduled and on-demand paths are two thin callers of it, so a behaviour change is one edit, not two. Swapping the placeholder reader for the real one is one factory body, not a change to any consumer |
| Liskov | `RepositoryGitStateReader` has four interchangeable implementations: unavailable, bus-backed, recording double, failing double. Every consumer codes against the protocol and none narrows the contract |
| Interface segregation | The reader exposes exactly two methods, `commits` and `branch_heads`, named in the resolver's vocabulary. The resolver never sees a message-bus type, a routing key or a timeout |
| Dependency inversion | The protocol is declared next to its consumers' vocabulary and the bus-backed implementation is selected in a factory at the resolver's composition root. The resolver depends on the protocol, never on the transport |

### Where the reader lives, and why

`backend/infrahub/git/state/`, a new subpackage of the git domain. Not
`backend/infrahub/services/adapters/`, which holds only the five infrastructure services carried on
`InfrahubServices` (`cache`, `event`, `http`, `message_bus`, `workflow`); a repository git-state read
is domain code, not one of those.

Two precedents in the tree give the exact shape, and the tasks below follow them rather than
inventing one:

- `backend/infrahub/git/fingerprint/blob_resolver.py` declares the `BlobResolver` protocol and its
  production implementation `GitBlobResolver` side by side in a domain subpackage, with the composer
  taking the protocol as a constructor parameter and `FingerprintComposer` building the concrete one
  at its own entry point.
- `backend/infrahub/task_manager/flow_run/` is the same shape one layer larger, and it is consumed by
  a GraphQL resolver exactly as ours will be: `FlowRunReaderProtocol` and `FlowRunReader` in
  `reader.py`, everything assembled by `build_prefect_task_service` in `service.py`, and
  `infrahub.graphql.queries.task::Tasks.resolve` calling that factory at the top of the resolver.

So the resolver calls a factory, and `InfrahubServices` is not touched at all. The earlier draft of
this file registered the reader on that hub; that is dropped, which removes a shared-hub edit and a
default-swapping task, and keeps the settings read (`config.SETTINGS.broker.rpc_timeout`) inside the
factory where the DI rule wants it.

Import-graph check, since the reader now lives under `infrahub.git`: the API server already imports
`infrahub.git.models` from `graphql/mutations/repository.py` and `api/artifact.py`, and
`infrahub/git/__init__.py` already pulls `git.repository` and GitPython with it. Placing the reader
there adds no new dependency to the API server's import graph.

### The other refinement to the design docs

The protocol returns frozen dataclasses from `git/state/models.py`, not the message-bus
`*ResponseData` Pydantic models that data-model.md names. This is forced as well as preferred:
`backend/tests/unit/message_bus/test_mappings.py::test_message_command_overlap` asserts `MESSAGE_MAP`
and `COMMAND_MAP` hold the same keys, so a message pair cannot be registered a phase before its
handler. Registering the pair in Phase 2 would drag the whole worker read forward and delay the
frontend hand-off, which is the one thing this ordering exists to protect.

T006 records this, the location above, the `git/state/log_reader.py` split, and the contradictions
found while writing these tasks and during `/speckit-analyze`, so the archived doc set matches what
lands.

---

## Pull request decomposition

Ninety-five tasks is a file-level count, not an effort-level one: a dozen of them add a single enum,
regenerate a committed artefact, or walk a quickstart. Grouped by review boundary the feature is
eleven pull requests. Every block heading below carries its `[PR n]` tag; this table is the authoritative
mapping.

| PR | Content | Tasks | Depends on |
| --- | --- | --- | --- |
| 1 | **Spec set.** This directory's first commit, including T006's reconciliation | T006 | none |
| 2 | **Contract and resolvers.** Enums, value objects, cache keys, reader seam, graphene types, branch-mapping extraction, both resolvers, the mutation, workflow stubs, permission tests, schema and frontend codegen. Blocks 2.1 to 2.4 and 2.6 | T002, T003-T005, T007-T020, T025-T028 | PR 1 |
| 3 | **Per-branch graph query.** `RepositoryBranchValuesQuery` and the tests pinning its inheritance. Block 2.5 | T021-T024, T097 | PR 2, mergeable either side of checkpoint 2A |
| 4 | **Bounded RPC.** Shared path: `rpc(timeout=)`, the setting, `WORKER_TIMEOUT`. Block 3.1 | T029-T031, T033, T035, T036 | PR 2 |
| 5 | **Worker read path.** Classification, the log reader, the commit-log message pair and handler, the warm-up flow, the factory swap. Blocks 3.2 to 3.4 | T037-T048, T092, T093, T096 | PR 4 |
| 6 | **Commits tab.** Frontend only, touches no backend file. Block 3.5 | T049-T058 | PR 2 (and T094 for the two rendering tasks) |
| 7 | **US1 end to end.** Small; fold into whichever of PR 5 and PR 6 lands second rather than raising it alone. Block 3.6 | T059, T060 | PR 5 and PR 6 |
| 8 | **Read-only refs check.** Configuration, the shared body, both callers, component and integration tests. Blocks 4.1 to 4.3 | T061-T071 | PR 2 |
| 9 | **Check remote now.** The frontend action, its tests and its e2e. Block 4.4 | T072-T075, T095 | PR 8 and PR 6 |
| 10 | **Branch drift.** The branch-heads message pair and read, real drift rows. Phase 5 | T076-T085 | PR 3, PR 4 and T092 |
| 11 | **Polish.** The SC-004 measurement, the FR-002 test, user documentation, the knowledge pages. Phase 6 | T086-T089 | the stories shipping |

Not pull requests: T001 (a sign-off, recorded in plan.md), T094 (a design decision on the canvas),
and T090 / T091 (the pre-push routine run before every one of the above, not content in any of them).

**Three of these boundaries are mandatory rather than chosen.** PR 3 is new graph-query surface that
IFC-3104 extends and the periodic sync later depends on. PR 4 changes behaviour for every existing
`rpc` caller, including the git file read. PR 5 is where the feature stops answering
`NOT_IMPLEMENTED`. Each is reviewed on its own merits.

**The number that matters is not eleven.** PRs 1, 2, 4, 5, 6 and 7 are the MVP: six pull requests to
a shippable commit view, which is the whole of this feature's value for read-write repositories. PRs
8 through 10 are the read-only and per-branch slices, each independently demoable and each deferrable
without breaking anything before it. PR 10 in particular ships a query whose UI consumer does not
exist until the IFC-3104 Branches card does, so it is the easiest to postpone.

**Where the calendar collapses.** Once PR 2 merges, PRs 3, 4, 6 and 8 are unblocked simultaneously
and share no files. That is the three-developer split under "Parallel team strategy" below; it
shortens the elapsed time without changing the pull request count.

**PR 2 is the largest, at twenty-two tasks.** Splitting it lands `schema/schema.graphql` either
without resolvers or without types, which is what Phase 2 exists to avoid, so the default is to keep
it whole. Should it need splitting, the seam that preserves that property is T003 to T009
(vocabulary, value objects, reader seam, test helpers, no GraphQL at all) ahead of the rest.

---

## Phase 1: Setup (governance and a clean baseline)

**Purpose**: clear the one blocking approval and establish that every generated artefact is clean
before anything is edited, so a later regeneration diff is unambiguously ours.

- [x] T001 Record the "Ask First" sign-off in the Governance paragraph of `dev/specs/ifc-3101-repo-commit-visibility/plan.md`: the additive GraphQL query and mutation surface, plus `BrokerSettings.rpc_timeout` and `GitSettings.read_only_refs_check_interval_mins`. **Done 2026-09-04**, approved by Patrick Ogenstad. The GraphQL gate was definitional (the feature *is* new queries); the substantive half was `rpc_timeout` changing behaviour for existing `rpc` callers, and 30 seconds is the agreed default
- [ ] T094 [P] Get the three design-canvas updates the spec's Assumptions record, and the one presentation question the PRD left to the designer, settled on the [Git sync visibility canvas](https://claude.ai/design/p/d8efb789-c722-4622-b8d8-0bceb7054774?file=Git+sync+visibility.dc.html&via=share): drop the commit-count badge (FR-024), add a check time alongside the update time on the freshness line for read-only repositories (FR-007), place a "check remote now" action (FR-015), and settle how a rewritten ref is distinguished from ordinary drift without introducing a new repository status value. Blocks T054 and T072 only, so it runs alongside the whole of Phase 2 rather than gating it
- [ ] T002 [P] Capture a clean generated-artefact baseline: run `uv run invoke schema.validate-graphqlschema`, `uv run invoke docs.validate`, `uv run invoke release.validate-dockercomposeenv`, and `cd frontend/app && pnpm codegen && git diff --exit-code src/shared/api/graphql/generated`. Fix or note any pre-existing drift before editing source

**Checkpoint**: approval recorded, generated files known clean. Nothing here is a pull request of its
own: T001 is a sign-off already recorded in plan.md, T002 is a check run before editing anything, and
T094 is a design decision that runs on its own track and gates only the two frontend tasks rendering
it. PR 1 is this directory's first commit, carrying T006 from block 2.1.

---

## Phase 2: Foundational (the published contract and Infrahub's own answers)

**Purpose**: land the whole GraphQL surface once, unconditionally, with every answer the API server
can give on its own. This is plan Phase A. It blocks all three user stories and it is the frontend
hand-off, so it comes first and stays as small as it can be while still being honest.

**Why it is the MVP**: nothing in the frontend reads a live server schema. The frontend types against
the checked-in `schema/schema.graphql` through gql.tada and graphql-codegen, so the moment that file
carries the new SDL the frontend team is unblocked, whether or not any server can yet answer with
commits. `UNAVAILABLE / NOT_IMPLEMENTED` is a state the UI has to handle regardless.

**CRITICAL**: no user story work starts before checkpoint 2A.

### Block 2.1 [PR 2]: shared vocabulary and value objects (fully parallel)

T006 is the exception in this block: it is documentation only and belongs to PR 1.

- [ ] T003 [P] Add `RepositoryGitCondition`, `RepositoryCommitState` and `RepositoryGitUnavailableReason` as `InfrahubStringEnum` subclasses in `backend/infrahub/core/constants/__init__.py`, with exactly the members and string values in data-model.md. Constants only, no helper functions in that module
- [ ] T004 [P] Create `backend/infrahub/git/state/models.py` with the frozen dataclasses `CommitEntry`, `GitStateFacts`, `CommitLogRequest`, `BranchHeadsRequest`, `CommitLogResult`, `BranchDriftRow` and `BranchDriftResult`, fields per data-model.md plus `unavailable_reason`, `warm_up_task_id`, `fetched_at` and `error_message` on the two result types. Pure module: no `git` import, no I/O, no logging
- [ ] T005 [P] Create `backend/infrahub/git/state/cache_keys.py` owning a prefix constant and the four key builders over a repository id (`git:warmup:<id>`, `git:refs_check:due:<id>`, `git:refs_check:running:<id>`, `git:refs_check:last:<id>`), after `infrahub.webhook.constants::CACHE_KEY_PREFIX` for the prefix and `task_manager/flow_run/cache_key.py` for the builder. Use `infrahub.message_bus.types::KVTTL` for the warm-up TTL and computed integers for the two that no member fits. Plain functions, no class: nothing varies per caller. The API resolver and the worker flows read and write these keys from different processes, and nothing else makes them agree on the string
- [x] T006 [P] **Done 2026-09-04, in PR 1** (documentation only, applied before any code in this block). Update `dev/specs/ifc-3101-repo-commit-visibility/data-model.md`, `contracts/message_bus.md` and the Source Code tree in `plan.md` with what the tasks below actually build: the `git/state/` package and factory instead of a reader inside the resolver module, dataclass return types on the protocol, the shared cache-key module, `git/state/log_reader.py` (T092) as the owner of every git read with both handlers shallow over it, and the remote-branch mapping resolved on the API side from the graph value through one extracted function. Grep the whole spec directory for `GitCommitLogGetResponseData`, `graphql/queries/repository_git_state.py`, `git/commit_log` and `WorkerRepositoryGitStateReader` so no file keeps a superseded shape, and fix the stale test path in the quickstart's Phase A command (`backend/tests/unit/git/test_commit_log.py`, now `backend/tests/unit/git/state/test_classification.py`). Add to `plan.md`'s tree the files it currently omits: `git/state/{cache_keys,factory,log_reader}.py`, `git/branch_mapping.py`, `backend/tests/helpers/repository_git_state.py`, `backend/tests/component/api/`, the ref-validation unit test and the FR-002 component test. Record one deliberate divergence from the PRD: the warm-up trigger is not declared as its own protocol, because the single-flight behaviour is already testable without patching through a recording cache and `WorkflowRecorder` (T044), which is the property that constraint existed to protect. The cache-key table, FR-025 and quickstart step 8 were already corrected on 2026-09-04; check them rather than re-editing them. Also reconciled in the same pass: the residual `count` in `plan.md` and `research.md` against FR-024, the NATS support claim in Technical Context, `critiques/` missing from the documented structure, and the settled second-request decision still reading as open in `spec.md`

### Block 2.2 [PR 2]: the reader seam (dependency inversion)

Depends on T004.

- [ ] T007 Create `backend/infrahub/git/state/reader.py` with the `RepositoryGitStateReader` protocol (`commits(request: CommitLogRequest) -> CommitLogResult`, `branch_heads(request: BranchHeadsRequest) -> BranchDriftResult`) and `UnavailableRepositoryGitStateReader`, which answers `UNAVAILABLE` with `unavailable_reason=NOT_IMPLEMENTED`, empty rows and a display-safe message. Protocol and its dependency-free implementation side by side, as `git/fingerprint/blob_resolver.py` does. Imports only `git/state/models.py` and `core/constants`
- [ ] T008 Create `backend/infrahub/git/state/factory.py` with `build_repository_git_state_reader(...) -> RepositoryGitStateReader`, returning `UnavailableRepositoryGitStateReader()` in this phase, following `task_manager/flow_run/service.py::build_prefect_task_service`. This factory is the only place that will ever read a setting or pick an implementation, so block 3.4 changes its body and nothing else
- [ ] T009 [P] Create `backend/tests/helpers/repository_git_state.py` with `RecordingRepositoryGitStateReader` (appends each request to an ordered list and replays queued results) and `FailingRepositoryGitStateReader` (raises `WorkerTimeoutError`), following `StaticBlobResolver` in `backend/tests/unit/git/fingerprint/conftest.py`. Not `backend/tests/adapters/`, which mirrors `services/adapters/`. These are the third and fourth implementations of the protocol and the reason the component tests need no patching: the recorded requests are what make "no worker request was made" and "the request carried this branch and this flag" assertable as full frozen-dataclass equality

### Block 2.3 [PR 2]: graphene types and the registered surface

Depends on block 2.2. T011 and T012 are the same new file and sequential; the rest fan out.

- [ ] T010 [P] Create `backend/infrahub/graphql/types/repository.py` with `RepositoryCommit`, `RepositoryCommitNode`, `RepositoryGitUnavailable`, `RepositoryCommits`, `RepositoryBranchDrift`, `RepositoryBranchDriftNode` and `RepositoryBranchDrifts`, exactly as `contracts/repository_git_state.graphql` prints them. Enums via `graphene.Enum.from_enum` over the T003 classes. Every description single-line, snake_case field names (the schema is built with `auto_camelcase=False`)
- [ ] T011 [P] Create `backend/infrahub/git/branch_mapping.py` with a pure function taking the Infrahub branch name, the repository's configured default branch and Infrahub's default branch, all three required with no defaults, and returning the remote branch to read; make `InfrahubRepositoryBase._get_mapped_remote_branch` in `backend/infrahub/git/base.py` delegate to it with no behaviour change, and update the branch-mapping section of `dev/knowledge/backend/git-sync.md`, which names that method today. Leave `_get_mapped_target_branch` alone, and leave the `default_branch` property's `or registry.default_branch` fallback alone: removing that is the configured-default-branch PRD's P1 and is out of scope here. The reason for extracting rather than calling the method is that the API server cannot call it (it is a private instance method and the API server must never build a repository object), and the reason for extracting rather than restating the two-line rule in the resolver is that two copies would drift on the default-branch case. Required parameters are what keep the extracted copy free of the fallback the other PRD is removing. This extraction is a deliberate departure from the PRD's "without refactoring it" and is recorded as such under Deviations in `spec.md`; do not treat it as an incidental refactor
- [ ] T012 Create `backend/infrahub/graphql/queries/repository_git_state.py` with the shared repository loader and permission gate used by both queries: `NodeManager.get_one_by_id_or_default_filter` on `InfrahubKind.GENERICREPOSITORY` for the request branch, then `graphql_context.active_permissions.raise_for_permission(define_object_permission_from_branch(schema=<concrete kind>, action=PermissionAction.VIEW, branch_name=...))`. The imperative check is required because `InfrahubGraphQLQueryAnalyzer` maps top-level fields to kinds by exact name and cannot see a custom query
- [ ] T013 Add the `InfrahubRepositoryCommits` resolver to `backend/infrahub/graphql/queries/repository_git_state.py`: build the reader with the T008 factory, resolve the imported commit from `commit.value` on the request branch, resolve `git_ref` with an exhaustive `match` on the repository kind rather than a predicate chain (the T011 function over the repository's own `default_branch.value` and `registry.default_branch` for the read-write kind, `ref.value` for the read-only kind, with no fallback if either is missing), returning `git_ref: null` with `condition: NOT_TRACKED` when the kind's source value is absent, which is why the contract makes the field nullable; validate `limit` to 1..100 and `offset` to `>= 0`, gate `pending_count` on selection with `extract_graphql_fields`, then delegate to the reader and map its result onto the graphene types
- [ ] T014 Add the `InfrahubRepositoryBranchDrift` resolver to the same module: resolve the row set from `registry.branch` (branches with `sync_with_git` for the read-write kind, every branch for the read-only kind, excluding `MERGED`, `DELETING` and the global branch), delegate to the reader, and return the column-level unavailable state with empty edges until block 2.5 supplies the rows
- [ ] T015 [P] Add `ReadOnlyRepositoryCheckRefs` to `backend/infrahub/graphql/mutations/repository.py`, requiring `PermissionAction.UPDATE` on the concrete kind the way `ReadOnlyRepositoryImportLastCommit` does, refusing a non-read-only repository, and submitting `GIT_READ_ONLY_REPOSITORY_CHECK_REFS`. Returns `ok` and `task`
- [ ] T016 [P] Add the three `WorkflowDefinition` constants `GIT_REPOSITORY_WARM_UP`, `GIT_READ_ONLY_REPOSITORIES_CHECK_REFS` (`cron="* * * * *"`, `concurrency_limit=1`, `ConcurrencyLimitStrategy.CANCEL_NEW`) and `GIT_READ_ONLY_REPOSITORY_CHECK_REFS` to `backend/infrahub/workflows/catalogue.py`, with flow bodies in `backend/infrahub/git/tasks.py` that log and return in this phase. The definitions must exist for `backend/tests/unit/workflows/test_catalogue.py` to pass
- [ ] T017 Register the two query fields and the mutation in `backend/infrahub/graphql/schema.py` (`InfrahubBaseQuery`, `InfrahubBaseMutation`) and export the resolvers from `backend/infrahub/graphql/queries/__init__.py`

### Block 2.4 [PR 2]: tests for the contract

Depends on block 2.3. All three are different files and run in parallel.

- [ ] T018 [P] Create `backend/tests/component/graphql/queries/test_repository_git_state.py` covering, with `RecordingRepositoryGitStateReader` injected: both queries return the Infrahub-side fields for the request branch; the answer follows an Infrahub branch switch; `limit` outside 1..100 and a negative `offset` are refused with the exact error message; selecting `pending_count` records a request whose full dataclass equals the expected one including `include_pending_count=True`, and omitting it records one with `False`; selecting only Infrahub-side fields records an empty request list; the placeholder's `UNAVAILABLE / NOT_IMPLEMENTED` reaches the response
- [ ] T019 [P] Extend `backend/tests/component/graphql/auth/` with the permission cases: a user holding `Core/Repository/view` reads both queries; a user without it is denied with the same error as querying `CoreRepository` directly; the mutation requires update permission. Reload the repository after the denial and assert nothing changed
- [ ] T020 [P] Extend `backend/tests/component/graphql/mutations/test_repository.py` with the check-refs mutation using `WorkflowRecorder`: the recorded submission names `GIT_READ_ONLY_REPOSITORY_CHECK_REFS` with the repository id, a read-write repository is refused, and the returned `task.id` is the submitted run's

### Block 2.5 [PR 3]: the per-branch graph read (own pull request, reviewable on its own)

Depends on block 2.1. Independent of blocks 2.2 to 2.4, so it can be built and reviewed in parallel
with them and merged either side of checkpoint 2A.

- [ ] T021 Create `backend/infrahub/core/query/repository.py` with `RepositoryBranchValuesQuery` following `dev/knowledge/backend/query-pattern.md`: parameters `repository_id`, an explicit `branch_scopes` list of `BranchScope(branch_name, branch_names, time_base, time_tip)` and an explicit `attribute_names` set; one statement that `UNWIND`s the scopes and applies the standard edge-activity predicate per scope with `ORDER BY branch_level DESC, from DESC, status ASC LIMIT 1` plus the active-status check; `get_data()` returns frozen `RepositoryBranchValue` rows carrying `source_branch`. Shape after `core/diff/query/artifact.py` for the multi-branch value read and `core/query/diff.py::DiffCountChanges` for the row-per-branch return and its Python-side backfill
- [ ] T022 Create `backend/tests/component/core/query/test_repository_branch_values.py` pinning the resolution before anything depends on it: a branch with its own `commit` reports it; a branch that never imported reports its origin branch's fork-point value with `source_branch` naming that branch, still does after the default branch imports a newer commit, and reports the newer value after a rebase; a read-only repository reports each branch's own `ref`; and the recorded database query count is identical for a fixture with 5 branches and one with 200, asserted with `backend/tests/helpers/db_query_counter.py` against a pinned positive number
- [ ] T023 Replace the row source in the `InfrahubRepositoryBranchDrift` resolver with `RepositoryBranchValuesQuery`, so each row carries the `tracked_commit` and `git_ref` its own branch resolves, `remote_head` null, `NOT_TRACKED` where nothing is tracked or inherited, and the column-level unavailable state still set. Leave `infrahub.git.utils::get_repositories_commit_per_branch` untouched
- [ ] T097 Confirm the `RepositoryBranchValuesQuery` boundary with the IFC-3104 owner **before this block's pull request lands**, not after: that this single-repository per-branch read is the primitive that epic widens to many repositories with server-side filters, ordering and paging, and that reading the tracked commit and ref here does not encroach on the Branches card's other graph-resolved values. The PRD assigns every graph-resolved per-branch value to that epic, so this is the one scope boundary this feature moves and it needs the other side's agreement rather than a unilateral note. Record the outcome in `spec.md`'s Deviations entry. T084 remains the post-implementation hand-off record
- [ ] T024 Extend `backend/tests/component/graphql/queries/test_repository_git_state.py` with the drift row set: read-write branches without `sync_with_git` are absent, `MERGED` and `DELETING` branches and the global branch are absent, every branch of a read-only repository is present, and a read-only branch with nothing imported or inherited reports `NOT_TRACKED`

### Block 2.6 [PR 2]: regenerate, document, hand off

Depends on blocks 2.3 and 2.4 (2.5 may land after).

- [ ] T025 Regenerate `schema/schema.graphql` with `uv run invoke schema.generate-graphqlschema` and confirm `uv run invoke schema.validate-graphqlschema` passes. Diff the new SDL against `contracts/repository_git_state.graphql` field by field and assert the schema exposes no `count`, no `author_email` and no `answered_by`
- [ ] T026 Regenerate the frontend types: `cd frontend/app && pnpm codegen` for `src/shared/api/graphql/generated/{graphql-env.d.ts,graphql-cache.d.ts,types.ts}`, and commit them
- [ ] T027 [P] Add a towncrier fragment `changelog/ifc-3101-repository-commits-api.added.md` describing the new commit-log and branch-drift queries and the on-demand refs-check mutation, in user-facing terms
- [ ] T028 [P] Walk quickstart.md "Phase A" against a running stack (`uv run invoke dev.start`) and record any step whose expectation the implementation contradicts, amending quickstart.md rather than the assertion

**Checkpoint 2A (the frontend hand-off, and the MVP)**: `schema/schema.graphql` and the frontend
generated types carry the full surface; both queries answer with real repository, branch, ref and
imported-commit values and an honest unavailable state; permission behaves exactly as it does for the
repository itself. Frontend work (block 3.5) can start now and does not wait for any later phase.

**Checkpoint 2B**: drift rows carry each branch's own tracked commit and ref from one database query,
with the query count independent of branch count.

---

## Phase 3: User Story 1 - See what Infrahub has imported and what is pending (Priority: P1) 🎯 MVP

**Goal**: the commit view answers for real. A paged newest-first log read live from a worker's clone,
with the imported commit and the remote head marked, the pending range identifiable, the rewritten
condition reported as itself, a not-yet-available state that resolves on its own, and a copyable full
hash.

**Independent Test**: against a `FileRepo` fixture whose remote has advanced past the imported
commit, open the Commits tab on that branch and confirm both markers, the pending range, the
per-commit fields, the freshness line, and hash copying. No read-only repository and no branch list
involved.

**Parallelism**: block 3.5 (frontend) depends only on checkpoint 2A, so it runs alongside blocks 3.1
to 3.4 from the start. Within the backend, 3.1 gates 3.4, and 3.2 gates 3.3.

### Block 3.1 [PR 4]: bounded worker RPC (shared path, its own pull request)

Changes behaviour for every existing `rpc` caller, so it lands and is reviewed on its own. US3 also
depends on it.

- [ ] T029 [US1] Add `timeout: float | None = None` to `InfrahubMessageBus.rpc` in `backend/infrahub/services/adapters/message_bus/__init__.py` and implement it in `rabbitmq.py` and `nats.py` by wrapping the reply future in `asyncio.timeout`, and in `local.py` by accepting and ignoring it. `None` resolves to `config.SETTINGS.broker.rpc_timeout`
- [ ] T030 [US1] Add `rpc_timeout: int = 30` (`ge=1`, env `INFRAHUB_BROKER_RPC_TIMEOUT`) to `BrokerSettings` in `backend/infrahub/config.py`
- [ ] T031 [US1] Add `WorkerTimeoutError` to `backend/infrahub/exceptions.py` (HTTP 504), the `WORKER_TIMEOUT` entry to `infrahub.errors.catalogue::CATALOGUE` with stability `evolving`, `WorkerTimeoutData(operation, timeout_seconds, retry_after_seconds)` to `backend/infrahub/errors/payloads.py`, and the payload case to `infrahub.graphql.error_formatter::_build_payload`. The message names the routing key only, never a worker identity or a path
- ~~T032~~ **Retired 2026-09-04, moved out of this feature.** Calling `InfrahubResponse.raise_for_status()` in `infrahub.api.file::get_file` fixes a pre-existing defect on the same call path, but it is unrelated to commit visibility and the PRD scopes this shared-path change to the bounded wait alone. Filed as its own ticket. Sequence that ticket immediately after PR 4 so the endpoint does not sit answering 504 on a hang and 200 on a worker-side error for longer than one release. Id left retired rather than reused, so every other task id stays stable
- [ ] T033 [P] [US1] Create `backend/tests/component/services/adapters/message_bus/test_rpc_timeout.py`: with a bus adapter that never replies, `rpc` raises `WorkerTimeoutError` within the configured bound and the GraphQL formatter renders `code: WORKER_TIMEOUT`, `http_status: 504` and a `data.retry_after_seconds` equal to the timeout. Assert the whole error message with `==`
- ~~T034~~ **Retired 2026-09-04**, with T032: it tested that fix and travels with it to the new ticket
- [ ] T035 [US1] Regenerate and commit `schema/error-catalogue.json`, `frontend/app/src/shared/api/errors/catalogue.generated.ts`, `docs/docs/reference/error-catalogue.mdx` and `docs/docs/reference/configuration.mdx` (`uv run invoke docs.generate`), add the `INFRAHUB_BROKER_RPC_TIMEOUT` mapping to `development/docker-compose.yml` and the root compose env block, and confirm `uv run invoke release.validate-dockercomposeenv` and `uv run invoke docs.validate` pass
- [ ] T036 [P] [US1] Add `changelog/ifc-3101-bounded-worker-rpc.changed.md` covering the bounded wait and the new setting. Not the file endpoint: that fix left this feature with T032

### Block 3.2 [PR 5]: classification (pure, no I/O)

Depends only on T003 and T004, so it can start during Phase 2.

- [ ] T037 [P] [US1] Create `backend/infrahub/git/state/classification.py` with `classify(facts)` and `classify_commit(hash, is_ancestor_of_imported, facts, condition)`: `ORPHANED` first of all, when the imported hash is present but `imported_resolvable` is false, so the ancestry branches are never reached with a hash git cannot resolve; then `IN_SYNC` when head equals imported, `BEHIND` when imported is an ancestor of head, `REWRITTEN` when it is not, `NO_REMOTE` when there is no head, `NOT_TRACKED` when nothing is imported; per-commit `IMPORTED` before `HEAD`, then `HEAD`, then `PENDING` / `HISTORY` / `UNRELATED`, with every non-head commit `UNRELATED` under both `REWRITTEN` and `ORPHANED`
- [ ] T038 [P] [US1] Create `backend/tests/unit/git/state/test_classification.py` with parametrised dataclass cases over `GitStateFacts` and per-commit inputs, no repository and no fixtures: each condition, the precedence when head equals imported, a non-linear history where list position would mislead, the absence of a pending count under `REWRITTEN`, `ORPHANED` and `NOT_TRACKED`, and that `ORPHANED` is decided from `imported_resolvable` alone with both ancestry fields left `None`, which is what proves no ancestry call could have been made

### Block 3.3 [PR 5]: the worker read path

Depends on T037. T092 owns the git work; T039 and T040 are one file each and parallel over it; T041
registers both.

- [ ] T092 [US1] Create `backend/infrahub/git/state/log_reader.py`, the only module that knows how a commit log is produced, so neither handler holds git code and the availability path is not written twice. It owns: an availability check that builds the repository object for the kind without `init`, calls `validate_local_directories()`, and turns `RepositoryInvalidFileSystemError` into a `NOT_CLONED` outcome carrying a warm-up task id, attempting `cache.set(key=<warm-up key from git/state/cache_keys.py>, expires=60, not_exists=True)` and submitting `GIT_REPOSITORY_WARM_UP` only when that set succeeds; head resolution for a `git_ref` with no fetch (`origin/<branch>` for read-write, `origin/<ref>` then `<ref>` for read-only, `None` meaning `NO_REMOTE`); fact gathering, in this order: resolve the imported hash against the clone first and set `imported_resolvable`, then call `Repo.is_ancestor` only when it resolved, because that call raises `GitCommandError` on an unresolvable rev rather than returning `False`; then `git rev-list --count` only when the pending count was selected; a paged walk with `iter_commits(head, max_count=limit, skip=offset)`; and the `FETCH_HEAD` mtime for `fetched_at`. Classification comes from the T037 functions, which stay pure and separate. Never take the repository lock, never call `get_initialized_repo`, `get_commit_value`, `fetch` or `pull`, and never count the whole history. All GitPython work runs inside `asyncio.to_thread`. Collaborators (cache, workflow submitter) arrive as required constructor parameters. T077 extends this module with the branch-heads pass rather than repeating any of the above
- [ ] T039 [US1] Create `backend/infrahub/message_bus/messages/git_commit_log_get.py` with `ROUTING_KEY = "git.commit_log.get"`, `GitCommitLogGet`, `GitCommitLogGetResponseData` and `GitCommitLogGetResponse`, fields per data-model.md, following `git_file_get.py`
- [ ] T040 [US1] Create `backend/infrahub/message_bus/operations/git/commit_log.py`: unpack the message, resolve the singletons it needs, delegate to the T092 reader, reply. Intentionally shallow, following `git.file.get`'s handler. No git call, no cache call and no workflow submission in this module
- [ ] T041 [US1] Register the pair in `backend/infrahub/message_bus/messages/__init__.py` (`MESSAGE_MAP`, `RESPONSE_MAP`, `PRIORITY_MAP` at priority 4) and the handler in `backend/infrahub/message_bus/operations/__init__.py` (`COMMAND_MAP`), and add `git.commit_log.get` to `operations_without_flows` in `backend/tests/unit/message_bus/test_mappings.py` since the handler is a plain coroutine like `git.file.get`. `test_message_command_overlap` fails if the two maps drift, which is why registration lands with the handler
- [ ] T042 [US1] Add `GitRepositoryWarmUp` to `backend/infrahub/git/models.py` and implement `warm_up_git_repository` in `backend/infrahub/git/tasks.py`, replacing the T016 stub: `get_initialized_repo` under `lock.registry.get(name=<repository_name>, namespace="repository")`, then broadcast `RefreshGitFetch` pinned to the imported commit so every other worker converges. Resolve singleton getters at the flow top and delegate; no business logic in the flow body
- [ ] T043 [P] [US1] Create `backend/tests/component/message_bus/operations/git/test_commit_log.py` on `backend/tests/helpers/file_repo.py` fixtures: behind (count and per-commit states), in sync (both markers on one commit, nothing pending), rewritten via force-push to a `receive.denyCurrentBranch=ignore` remote (no pending count, the imported hash absent from the page), a repository with no commits, an imported commit whose object the clone does not hold reported as `ORPHANED` with no exception and no pending count, paging across a known history, `fetched_at` present and moving after a fetch, and `include_pending_count=False` leaving the counting call unmade. Add one case that drives the T092 reader directly against two clone directories left at different states and asserts `remote_head` and `fetched_at` both track the clone being read. That is the compensating control SC-009 rests on in place of a two-worker fixture, and until it is asserted the freshness statement is only claimed to expose a worker that has fallen behind
- [ ] T044 [P] [US1] Add to the same suite the not-cloned path with a recording cache and `WorkflowRecorder`: the reply carries `NOT_CLONED` and a warm-up task id, ten concurrent invocations start exactly one warm-up, and a handler invocation does not block a concurrent message on the same worker

### Block 3.4 [PR 5]: swap the seam onto the worker

Depends on blocks 3.1 and 3.3.

- [ ] T045 [US1] Create `backend/infrahub/git/state/bus_reader.py` with `BusRepositoryGitStateReader`, taking the message bus and the timeout as required constructor parameters (plain values, not a settings object), issuing `rpc(..., timeout=...)` and mapping the reply's Pydantic data onto the `git/state/models.py` result dataclasses. It is the only module in the read path that knows a routing key
- [ ] T046 [US1] Change the body of `build_repository_git_state_reader` in `backend/infrahub/git/state/factory.py` to return `BusRepositoryGitStateReader` built with the message bus and `config.SETTINGS.broker.rpc_timeout`. This is the whole swap: no resolver, no test and no consumer changes, which is the property the factory exists for
- [ ] T047 [US1] Add `checked_at` resolution to the two resolvers in `backend/infrahub/graphql/queries/repository_git_state.py`, read through the T005 cache-key module for the read-only kind and null for the read-write kind. Written by Phase 4; null until then, which is correct for both kinds today
- [ ] T048 [P] [US1] Extend `backend/tests/component/graphql/queries/test_repository_git_state.py` with `FailingRepositoryGitStateReader`: the query surfaces `WORKER_TIMEOUT` with its retry hint rather than an `UNAVAILABLE` result, and the drift query's rows still render with only the column reporting its own state
- [ ] T093 [P] [US1] Create `backend/tests/unit/git/state/test_bus_reader.py` against a recording bus double: `BusRepositoryGitStateReader` sends the expected routing key with the timeout it was constructed with, and maps a reply's Pydantic data onto the `git/state/models.py` dataclasses field by field, including `NOT_CLONED` with a `warm_up_task_id` and a reply carrying `error_message`. The PRD names the git read client as a unit-test target, and this is the one module between the resolver tests and the handler tests with no coverage otherwise
- [ ] T096 [US1] Add the PRD's integration-level check to `backend/tests/integration/git/`: run `InfrahubRepositoryCommits` end to end against a fixture repository through a real worker read, not a double, asserting the commits come back for the request branch; and in the same suite, that a selection requesting only Infrahub-side fields produces no worker traffic at all. T018 covers both against `RecordingRepositoryGitStateReader`, which cannot show that the real transport is also lazy, and the PRD asks for this one at integration level specifically

### Block 3.5 [PR 6]: the Commits tab (starts at checkpoint 2A, parallel with 3.1 to 3.4)

Every task here builds against the generated types from T026 and the `UNAVAILABLE` state, so none of
it waits on the worker read. T049 to T052 are separate files and parallel.

- [ ] T049 [P] [US1] Create `frontend/app/src/entities/repository/api/get-repository-commits-from-api.ts`: the gql.tada document for `InfrahubRepositoryCommits` from the contract's example, with `limit` and `offset` parameters
- [ ] T050 [P] [US1] Create `frontend/app/src/entities/repository/domain/use-cases/get-repository-commits.ts` mapping the API response to the domain shape the tab renders
- [ ] T051 [P] [US1] Create `frontend/app/src/entities/repository/domain/rules/is-git-state-available.ts`, a pure predicate over the condition and unavailable reason that decides whether to keep polling
- [ ] T052 [P] [US1] Create `frontend/app/src/entities/repository/ui/queries/repository.query-keys.ts` (or extend it if present) with the commit-log key factory, following `entities/branches/ui/queries/branch.query-keys.ts`
- [ ] T053 [US1] Create `frontend/app/src/entities/repository/ui/queries/get-repository-commits.query.ts`: `refetchInterval` while the state is unavailable, following `entities/branches/ui/queries/get-branch-action-state.query.ts`, and `placeholderData: keepPreviousData` so a cold worker answering a later poll cannot blank a populated list
- [ ] T054 [US1] Create `frontend/app/src/entities/repository/ui/repository-commits-tab.tsx`: newest-first rows with short hash, summary, author and date; the imported and head markers; per-row state from the response, never inferred from row position; `CopyToClipboardButton` for the full hash; `DateDisplay fullTimestamp` for the freshness line, showing `checked_at` when present and `fetched_at` otherwise and both when they differ; `Pagination` with `usePagination` and no total; `NoDataFound` for the not-yet-available state, rendered only when there is no previous data; a distinct banner for `REWRITTEN`. Every state and marker carries a text label or an icon with an accessible name, never colour alone, and the copy action announces completion
- [ ] T055 [US1] Register the tab: add `REPOSITORY_COMMITS_TAB` to `frontend/app/src/entities/repository/domain/model/repository.ts`, the tab entry gated with `isOfKind(GENERIC_REPOSITORY_KIND, ...)` in `frontend/app/src/entities/nodes/object/ui/object-details/object-details-tabs.tsx`, the route element `frontend/app/src/pages/objects/object-details/repository-commits.tsx`, and the nested route in `frontend/app/src/app/router.tsx`
- [ ] T056 [P] [US1] Create `frontend/app/src/entities/repository/ui/repository-commits-tab.test.tsx` querying by accessible name rather than by class: rows render every field, both markers are identifiable, the rewritten banner replaces the pending range, the not-yet-available state renders distinctly from an error, a poll answering unavailable keeps the previously loaded page, and the copy action places the full hash on the clipboard and announces itself. Fixtures cover rewritten and not-cloned, which cannot be produced against a live repository
- [ ] T057 [P] [US1] Create `frontend/app/src/entities/repository/domain/rules/is-git-state-available.test.ts` over every condition and unavailable reason
- [ ] T058 [P] [US1] Add `changelog/ifc-3101-repository-commits-tab.added.md` for the Commits tab

### Block 3.6 [PR 7]: end to end

Depends on blocks 3.4 and 3.5.

- [ ] T059 [US1] Create `tests/e2e/repository/test_repository_commits.py` against `demo_edge_repo`, seeded already behind with the sync tick awaited once in a fixture rather than pushing mid-test and waiting out the one-minute cron: open the Commits tab, assert a row per commit with hash, summary, author and relative date, both markers, the pending range, and that the copy button places the full hash on the clipboard. Run it with `--pdb` while developing
- [ ] T060 [US1] Walk quickstart.md "Phase B" end to end and reconcile any divergence in quickstart.md

**Checkpoint (MVP complete)**: a user on any Infrahub branch reads the repository's recent commits
inside Infrahub, sees which commit is imported and which is at the remote head, identifies what is
pending, is told plainly when the ref was rewritten, copies a full hash, and sees how fresh the answer
is. Read-write repositories get the whole of this story's value here.

---

## Phase 4: User Story 2 - Notice upstream movement on a read-only repository (Priority: P2)

**Goal**: a read-only repository's tracked ref is checked on a configurable interval and on demand.
Movement becomes visible without touching what Infrahub runs: the tracked commit never changes, no
import runs, and no worker checks out anything new.

**Independent Test**: advance a fixture read-only remote, wait out the interval or trigger the check,
and confirm the drift is visible, the tracked commit and imported content are byte-identical, and the
convergence broadcast went to the pool with the tracked commit pinned. No commit view UI required.

**Parallelism**: T061 to T063 are independent files. T064 to T067 are the same two files and are
sequential. T073 depends only on checkpoint 2A and can run alongside the backend work.

### Block 4.1 [PR 8]: configuration and parameters

- [ ] T061 [P] [US2] Add `read_only_refs_check_interval_mins: int = 15` (`ge=1`, env `INFRAHUB_GIT_READ_ONLY_REFS_CHECK_INTERVAL_MINS`) to `GitSettings` in `backend/infrahub/config.py`. No disabling value: lengthening the interval is the control, matching `CacheSettings.clean_up_deadlocks_interval_mins`
- [ ] T062 [P] [US2] Add `GitReadOnlyRepositoryCheckRefs` and its `TrackedRef` to `backend/infrahub/git/models.py` per data-model.md
- [ ] T063 [P] [US2] Add the `INFRAHUB_GIT_READ_ONLY_REFS_CHECK_INTERVAL_MINS` mapping to `development/docker-compose.yml` and the root compose env block, regenerate `docs/docs/reference/configuration.mdx` with `uv run invoke docs.generate`, and confirm `uv run invoke release.validate-dockercomposeenv` and `uv run invoke docs.validate` pass

### Block 4.2 [PR 8]: the shared check body and its two callers

Depends on block 4.1. One body, two thin callers, so the scheduled and on-demand paths cannot
diverge.

- [ ] T064 [US2] Implement the per-repository body in `backend/infrahub/git/tasks.py` as an injectable component with a single entry point, in this order: claim the repository by writing this flow's run id to the in-flight key from `git/state/cache_keys.py` with `not_exists=True` and a ceiling derived from the same constant as T066's per-repository timeout plus a margin (a shorter ceiling would expire mid-run and admit a second check), and on a failed claim return the run id already recorded without contacting the remote; resolve the tracked refs and read the local `origin/<ref>` or tag SHA with no lock; validate every ref with `git check-ref-format --allow-onelevel` and refuse on failure; run `git ls-remote origin -- <ref>` with no lock held and with `GIT_HTTP_LOW_SPEED_LIMIT` and `GIT_HTTP_LOW_SPEED_TIME` in the subprocess environment; return if nothing moved; only then take `lock.registry.get(name=<repository_name>, namespace="repository")` around `InfrahubRepositoryBase.fetch()` and the `RefreshGitFetch` broadcast pinned to the tracked commit for each Infrahub branch pinning that ref. Release the in-flight key in a `finally`. Never write `commit` or `ref`, and never call `InfrahubReadOnlyRepository.get_commit_value` or `update_latest_commit`, both of which fetch or write
- [ ] T065 [US2] Add failure handling and observability to the same body: catch `GitCommandError` and the repository errors per repository, record the failure with the repository name and the reason, delete the due key so the next tick retries rather than treating the repository as checked, write the last-checked key with the current timestamp on success and on failure alike, and emit one structured record per detected movement carrying repository, ref, previous head and new head
- [ ] T066 [US2] Implement `check_read_only_repositories_refs` in `backend/infrahub/git/tasks.py`, replacing the T016 stub: resolve read-only repositories via `get_repositories_commit_per_branch(kind=READONLYREPOSITORY)`, apply the due check by writing the due key with `expires=<interval seconds>, not_exists=True` and skip a repository whose write fails, then run each due repository's body as a Prefect `@task` under this flow run with bounded concurrency and a per-repository timeout. Record checked, moved, failed and duration for the tick, and never fail the flow run because one remote is unreachable
- [ ] T067 [US2] Implement `check_read_only_repository_refs` in `backend/infrahub/git/tasks.py` for the on-demand path: no due check, same shared body. The mutation always returns the run it submitted; a run that loses the claim exits without contacting the remote, which is what makes repeated clicks idempotent. Do not attempt to claim in the resolver so the mutation can return the earlier run's id: the claim belongs to the body both paths share, and a request admitted before the first run claims the repository is a race no resolver-side claim closes without a second key

### Block 4.3 [PR 8]: tests

Depends on block 4.2. Four separate files, parallel.

- [ ] T068 [P] [US2] Create `backend/tests/component/git/test_check_refs.py` with recording adapters: a repository not yet due is skipped and one that is due is checked; an unchanged remote produces a refs listing and no fetch and no broadcast; the recorded lock timeline shows the lock taken only around the fetch and the broadcast and never around `ls-remote`; a second trigger while one is in flight performs no remote call and reports the claim it found; a crashed run releases its in-flight key; a repository whose remote is unreachable is recorded with its reason, does not abort the cycle, has its due key deleted, and does not delay a concurrent import of the same repository; the tick record carries checked, moved and failed; `RefreshGitFetch` is broadcast once per Infrahub branch pinning the moved ref with `commit` pinned to the tracked commit rather than the new head; and the due key is written with a TTL taken from the configured interval, so a changed setting spaces the next cycle differently without any schedule rewrite (SC-014)
- [ ] T069 [P] [US2] Add a unit test in `backend/tests/unit/git/` for the ref validation, including a ref starting with `-`, asserting it is refused before any subprocess runs
- [ ] T070 [P] [US2] Create `backend/tests/integration/git/test_readonly_refs_check.py` against Gogs: advance the tracked ref, force-push it, move a tag, and delete a tag. Assert throughout that `commit` is unchanged and the imported commit's content is still readable on the worker (its worktree is the reachability root that makes forcing tag updates safe), that a deleted upstream tag yields `NO_REMOTE` and no exception, and that `RecordingLockRegistry` shows no overlap with a concurrent import under `repository.<name>`
- [ ] T071 [P] [US2] Add a handler-level test that receiving `RefreshGitFetch` with a pinned commit updates the local copy without moving the pin (`update_commit_value=False`), which is the convergence half of this story that no two-worker fixture is used for

### Block 4.4 [PR 9]: frontend and release notes

T073 depends only on checkpoint 2A; T072 depends on T067.

- [ ] T072 [US2] Add the "check remote now" action to `frontend/app/src/entities/repository/ui/repository-commits-tab.tsx`, read-only repositories only, submitting `InfrahubReadOnlyRepositoryCheckRefs`, disabled while a check is in flight, surfacing the returned task id rather than firing a second run. Without it the on-demand half of this story has no entry point outside the API
- [ ] T073 [P] [US2] Extend `frontend/app/src/entities/repository/ui/repository-commits-tab.test.tsx` with the action's states and the freshness line showing a recent `checked_at` above an older `fetched_at`, asserted by accessible name
- [ ] T095 [US2] Extend `tests/e2e/repository/` with the on-demand check against a read-only repository fixture: the action is present for the read-only kind and absent for the read-write kind, triggering it surfaces a task id, and the freshness line's check time advances afterwards even when the remote has not moved. Constitution IV requires e2e for user-facing features and this button is one; it needs a read-only repository in the e2e data set, which `demo_edge_repo` does not provide, so budget the fixture with the task
- [ ] T074 [P] [US2] Add `changelog/ifc-3101-readonly-refs-check.added.md` covering the periodic check, the on-demand action and the new interval setting
- [ ] T075 [US2] Walk quickstart.md "Phase C" and reconcile any divergence

**Checkpoint**: a commit pushed to a read-only repository's tracked ref becomes visible within the
interval with no user action and immediately on demand, and nothing about what Infrahub runs has
moved.

---

## Phase 5 [PR 10]: User Story 3 - See per-branch drift from the branch list (Priority: P3)

**Goal**: the drift query answers with real remote heads for every branch of a repository from a
single worker request, with the column's unavailable state confined to itself.

**Independent Test**: against a repository with 200 branches, three of which are behind, the drift
query returns exactly those three with a differing remote head, in one worker request, with a
database query count identical to a five-branch repository.

**Depends on**: checkpoint 2B (the graph read), block 3.1 (the bounded RPC) and T092 (the log reader,
which T077 extends rather than duplicating). The UI column has no rows to annotate until the IFC-3104
Branches card exists, which is why this story ships as a query.

- [ ] T076 [P] [US3] Create `backend/infrahub/message_bus/messages/git_branch_heads_get.py` with `ROUTING_KEY = "git.branch_heads.get"`, `GitBranchHeadsGet` carrying `branches: list[BranchRefInput]`, plus its response and response data per data-model.md
- [ ] T077 [P] [US3] Add the branch-heads pass to `backend/infrahub/git/state/log_reader.py`: one pass over `get_branches_from_remote()` and the tag refs resolving every row's head with no fetch, classifying each row `NOT_TRACKED` / `NO_REMOTE` / `IN_SYNC` / `BEHIND` / `REWRITTEN` with the T037 functions and no pending count, inside `asyncio.to_thread`. Then create `backend/infrahub/message_bus/operations/git/branch_heads.py` as a shallow handler over it, the same shape as T040. The availability and warm-up path is reached through the reader, not written a second time, which is the whole reason T092 exists
- [ ] T078 [US3] Register the pair in `backend/infrahub/message_bus/messages/__init__.py` and the handler in `backend/infrahub/message_bus/operations/__init__.py`, and add `git.branch_heads.get` to `operations_without_flows` in `backend/tests/unit/message_bus/test_mappings.py`
- [ ] T079 [US3] Implement `branch_heads` on `BusRepositoryGitStateReader` in `backend/infrahub/git/state/bus_reader.py` and remove the drift resolver's column-level `NOT_IMPLEMENTED` state in `backend/infrahub/graphql/queries/repository_git_state.py`, so rows carry their remote head
- [ ] T080 [P] [US3] Create `backend/tests/component/message_bus/operations/git/test_branch_heads.py` on `FileRepo` fixtures: three behind out of many, a branch with no remote counterpart as `NO_REMOTE`, a rewritten branch as `REWRITTEN` with no pending count, a branch with nothing tracked as `NOT_TRACKED`, and the not-cloned path
- [ ] T081 [P] [US3] Extend `backend/tests/component/graphql/queries/test_repository_git_state.py` with `BusRecorder`: exactly one `git.branch_heads.get` message for a repository with 200 branches, and a repository with no answering worker returning its rows with only the column unavailable
- [ ] T082 [P] [US3] Assert in the same suite that the drift query exposes no filtering, ordering or counting argument for drift
- [ ] T083 [P] [US3] Add `changelog/ifc-3101-branch-drift-query.added.md`
- [ ] T084 [US3] Record the hand-off on the IFC-3104 epic: the Branches card consumes `InfrahubRepositoryBranchDrift` for its drift column, and `RepositoryBranchValuesQuery` is the primitive that epic widens to many repositories rather than writing a second one. Sharpen the Dependencies section of `dev/specs/ifc-3101-repo-commit-visibility/spec.md` if its wording needs it
- [ ] T085 [US3] Walk quickstart.md "Phase D" and reconcile any divergence

**Checkpoint**: all three stories are independently functional. The drift column's server side is
complete and waiting only on the sibling card for rows.

---

## Phase 6 [PR 11]: Polish and cross-cutting concerns

T090 and T091 belong to no pull request: they are the pre-push routine run before every one of the
eleven.

- [ ] T086 [P] Verify SC-004 against a repository with 10,000 commits of history: the first page returns in under 2 seconds. Record the measurement in `dev/specs/ifc-3101-repo-commit-visibility/quickstart.md`
- [ ] T087 [P] Add a component test under `backend/tests/component/git/` pinning FR-002 and SC-003: adding a repository with a multi-hundred-commit history produces a stored-node delta independent of history length, and no proposed-change diff entry or merge conflict is attributable to commit data
- [ ] T088 [P] Add user-facing documentation for the commit view and the read-only refs check under `docs/docs/`, decided with the `audit-docs` skill so it lands in the right layer, and covering that commits are read live and never stored, what the two freshness values mean, and that the check never changes what Infrahub runs
- [ ] T089 [P] Add a `dev/knowledge/backend/` page for the repository git-state read path: the reader protocol and its four implementations, the factory as the only wiring point, why the read never clones or locks, the two freshness values and where each comes from, and the four cache keys with `checked_at` being best-effort because the cache is not durable. Link it from `dev/knowledge/backend/git-sync.md`, and note there that the extracted mapping function is the seam the configured-default-branch work will own. Add the frontend counterpart under `dev/knowledge/frontend/` as well, per the constitution's Documentation Requirements: the `api/ -> domain/ -> ui/` chain for the Commits tab, the polling rule and why it keeps previous data, and where the two freshness values are rendered
- [ ] T090 Run `uv run invoke format`, `uv run invoke lint`, `ruff check . --exclude python_sdk`, `cd frontend/app && pnpm biome:fix && pnpm knip`, then `/pre-ci`
- [ ] T091 Walk quickstart.md "Phase E" and the "Before pushing" block end to end, and confirm every generated artefact is committed (`uv run invoke docs.validate`, `uv run invoke schema.validate-graphqlschema`, `pnpm codegen` with a clean diff)

---

## Dependencies and execution order

### Phase dependencies

- **Phase 1 (Setup)**: no dependencies. T001 gates Phase 2
- **Phase 2 (Foundational)**: blocks all three stories. Internally: 2.1 → 2.2 → 2.3 → 2.4 → 2.6, with
  2.5 branching off 2.1 and mergeable either side of checkpoint 2A
- **Phase 3 (US1, P1)**: needs checkpoint 2A. Block 3.5 needs nothing else
- **Phase 4 (US2, P2)**: needs checkpoint 2A. Does not need Phase 3
- **Phase 5 (US3, P3)**: needs checkpoint 2B and block 3.1
- **Phase 6 (Polish)**: needs the stories being shipped

### Story dependencies

- **US1** is self-contained on top of Phase 2 and is the MVP
- **US2** is independent of US1 on the backend. Its frontend action (T072) extends the tab US1 builds,
  so if US2 ships first, that action lands with US1's tab instead
- **US3** shares the bounded RPC (block 3.1) and the classification functions (T037) with US1. That is
  the one cross-story edge, and it is harmless because US3 is last in priority. If US3 must ship
  before US1, block 3.1 and T037 move ahead of it unchanged

### The one ordering that matters most

T021 and T022 (the per-branch graph query and the tests that pin its inheritance behaviour) are
ordered tests-first deliberately. The resolution being reproduced is subtle: `commit` is `LOCAL` on a
branch-agnostic node, so its creation edge lands on the global branch and a branch that never imported
inherits its origin branch's fork-point value rather than null, and a rebase moves that inherited
value forward with no git activity on the branch. Origin branch, not default branch: the two usually
coincide and the tests must not assume they always do. Pinning it before anything depends on it means a
regression changes a test rather than silently changing what every branch reports.

### Parallel opportunities

- Phase 1: T002 and T094 alongside T001; T094 then runs on its own track through Phase 2
- Block 2.1: T003, T004, T005 together (T006 goes earlier, with PR 1)
- Block 2.2: T009 alongside T007 and T008
- Block 2.3: T010, T011, T015, T016 together, then T012 → T013 → T014 → T017
- Block 2.4: T018, T019, T020 together
- Block 2.5 in full, alongside blocks 2.2 to 2.4
- Block 3.2 during Phase 2, once T003 and T004 land
- Block 3.5 (six of ten tasks parallel) from checkpoint 2A, alongside the whole backend of Phase 3
- Block 3.3: T092 first, then T039 and T040 together, then T043 and T044 together
- Block 3.4: T048 and T093 together
- Phase 4: T061, T062, T063 together; T068 to T071 together; T095 after T072
- Phase 5: T076 and T077 together; T080 to T083 together
- Phase 6: T086 to T089 together

### Parallel example: the frontend and the worker read

```text
# Immediately after checkpoint 2A, two tracks with no shared file:
Track A (backend):  T029 → T030 → T031 → T033 → T035        (bounded RPC PR)
                    T092 → T039 ∥ T040 → T041 → T042 → T045 ∥ T093 → T046
Track B (frontend): T049 ∥ T050 ∥ T051 ∥ T052 → T053 → T054 → T055 → T056 ∥ T057
```

---

## Implementation strategy

### Fastest path to a frontend hand-off

1. T001, T002, and T094 started on its own track
2. PR 2: blocks 2.1 to 2.4 and 2.6 (2.5 is PR 3 and is not on this path)
3. **Stop and hand off**: `schema/schema.graphql` and the generated frontend types carry the whole
   surface. The frontend has real repository, branch, ref and imported-commit values, an honest
   unavailable state to build against, and Vitest fixtures for the two states no live repository can
   produce
4. PR 3: block 2.5

### MVP (User Story 1 only): six pull requests

1. PR 1 and PR 2 (Phase 1, Phase 2)
2. PR 4: block 3.1, on its own because it is a shared path
3. PR 5 (blocks 3.2 to 3.4) and PR 6 (block 3.5) in parallel, then PR 7 (block 3.6), folded into
   whichever of PR 5 and PR 6 lands second
4. **Stop and validate**: quickstart.md "Phase B" against a `FileRepo` fixture
5. Ship. Read-write repositories now have the whole of this feature's value

### Incremental delivery

1. Phase 2 (PRs 2 and 3) → contract published, frontend unblocked
2. Phase 3 (PRs 4 to 7) → the commit view answers for real (MVP, demo-able)
3. Phase 4 (PRs 8 and 9) → read-only repositories stop being blind (demo-able on its own by
   advancing a fixture remote)
4. Phase 5 (PR 10) → the drift column's server side, waiting on IFC-3104 for rows
5. Phase 6 (PR 11) → documentation, measurements, pre-CI

Each phase is independently reviewable and shippable, and none breaks the one before it.

### Parallel team strategy

With three developers after checkpoint 2A:

- Developer A: PR 4 (bounded RPC, shared path), then PR 5 (blocks 3.2 to 3.4)
- Developer B: PR 6 (Commits tab) against the published contract
- Developer C: PR 3 (graph read), then PR 8 (Phase 4)

PR 10 then needs only T076 to T083 from whoever is free, since its prerequisites are already in.
The eleven pull requests do not shrink under parallelism; the elapsed time does.

---

## Notes

- `[P]` means a different file and no dependency on an incomplete task
- The feature writes nothing to the graph: no schema change, no migration, and no write to `commit` or
  `ref` anywhere. No task below requires one; if implementing one seems to, stop and reconcile it
  against `spec.md` before writing the write
- Generated artefacts are regenerated in the phase whose source change makes them stale, never
  hand-edited: `schema/schema.graphql` and the frontend GraphQL types in block 2.6, the error
  catalogue and configuration reference in block 3.1, the configuration reference again in block 4.1.
  CI fails on a stale generated file
- Commit after each task or coherent block, and add the changelog fragment in the same commit as the
  user-visible change it describes
- Stop at any checkpoint to validate a story on its own
