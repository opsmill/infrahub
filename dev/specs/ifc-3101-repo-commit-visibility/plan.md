# Implementation Plan: Git Repository Commit Visibility

**Branch**: `pog-repo-commit-visibility-ifc-3101` | **Date**: 2026-09-03 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/ifc-3101-repo-commit-visibility/spec.md`, plus the
direction to deliver the GraphQL API first, with sample data if necessary, so the frontend team can
start immediately.

## Summary

Expose a repository's git state on the request branch through two new top-level GraphQL queries
(`InfrahubRepositoryCommits`, a paged newest-first commit log with per-commit state and the imported
and remote-head markers; `InfrahubRepositoryBranchDrift`, per-branch drift from one worker request)
and one mutation (`InfrahubReadOnlyRepositoryCheckRefs`). Commits are read live from a task worker's
existing clone over a point-to-point message-bus RPC with a bounded wait; they are never stored.
Infrahub's own per-branch tracked values for the drift list come from one new Cypher query rather
than one query per branch.
Read-only repositories gain an every-minute cron flow that, per repository and on a configurable
interval, lists remote refs and fetches only when the tracked ref moved, then converges every worker
through the existing `RefreshGitFetch` broadcast without ever writing the tracked commit.

The contract lands first (Phase A): full SDL, permission enforcement, the per-branch graph query, and
a reader seam that answers `UNAVAILABLE / NOT_IMPLEMENTED` until the worker read lands. The frontend
team builds against the regenerated `schema/schema.graphql`, which is what actually unblocks them,
since nothing in the frontend reads a live server schema. Phases B to D add the bounded RPC, the
worker read and the refs check.

## Technical Context

**Language/Version**: Python 3.14 (backend), TypeScript 5.9 / React 19.2 (frontend)
**Primary Dependencies**: graphene (existing), GitPython 3.1.61 (existing; `Repo.is_ancestor`,
`Repo.iter_commits`, `git.rev_list`), Prefect via `infrahub.workflows` (existing), the RabbitMQ
message bus (existing; the NATS adapter is edited for signature parity only and is not a supported
driver, see research.md), TanStack Query v5 and gql.tada (existing)
**Storage**: none new. Four short-lived cache keys in the existing `service.cache`: warm-up
collapsing, the refs-check due marker, the in-flight guard, and the last-checked timestamp
**Testing**: pytest unit (`backend/tests/unit/`), component with testcontainers
(`backend/tests/component/`), integration with a Gogs remote (`backend/tests/integration/git/`),
Vitest browser mode, pytest-playwright e2e (`tests/e2e/`)
**Target Platform**: Infrahub API server plus task workers, Linux containers
**Project Type**: web application (backend + frontend)
**Performance Goals**: first commit page under 2 seconds for a 10,000-commit history (SC-004);
drift for 200 branches in one worker request (SC-005); an idle read-only repository costs one
`ls-remote` per interval (FR-018)
**Constraints**: no synchronous clone inside a read (FR-013); worker wait bounded by
`broker.rpc_timeout` with a catalogued error (FR-012); no write to `commit` or `ref` anywhere in this
feature (FR-016); no graph schema change; `schema/schema.graphql` must stay environment-independent
**Scale/Scope**: 3 GraphQL operations, 1 Cypher query class, 2 RPC message pairs, 3 workflow
definitions, 2 settings, 1 catalogue error, 1 frontend tab plus one query chain; one shared-path
change to `InfrahubMessageBus.rpc`

All Technical Context unknowns were resolved in [research.md](research.md); no NEEDS CLARIFICATION
remains.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Schema-Driven Integrity | PASS | No node, attribute or migration. Generated files are regenerated, never edited: `schema/schema.graphql`, frontend GraphQL types, error-catalogue artefacts, configuration reference. |
| II. Branch-Safe by Default | PASS | Every answer is computed for `graphql_context.branch`: the imported commit is the branch-local or branch-aware `commit`, the read-only `ref` is branch-aware, and the remote branch is mapped through `_get_mapped_remote_branch`. Nothing is written, so merge behaviour is unchanged (SC-011). |
| III. Type Safety & Explicit Contracts | PASS | SDL defined before implementation (`contracts/`); frozen dataclasses in `infrahub.git.state.models`; Pydantic message models at the bus boundary; `RepositoryGitStateReader` protocol returning those dataclasses, never a wire model; frontend uses gql.tada-derived types. |
| IV. Test Discipline | PASS | Unit tests for classification; component tests for the per-branch query, resolvers, permission denial, laziness, RPC timeout, handlers; integration tests for behind, rewritten, tag move, lock serialisation; e2e for the Commits tab. Test adapters (`BusRecorder`, `WorkflowRecorder`, `RecordingLockRegistry`) instead of mocks. |
| V. Query Performance & Efficiency | PASS | Worker cost per page is constant in history length (`iter_commits` with skip and at most `limit` ancestry checks). Graph side: the drift list reads every branch's tracked values in one parameterised query (`core/query/repository.py`), so the query count is independent of branch count, asserted by instrumentation at 5 and 200 branches. The existing per-branch sync helper is left untouched; IFC-3104 refactors it onto the same query. |
| VI. Security & Input Boundaries | PASS | `limit` bounded to 1..100 and `offset` non-negative in the resolver; repository view permission enforced imperatively (the analyzer cannot see custom queries); timeout error message names the operation only, never the worker or paths; credentials for `ls-remote` come from the worker's existing git config, never from the message. |
| VII. Simplicity & Maintainability | PASS | Reuses `GitFileGet`, `RefreshGitFetch`, `WorkflowDefinition` cron with `CANCEL_NEW`, cache `not_exists`, `define_object_permission_from_branch`, and `get_repositories_commit_per_branch` for the refs-check flow's repository list. The reader protocol earns its place by keeping the message-bus dependency out of the resolver, and its second and third implementations are the test doubles. The one new abstraction, `RepositoryBranchValuesQuery`, is required by Principle V rather than anticipated: it follows the existing Query-class pattern, has a caller in this feature, and a second in IFC-3104. No sample-data path, no throwaway setting. No new dependency. |

**Verdict**: all gates pass. No complexity justification required. Re-evaluated after Phase 1 design:
unchanged.

**Governance ("Ask First")**: signed off by Patrick Ogenstad on 2026-09-04, covering the additive
GraphQL query and mutation surface (`InfrahubRepositoryCommits`, `InfrahubRepositoryBranchDrift`,
`InfrahubReadOnlyRepositoryCheckRefs`) and both new configuration settings.

The GraphQL half is definitional rather than a choice: the feature is two new queries and a mutation,
so the schema necessarily changes. `BrokerSettings.rpc_timeout` is the part of the sign-off with
substance, because it changes behaviour for callers this feature does not add:
`infrahub.api.file::get_file` and `ValidateRepositoryConnectivity` go from an unbounded wait to a
failure at 30 seconds. That is the intended shared-path change, 30 seconds is the agreed default, and
a worker slow enough to have previously answered late will now return a catalogued 504 instead. It
lands as its own reviewed pull request (Phase B1).

## Project Structure

### Documentation (this feature)

```text
specs/ifc-3101-repo-commit-visibility/
├── spec.md
├── plan.md                              # This file
├── research.md                          # Phase 0 decisions
├── data-model.md                        # enums, value objects, messages, cache keys, settings
├── quickstart.md                        # validation scenarios per phase
├── contracts/
│   ├── repository_git_state.graphql     # GraphQL SDL, examples, error contract
│   └── message_bus.md                   # RPC pairs, rpc timeout, reused broadcast
├── checklists/requirements.md           # spec quality gate, plus the recorded decisions and deviations
├── critiques/                           # dual-lens critique output, archived against the draft it reviewed
└── tasks.md                             # Phase 2 output (/speckit-tasks, not created here)
```

### Source Code (repository root)

```text
backend/infrahub/
├── core/constants/__init__.py                    # EDIT  RepositoryGitCondition, RepositoryCommitState, RepositoryGitUnavailableReason
├── core/query/repository.py                      # NEW   RepositoryBranchValuesQuery: per-branch attribute values for one
│                                                 #       repository in a single query, explicit branch list and attribute set
├── config.py                                     # EDIT  BrokerSettings.rpc_timeout, GitSettings.read_only_refs_check_interval_mins
├── exceptions.py                                 # EDIT  WorkerTimeoutError
├── errors/{catalogue,payloads}.py                # EDIT  WORKER_TIMEOUT, WorkerTimeoutData
├── graphql/error_formatter.py                    # EDIT  payload case for WORKER_TIMEOUT
├── graphql/types/repository.py                   # NEW   graphene types and enums from contracts/
├── graphql/queries/repository_git_state.py       # NEW   two resolvers only; the reader lives under git/state/
├── graphql/queries/__init__.py                   # EDIT  export
├── graphql/mutations/repository.py               # EDIT  ReadOnlyRepositoryCheckRefs
├── graphql/schema.py                             # EDIT  register query fields and mutation
├── git/state/models.py                           # NEW   frozen dataclasses: requests, results, CommitEntry, GitStateFacts
├── git/state/classification.py                   # NEW   pure classification, no I/O
├── git/state/reader.py                           # NEW   RepositoryGitStateReader protocol + Unavailable implementation
├── git/state/factory.py                          # NEW   build_repository_git_state_reader, the only wiring point
├── git/state/bus_reader.py                       # NEW   BusRepositoryGitStateReader, the only module knowing a routing key
├── git/state/log_reader.py                       # NEW   every git read against an existing clone; both handlers are thin over it
├── git/state/cache_keys.py                       # NEW   prefix + the four key builders, shared by resolver and flows
├── git/branch_mapping.py                         # NEW   extracted remote-branch mapping, required parameters, no fallback
├── git/base.py                                   # EDIT  _get_mapped_remote_branch delegates to branch_mapping
├── git/models.py                                 # EDIT  GitRepositoryWarmUp, GitReadOnlyRepositoryCheckRefs
├── git/tasks.py                                  # EDIT  warm_up_git_repository, check_read_only_repositories_refs,
│                                                 #       check_read_only_repository_refs
├── workflows/catalogue.py                        # EDIT  three WorkflowDefinition constants
├── message_bus/messages/git_commit_log_get.py    # NEW
├── message_bus/messages/git_branch_heads_get.py  # NEW
├── message_bus/messages/__init__.py              # EDIT  MESSAGE_MAP, RESPONSE_MAP, PRIORITY_MAP
├── message_bus/operations/git/commit_log.py      # NEW   shallow handler: unpack, delegate to log_reader, reply
├── message_bus/operations/git/branch_heads.py    # NEW   shallow handler, same shape
├── message_bus/operations/__init__.py            # EDIT  COMMAND_MAP
└── services/adapters/message_bus/{__init__,rabbitmq,nats,local}.py   # EDIT  rpc(timeout=...)

backend/tests/
├── helpers/repository_git_state.py                               # NEW  Recording and Failing reader doubles
├── unit/git/state/test_classification.py                         # NEW  parametrised, no fixtures
├── unit/git/state/test_bus_reader.py                             # NEW  routing key, timeout, reply mapping
├── unit/git/                                                     # NEW  ref-format validation, including a "-" prefixed ref
├── unit/errors/                                                  # existing suites gain WORKER_TIMEOUT via parametrisation
├── unit/workflows/test_catalogue.py                              # existing, picks up new definitions
├── component/git/                                                # NEW  FR-002 stored-node delta independent of history length
├── component/core/query/test_repository_branch_values.py         # NEW  per-branch resolution, inheritance, query count at 5 vs 200 branches
├── component/graphql/queries/test_repository_git_state.py        # NEW  resolvers, permission, laziness
├── component/graphql/mutations/test_repository.py                # EDIT  check-refs mutation with WorkflowRecorder
├── component/services/adapters/message_bus/test_rpc_timeout.py   # NEW
├── component/message_bus/operations/git/test_commit_log.py       # NEW  handler on FileRepo fixtures, NOT_CLONED path
├── component/message_bus/operations/git/test_branch_heads.py     # NEW
├── component/git/test_check_refs.py                              # NEW  due check, ls-remote only when idle, lock scope
├── integration/git/test_repository_commits_query.py              # NEW  GraphQL query end to end through a real worker read, plus laziness
└── integration/git/test_readonly_refs_check.py                   # NEW  Gogs: advance, force-push, tag move, tag delete

schema/schema.graphql                                             # REGEN
schema/error-catalogue.json                                       # REGEN
docs/docs/reference/{configuration,error-catalogue}.mdx           # REGEN
docker-compose.yml, development/docker-compose.yml                # REGEN / EDIT  new env vars
changelog/                                                        # NEW   fragments per user-visible change

frontend/app/src/
├── shared/api/graphql/generated/{graphql-env.d.ts,graphql-cache.d.ts,types.ts}   # REGEN
├── shared/api/errors/catalogue.generated.ts                                       # REGEN
├── entities/repository/api/get-repository-commits-from-api.ts                     # NEW
├── entities/repository/domain/use-cases/get-repository-commits.ts                 # NEW
├── entities/repository/domain/rules/is-git-state-available.ts                     # NEW  pure predicate for polling
├── entities/repository/ui/queries/get-repository-commits.query.ts                 # NEW  refetchInterval while UNAVAILABLE
├── entities/repository/ui/queries/repository.query-keys.ts                        # NEW or EDIT
├── entities/repository/ui/repository-commits-tab.tsx                              # NEW  list, markers, copy hash, freshness
├── entities/repository/domain/model/repository.ts                                 # EDIT  REPOSITORY_COMMITS_TAB
├── entities/nodes/object/ui/object-details/object-details-tabs.tsx                # EDIT  Commits tab, isOfKind gate
├── pages/objects/object-details/repository-commits.tsx                            # NEW  route element
└── app/router.tsx                                                                 # EDIT  nested route

tests/e2e/repository/test_repository_commits.py                                    # NEW  shard_branches_repo
```

**Structure Decision**: web application layout, backend and frontend in their existing trees.
Backend additions follow the three-file GraphQL convention (`types/`, `queries/`, `schema.py`), the
message-bus convention (`messages/`, `operations/`), the Query-class pattern in
`dev/knowledge/backend/query-pattern.md` for the new graph read, and the git module split (pure logic
in a new module, I/O in `tasks.py` and the handlers). Frontend additions follow the `api/ -> domain/ -> ui/`
chain under `entities/repository/` and plug into the generic object detail page the way the existing
`repository_objects` tab does.

## Delivery Phases

Ordered for the fastest frontend hand-off. Each phase is independently reviewable and shippable.

### Phase A: contract and the graph read (frontend unblocked)

- Enums in `infrahub.core.constants`; graphene types in `graphql/types/repository.py`;
  `InfrahubRepositoryCommits`, `InfrahubRepositoryBranchDrift` and
  `InfrahubReadOnlyRepositoryCheckRefs` registered.
- Resolvers do the real Infrahub-side work: load the repository on the request branch, enforce view
  (queries) or update (mutation) permission with `define_object_permission_from_branch`, read the
  imported commit and the branch or ref, validate `limit` and `offset`, gate `pending_count` on
  selection with `extract_graphql_fields`. There is no `count` field to gate: FR-024 removes the
  total from the contract entirely.
- `RepositoryBranchValuesQuery` in `core/query/repository.py`: one statement returning the
  branch-resolved `commit`, and `ref` for the read-only kind, for one repository across an explicit
  branch list, with an explicit attribute-name set and a frozen-dataclass `get_data()`. It unwinds a
  per-branch scope (target branch, origin branch, fork-point time, query time) and applies the
  standard edge-activity predicate per scope with `ORDER BY branch_level DESC, from DESC, status ASC
  LIMIT 1` plus the active-status check, reproducing today's per-branch resolution including
  fork-point inheritance. Shape follows `core/diff/query/artifact.py` for multi-branch value reads
  and `core/query/diff.py::DiffCountChanges` for the row-per-branch return. Row set per the spec:
  branches synchronised with Git for the read-write kind, every branch for the read-only kind,
  excluding merged and deleting branches and the global branch. The drift resolver is its only caller
  in this feature; the periodic-sync helper is not touched.
- `RepositoryGitStateReader` protocol, with the worker reader as its only production implementation
  (see the sizing note below). No sample reader, no experimental setting. Until the Phase B2 handlers
  land, the protocol's placeholder answers `UNAVAILABLE / NOT_IMPLEMENTED`, which is a state the
  frontend must handle anyway.
- The mutation submits the `GIT_READ_ONLY_REPOSITORY_CHECK_REFS` workflow definition, whose flow body
  in this phase logs and returns; the definition must exist for
  `tests/unit/workflows/test_catalogue.py` to pass.
- Regenerate `schema/schema.graphql`, frontend GraphQL types, configuration reference, compose env.
- Changelog fragment (`added`), tests listed above for this phase.

### Phase B1: bounded RPC (shared path, own pull request)

- `InfrahubMessageBus.rpc(timeout=...)` across the three adapters, `BrokerSettings.rpc_timeout`,
  `WorkerTimeoutError`, `WORKER_TIMEOUT` catalogue entry and payload, formatter case, regenerated
  error-catalogue artefacts, component test with `BusRPCMock` that never replies.
- Not included: the `get_file` / `raise_for_status()` defect. Bounding the wait does leave that
  endpoint temporarily incoherent (504 on a hang, 200 on a worker-side error), and an earlier draft
  of this plan fixed it here on the grounds that this is already the reviewed change to that call
  path. It is unrelated to commit visibility and the PRD scopes this shared-path change to the
  bounded wait alone, so it now has its own ticket. Sequence that ticket immediately after this
  phase to close the window.

### Phase B2: worker read path

- `infrahub.git.state.classification` pure classification; `infrahub.git.state.log_reader` owning
  every git read against the clone plus the availability check and the collapsed warm-up, so both
  handlers stay shallow; `GitCommitLogGet` and `GitBranchHeadsGet` message pairs; handlers that never
  clone, never lock, never fetch; `NOT_CLONED` reply with collapsed warm-up via cache `not_exists`
  and `GIT_REPOSITORY_WARM_UP`; `BusRepositoryGitStateReader` replaces the placeholder through the
  factory, which is the only edit any consumer sees.
- The git work in both handlers runs in `asyncio.to_thread`. GitPython drives subprocesses
  synchronously, and one page is a head resolution, an ancestry check, up to `limit` per-commit
  ancestry checks and a paged walk. On the handler's event loop that stalls every other message the
  worker is serving, and the commit tab polls while unavailable. Page size stays bounded at 100 by
  the resolver; no lower cap is imposed, because with the work off the loop the cost is the caller's
  own latency and the default page is 10.
- Component tests on `FileRepo` fixtures (behind, in sync, rewritten via force-push to the
  `receive.denyCurrentBranch=ignore` remote, not cloned, paging, laziness), `BusRecorder` assertion of
  a single `git.branch_heads.get` for N branches, and an assertion that a handler invocation does not
  block a concurrent message on the same worker.

**Sizing note (why there is no sample reader).** Measured against the existing git file read, which is
the template: the message pair is 27 lines, its handler is 36, and registration is four one-line
entries plus one command-map line. The git work itself is five calls, four of which already exist in
the git module minus their fetches (head resolution, ancestry, paged iteration, a pending count, a
`FETCH_HEAD` stat), and the classification is pure logic that needs unit tests either way. A
deterministic sample reader would cost a comparable amount, plus a determinism test, a configuration
setting, a public configuration-reference entry, a compose mapping and its own removal, all of it
discarded. The two states a frontend developer cannot conjure against a live repository, rewritten and
not-cloned, are covered by Vitest fixtures, which is where UI-state tests belong. If a server-side
fake is wanted before B2 lands, it returns literal placeholder strings behind the flag with no
determinism logic, no test and no documentation entry.

### Phase C: read-only refs check

- `check_read_only_repositories_refs` cron flow with due check on `git:refs_check:due:<id>` and
  `GitSettings.read_only_refs_check_interval_mins`; `check_read_only_repository_refs` per-repository
  flow submitted by the mutation. Both delegate to one shared body so the scheduled and on-demand
  paths cannot diverge.
- **No off switch.** `read_only_refs_check_interval_mins` stays `ge=1`, matching
  `CacheSettings.clean_up_deadlocks_interval_mins`, the nearest analogue. Lengthening the interval is
  the control for a check judged too frequent. Of the five cron workflows in the catalogue, only
  anonymous telemetry can be disabled, and that is a privacy opt-out rather than an operational kill
  switch; the git sync, deadlock cleanup, webhook configure and merge watcher have none. An idle
  repository costs one refs listing per interval and no content transfer, which is strictly less than
  the every-minute sync already does for read-write repositories.
- **Lock scope (FR-019).** The lock wraps only the steps that touch the local copy. Order per
  repository: resolve the tracked refs and read the local `origin/<ref>` or tag SHA, then
  `git ls-remote origin <ref>` with **no lock held**, then return if nothing moved (FR-018), then take
  `lock.registry.get(name=<repository_name>, namespace="repository")` around
  `InfrahubRepositoryBase.fetch()` and the `RefreshGitFetch` broadcast. A hung remote therefore cannot
  block an import. Ref values are validated with `git check-ref-format --allow-onelevel` before
  reaching the command line, and the network call runs with git's low-speed abort configured
  (`GIT_HTTP_LOW_SPEED_LIMIT` / `GIT_HTTP_LOW_SPEED_TIME` in the subprocess environment) so an
  unresponsive remote fails instead of hanging for the life of the tick.
- **Non-accumulation (FR-025).** Before doing any remote work, the shared body claims the repository
  with `cache.set(key=<running key>, value=<this flow's run id>, expires=<per-run ceiling>,
  not_exists=True)` and returns the recorded run id without contacting the remote when the claim
  fails. The value is the flow-run id rather than the worker identity for two reasons: the caller has
  to be able to name the run in progress, and this value reaches a user through the mutation, where
  worker identity does not belong (Principle VI, the same reason `answered_by` was dropped from the
  response). The ceiling comes from the same constant as the per-repository timeout plus a margin; a
  shorter ceiling would expire while a slow check was still running and admit a second one. The key is
  deleted in a `finally` so a crashed run does not lock the repository out for the whole ceiling.
  `CANCEL_NEW` on the cron definition remains, and now covers only whole ticks.

  The claim lives in the body, not in the mutation resolver, so the scheduled and on-demand paths
  cannot diverge. The consequence, made explicit in FR-025 and in the quickstart, is that a request
  admitted before the first run claims the repository submits its own run, which then finds the claim
  and exits without contacting the remote. One check performs remote work; the mutation does not
  promise that ten concurrent callers all receive one task id. Closing that window in the resolver
  would need a second key and a second claim protocol for no behavioural gain.
- **Failure handling (FR-026).** The per-repository body catches `GitCommandError` and the repository
  errors, records the failure with repository name and reason, and lets the cycle continue. On failure
  the `git:refs_check:due:<id>` due key is **deleted**, so the next tick retries rather than treating the
  repository as checked; on success it is left to expire naturally, which is what spaces the checks.
  The cycle records a failure count and never fails the flow run because one remote is unreachable.
- **Cycle shape.** The cron flow resolves the due repositories, then runs each repository's body as a
  Prefect `@task` under its own flow run with bounded concurrency and a per-repository timeout, rather
  than awaiting them one after another. One slow remote then cannot consume the tick and delay every
  other repository, and the work stays nested under the tick in the task list instead of creating a
  user-visible flow run per repository per tick. The burst is bounded because the due check already
  spreads repositories across ticks: with the default interval and the every-minute cron, roughly a
  fifteenth of read-only repositories come due on any given tick.
- **Observability (FR-027).** One structured record per tick carrying checked, moved, failed and
  duration, and one per detected movement carrying repository, ref, previous head and new head.
  Failures carry repository and reason. No metrics stack is introduced for this.
- **Check time (FR-007).** Every check writes `git:refs_check:last:<id>` with the current timestamp,
  on success and on failure alike, so `checked_at` reflects the last attempt rather than the last
  success. The resolver reads it; nothing on the worker records it, because a refs listing writes no
  file.
- **Ref hardening (FR-019, security).** Ref values are validated with
  `git check-ref-format --allow-onelevel` at the flow edge and refused on failure, and `--` precedes
  ref arguments wherever the git subcommand accepts it, so safety does not rest on argument order.
  Unit test with a `-` prefixed ref.
- Integration tests against Gogs: advance, force-push, move tag, delete tag; assert `commit`
  unchanged, the imported commit's content still readable on the worker under test,
  `RecordingLockRegistry` shows no overlap with an import, and the lock is never held across the
  `ls-remote` call.
- Component tests for the operational behaviour: a repository whose remote is unreachable is
  recorded, does not abort the cycle, and has its due key cleared so the next tick retries it; a
  second trigger while one is in flight starts no second run and returns the in-flight task id; a
  crashed run releases its in-flight key; the cycle record carries the three counts and a movement
  record carries both commits.
- Convergence (FR-017) is verified with a `BusRecorder` assertion that the check broadcasts
  `RefreshGitFetch` with `commit` pinned to the tracked commit for each Infrahub branch pinning that
  ref, plus a handler-level test that receiving it updates the copy without moving the pin. No
  two-worker fixture in this slice: per-worker delivery is the existing broadcast's behaviour on the
  supported driver, where each git worker holds its own exclusive queue.
- Changelog fragment (`added`) and the configuration reference regenerated.

### Phase D: frontend

- Commits tab on the repository detail page with markers, per-row state, `CopyToClipboardButton`
  for the full hash, `DateDisplay fullTimestamp` for `fetched_at`, `Pagination` with
  `usePagination`, `NoDataFound` for `UNAVAILABLE`, polling while unavailable, `REWRITTEN` banner.
- Freshness line shows `checked_at` when present and `fetched_at` otherwise, so a quiet read-only
  repository reads as recently checked rather than weeks stale. Both are shown when they differ.
- "Check remote now" action, read-only repositories only, submitting
  `InfrahubReadOnlyRepositoryCheckRefs`. Disabled while a check is in flight, and it surfaces the
  returned task id rather than firing a second run (FR-025). Without it the on-demand half of
  User Story 2 has no entry point outside the API, which matters because the interval stays at 15
  minutes.
- Polling keeps the loaded page: `placeholderData: keepPreviousData` (or the equivalent) so a cold
  worker answering a later poll with `UNAVAILABLE` cannot blank a populated list. The
  not-yet-available state renders only when there is no previous data.
- Accessibility (FR-028): each commit state and each marker carries a text label or an icon with an
  accessible name, never colour alone, and the copy action announces completion. Asserted in the
  Vitest tests by querying on accessible names rather than on classes.
- The drift column is specified (`InfrahubRepositoryBranchDrift` is live) but has no rows until the
  IFC-3104 Branches card exists; User Story 3's UI is tracked against that card.
- Vitest tests for the tab, the polling predicate, the keep-previous-data behaviour and the
  accessible names; e2e test on `demo_edge_repo`.
- The e2e suite asserts against a repository seeded already behind, with the sync tick awaited once
  in a fixture, rather than pushing mid-test and waiting out the one-minute cron. A fixed
  minute of wall time per run is both slow and a standing flake risk; the push-then-observe
  transition is covered at component level on `FileRepo` instead.

## Risks and Open Items

| Item | Handling |
| --- | --- |
| `get_file` ignores `RPCErrorResponse` and returns 200 with an empty body | Pre-existing, and made more visible by the bounded wait since a hang now returns 504 while a worker-side error still returns 200. Its own ticket, not fixed here; sequence it after Phase B1 |
| IFC-3104 owns a paginated, filterable branch-status query and the periodic-sync refactor over the same per-branch data | The single-repository query built here is the primitive both need. That epic extends it (many repositories, server-side filters, ordering, paging) instead of writing a second one; coordination recorded on the epic |
| The per-branch resolution the new query must reproduce is subtle: the read-write `commit` attribute is branch-local on a branch-agnostic node, so its creation edge sits on the global branch and a never-imported branch inherits the origin branch's fork-point value | Pinned by tests before the resolver uses it (inheritance, post-import, post-rebase), so a regression changes a test rather than silently changing what every branch reports |
| A cold worker for an idle read-only repository stays cold until a read triggers warm-up | By design (spec edge case); the `NOT_CLONED` state plus warm-up covers it |
| The repository page's existing status badge reflects the default branch only, so it can read "in sync" above a branch-scoped Commits tab reporting drift | Deferred as a design question, 2026-09-04. Not blocking: the badge is IFC-3104 and INFP-670 territory, and this feature neither reads nor changes it. Revisit when the Branches card lands |
| The contract ships before any git-derived answer exists, so a release cut between Phase A and Phase B2 exposes a query that only ever reports unavailable | Accepted, and preferred to fabricated commits reaching a release. `UNAVAILABLE / NOT_IMPLEMENTED` is honest, is a state the UI must handle regardless, and the Commits tab is not linked until Phase D |
| [PRD: Honour the configured repository default branch across the pipeline](https://opsmill.atlassian.net/wiki/spaces/Product/pages/858357761) (INFP-670, IFC-2870) restructures the same branch-mapping code | Not a dependency in either direction, and neither work needs the other first. The defect it guards against is the optional `default_branch_name` field feeding `InfrahubRepositoryBase.default_branch`, whose `or registry.default_branch` silently substitutes Infrahub's default branch when a call site did not supply the trunk. This feature never goes near that: the resolver reads the repository's `default_branch` attribute from the graph on the request branch, and that attribute is mandatory with `default_value="main"`, so there is no unset case and no fallback to write. What travels in the message is the resolved remote ref for one read, not the trunk as a configuration input, so it cannot be the second entry point for an unset value that its FR-003 and message-model cleanup are closing. The one genuine overlap is the mapping rule, extracted once into `infrahub.git.branch_mapping` with the existing method delegating, so the branch-role split inherits a single named function with required parameters instead of reconciling two copies. Coordination recorded on that epic. Three second-order notes: this feature's Commits tab becomes a diagnostic surface for exactly the defect that PRD fixes, since it shows the configured trunk's log while other pipeline paths may still read Infrahub's default branch; that PRD's P2 connect-time discovery needs the same hardened `ls-remote` primitive as the refs check here, so whichever lands second reuses it; and its P3 skipped-branch condition cannot be carried by `InfrahubRepositoryBranchDrift`, both because that PRD wants persistent state and because a colliding branch Infrahub deliberately does not import falls outside this query's row set |

## Complexity Tracking

No constitution violations to justify.
