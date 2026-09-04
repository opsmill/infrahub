# Research: Git Repository Commit Visibility

**Feature**: IFC-3101 | **Branch**: `pog-repo-commit-visibility-ifc-3101` | **Date**: 2026-09-03

Phase 0 output. Every unknown from the plan's Technical Context is resolved here as a decision with
rationale and the alternatives that were weighed. Code is cited as `module::symbol`; line numbers
are deliberately absent.

## Delivery order: contract first

**Decision**: Ship the GraphQL contract as the first pull request, with resolvers that are real for
everything the API server can answer alone (repository lookup, permission check, imported commit,
branch or ref name, and the per-branch graph read) and delegate the git-derived part to a
`RepositoryGitStateReader` protocol. The worker reader is the protocol's only production
implementation. Until it is wired, the seam answers `condition = UNAVAILABLE` and
`unavailable.reason = NOT_IMPLEMENTED`, which is an honest state the frontend has to handle anyway.
No sample-data reader and no experimental setting.

**Rationale**: `schema/schema.graphql` is a checked-in file that the frontend types against via
gql.tada (`frontend/app/tsconfig.json`) and graphql-codegen (`frontend/app/graphql.config.ts`);
nothing in the frontend reads a live server schema. Landing the SDL once, unconditionally, is what
unblocks the frontend team, and it does so whether or not any server can yet answer with commits.
Gating the *schema* on a flag would make the exported SDL environment-dependent and break
`tasks/schema.py::validate_graphqlschema`; that constraint is why the SDL lands unconditionally.

A fabricated-history reader was scoped and dropped after sizing the real read against the existing
git file read, which is its template: 27 lines of message class, 36 lines of handler, four one-line
registrations plus one command-map entry, and five git calls of which four already exist in the git
module minus their fetches. A deterministic sample reader costs about the same, and additionally a
determinism test, a configuration setting, a generated public configuration-reference entry, a
compose mapping and its own later removal, all discarded. The two UI states that cannot be produced
against a live repository on demand, rewritten and not-cloned, belong in Vitest fixtures rather than
in a server-side generator.

**Alternatives considered**: a deterministic sample reader behind an experimental flag (rejected
above: comparable cost, entirely throwaway, and `experimental_features` entries are surfaced through
`GET /api/config` and documented in the public configuration reference for a setting that would not
outlive the next phase); ship fabricated data unconditionally and remove it in Phase B (rejected: a
release cut between the two would present fabricated commits as real); keep Phase A on the feature
branch only (rejected: it blocks independent review of the contract and forces the frontend pull
request to target a branch). If a server-side stand-in is still wanted before the handlers land, it
returns literal placeholder strings with no determinism logic, no test and no documentation entry,
which costs a few lines and reads as obviously fake.

## Transport for the live read

**Decision**: Message-bus RPC, point-to-point, following `infrahub.api.file::get_file` and
`infrahub.message_bus.messages.git_file_get::GitFileGet`. Two new message pairs:
`GitCommitLogGet` / `GitCommitLogGetResponse` (routing key `git.commit_log.get`) and
`GitBranchHeadsGet` / `GitBranchHeadsGetResponse` (routing key `git.branch_heads.get`), both with
priority 4 in `infrahub.message_bus.messages::PRIORITY_MAP` like `git.file.get`.

**Rationale**: `dev/knowledge/backend/message-bus.md` reserves the bus for broadcasts and "rapid
RPC: git file retrieval, connectivity checks". A commit page is the same class of read: request-time,
sub-second, plain data, from a worker's local clone. The Prefect alternative
(`infrahub.services.adapters.workflow.worker::WorkflowWorkerExecution.execute_workflow`, used by
`infrahub.git.tasks::git_repository_diff_names_only`) calls `run_deployment` with `poll_interval=1`
and creates a flow run per page, which cannot meet SC-004 (first page under 2 seconds) for a paging
UI and pollutes the task list. The routing key lands in the shared `{namespace}.rpcs` queue through
`InfrahubMessageBus.worker_bindings` (`git.*.*`), so any warm worker answers.

**Alternatives considered**: `execute_workflow` with `persist_result=True` (rejected above); reading
git from the API server (rejected: the API server has no clone and must never acquire one).

## Bounded wait and the timeout error

**Decision**: Add a `timeout` parameter to `InfrahubMessageBus.rpc` (abstract in
`infrahub.services.adapters.message_bus::InfrahubMessageBus`, implemented in `rabbitmq.py`,
`nats.py`, `local.py`), wrapping the reply future in `asyncio.timeout`. The default comes from a new
`config::BrokerSettings.rpc_timeout` (seconds, default 30, env `INFRAHUB_BROKER_RPC_TIMEOUT`).
On expiry the adapter raises `infrahub.exceptions::WorkerTimeoutError` (HTTP 504), catalogued as
`WORKER_TIMEOUT` with payload `WorkerTimeoutData(operation, timeout_seconds, retry_after_seconds)`.
This lands as its own pull request before the read path, because it changes behaviour for every
existing `rpc` caller (`get_file`, `ValidateRepositoryConnectivity`).

**Rationale**: Today `RabbitMQMessageBus.rpc` and `NATSMessageBus.rpc` `await future` with no bound;
no `asyncio.wait_for` or `asyncio.timeout` wraps any RPC in the backend. FR-012 requires a bounded
wait with a catalogued error carrying a retry hint. The error catalogue
(`infrahub.errors.catalogue::CATALOGUE`) has no retry field in any payload today; retryability is
prose in `MERGE_IN_PROGRESS`. The three-key `extensions` shape produced by
`infrahub.graphql.error_formatter::build_catalogue_extensions` is fixed, so the hint goes inside
`data`. The retry hint is a fixed value equal to the timeout for now; the adaptive `Retry-After`
policy in `infrahub.api.admission.retry_policy` is about load shedding and is not reused.

**Alternatives considered**: per-call timeout only, default unbounded (rejected: a hang is never the
desired behaviour and the spec's governance table already anticipates the shared-path change);
message `Meta.expiration` (rejected: it bounds delivery, not the caller's wait).

**Observation, out of scope**: `infrahub.api.file::get_file` never calls
`InfrahubResponse.raise_for_status()`, so an `RPCErrorResponse` deserialises into an empty
`GitFileGetResponse` and the endpoint returns HTTP 200 with an empty body. Worth a separate issue.

## Warm-up when the answering worker has no clone

**Decision**: The `git.commit_log.get` and `git.branch_heads.get` handlers must not call
`infrahub.git.repository::get_initialized_repo`. They build the repository object without `init`
and call `InfrahubRepositoryBase.validate_local_directories()`; on
`RepositoryInvalidFileSystemError` they reply `condition = UNAVAILABLE`,
`unavailable.reason = NOT_CLONED`, and trigger a warm-up: `service.cache.set(key=f"git:warmup:{repository_id}", value=WORKER_IDENTITY, expires=60, not_exists=True)`
and, only when that set succeeded, `submit_workflow(GIT_REPOSITORY_WARM_UP)`. The new flow
`infrahub.git.tasks::warm_up_git_repository` runs `get_initialized_repo` under
`lock.registry.get(name=<repository_name>, namespace="repository")` and then broadcasts
`RefreshGitFetch` pinned to the imported commit so every other worker converges too.

**Rationale**: `InfrahubRepositoryIntegrator.init` clones inline, outside the repository lock, on
first sight of a missing directory. That is precisely the synchronous clone FR-013 forbids inside a
read. The cache `not_exists` flag (`infrahub.services.adapters.cache::InfrahubCache.set`) is the
existing distributed set-if-absent and collapses concurrent triggers across workers with no new
primitive. `RefreshGitFetch` handled by `infrahub.message_bus.operations.git.repository::fetch`
already clones-if-missing, fetches, and resets with `update_commit_value=False`; it is the
established convergence broadcast and needs no change. For read-write repositories the every-minute
`GIT_REPOSITORIES_SYNC` already broadcasts unconditionally, so a cold worker also warms within a
minute without our help; read-only repositories rely on the new flow.

**Alternatives considered**: Prefect `concurrency_limit=1` + `CANCEL_NEW` on the warm-up deployment
(rejected: it is per deployment, not per repository, so one repository's warm-up would cancel
another's); holding the repository lock in the handler and cloning (rejected by FR-013).

## Imported commit, remote head, ancestry, per-commit state

**Decision**: The API resolver reads Infrahub's side from the graph on the request branch:
`commit.value` and, per kind, `default_branch.value` (mapped to the remote branch through
`InfrahubRepositoryBase._get_mapped_remote_branch`) or `ref.value`. It sends
`imported_commit` and `git_ref` to the worker. The worker computes everything else on the main
clone (`get_git_repo_main()`), read-only and with no fetch:

- head: `origin/<branch>` for read-write; `origin/<ref>` then `<ref>` for read-only (the same
  fallback order as `InfrahubReadOnlyRepository.update_latest_commit`, without its fetch).
- relationship: `Repo.is_ancestor(imported, head)`; `False` means `REWRITTEN`.
- pending count: `git rev-list --count <imported>..<head>`, only when `BEHIND` and selected.
- page: `Repo.iter_commits(head, max_count=limit, skip=offset)`. No total: FR-024 drops it from the
  contract, so no counting pass over the whole history exists in the read path at all.
- per-commit state: `HEAD` if hash equals head, else `IMPORTED` if hash equals imported, else
  `PENDING` when the commit is not an ancestor of imported (`Repo.is_ancestor(commit, imported)` is
  false) and the condition is `BEHIND`, else `HISTORY`; under `REWRITTEN` every non-head commit is
  `UNRELATED`. When head equals imported, that commit is `IMPORTED` and the top-level `condition`
  is `IN_SYNC`; the two hashes at the top level let the UI draw both markers.

Classification is a pure function over frozen dataclasses in `infrahub.git.commit_log` (new module),
unit-tested without a repository.

**Rationale**: No commit listing or ancestry code exists in `backend/infrahub/` today
(`iter_commits` appears only in one integration test). GitPython 3.1.61 provides `is_ancestor`,
`merge_base` and `iter_commits`; per-page ancestry is at most `limit` cheap `merge-base` calls,
which stays constant as history grows. Non-linear history is why state is computed rather than
inferred from list position (FR-005).

**Alternatives considered**: materialising `rev-list imported..head` as a set for membership
(rejected: unbounded for a long-neglected repository); `git log --format` parsing (rejected: GitPython
already exposes typed commits).

## Freshness

**Decision**: Two values, from two different places.

`fetched_at` is the modification time of `<root>/main/.git/FETCH_HEAD` on the answering worker,
measured in the handler and returned in the RPC reply. Null when the file does not exist (a clone
that never fetched).

`checked_at` is read by the API resolver from the cache key `git:refs_check:last:<repository_id>`,
written at the end of every refs check. Read-only repositories only; null for read-write, where the
every-minute sync fetches and `fetched_at` already means what a reader would take it to mean.

The worker identity is deliberately **not** in the response. Support correlation is served by logging
it on the API server against the request id, which keeps an internal detail out of a payload every
repository viewer can read (Principle VI).

**Rationale**: Nothing records a fetch time today: no attribute, no cache entry, no FETCH_HEAD read.
Adding an attribute would be a schema change the spec rules out and would be per repository rather
than per worker, hiding exactly the divergence the freshness statement is meant to expose.

A refs listing writes nothing to the filesystem, so `FETCH_HEAD` does not move when a check confirms
the remote has not moved. Reporting only `fetched_at` would therefore tell an operator that a quiet
read-only repository was last seen weeks ago, moments after a successful check, which is precisely
the doubt this feature exists to remove. That is why the check time is a separate value rather than
folded into the same field, and why it is resolved from the cache rather than from the worker: no
file on the worker records it.

The last-checked key is distinct from the due key (`git:refs_check:due:<id>`), whose absence means "due
now" rather than "never checked" and whose lifetime is one interval. Conflating them would make
`checked_at` null exactly when a check is overdue, which is when its value matters most.

**Alternatives considered**: a cache key written after every fetch, replacing the FETCH_HEAD read
(rejected: it would need every existing fetch site to write it; FETCH_HEAD is maintained by git
itself); stamping a file during the refs check so the worker could report both (rejected: it would
make a read-only inspection write to disk, and the value is per repository rather than per worker);
reusing the due key for `checked_at` (rejected above).

## Per-branch drift in one worker request

**Decision**: `InfrahubRepositoryBranchDrift(repository_id)` resolves the tracked values per Infrahub
branch with a new `RepositoryBranchValuesQuery` (`infrahub.core.query.repository`) in one database
query, then sends a single `GitBranchHeadsGet` carrying `[{branch_name, git_ref, tracked_commit}]`.
The row set is decided entirely on the API side, so `sync_with_git` does not travel. The worker
answers from `InfrahubRepositoryBase.get_branches_from_remote()` (the
local mirror of `origin/*`, no fetch) and tag refs, and classifies each row: `NOT_TRACKED` when there
is no tracked commit, `NO_REMOTE` when the ref has no remote counterpart, else `IN_SYNC` / `BEHIND` /
`REWRITTEN` by the same rule as above, without a pending count. The row set is branches synchronised
with Git for the read-write kind and every branch for the read-only kind, excluding merged and
deleting branches and the global branch, so the column lines up with the sibling card's rows.

**Rationale**: FR-004 and SC-005 demand one worker request regardless of branch count, and the
constitution's Principle V forbids N+1 patterns on the graph side.
`infrahub.git.utils::get_repositories_commit_per_branch` cannot serve the resolver: it loops
`registry.branch.values()` and issues one `NodeManager.query` per branch for the whole repository
kind with no filter, so a page load would cost one query per branch, each returning every repository.
Its own docstring records the intent to become a single query.

Nothing in the codebase resolves an attribute value for one node across many branches today.
`Branch.get_query_filter_path` targets exactly one branch, emitting at most two `(branch IN [...],
time)` pairs: the origin branch at `branched_from` and the target branch at `at`. Two precedents
supply the shape. `infrahub.core.diff.query.artifact::ArtifactDiffQuery` reads attribute values on
two branches in one statement, proving multi-branch value resolution works;
`infrahub.core.query.diff::DiffCountChanges` returns one row per branch from a `branch_names` list
parameter with a Python-side backfill for branches that produced no rows. The new query generalises
the first to N branches using the second's return shape: `UNWIND` a per-branch scope of
`{target, branches, time_base, time_tip}` derived from each branch's `branched_from` and
`is_isolated`, then a `CALL` subquery per scope with the standard
`ORDER BY branch_level DESC, from DESC, status ASC LIMIT 1` and the active-status check.

Two storage facts constrain it, both verified in the tree. Repository kinds are node-level `AGNOSTIC`
(`core/schema/definitions/core/repository.py`), so the node is visible from every branch and the row
set must be driven from the branch list rather than from the node's own edges. And `commit` is
`LOCAL` on a branch-agnostic node, which sends its creation edge to the global branch
(`core/attribute.py::InfrahubAttribute.get_create_data`) while later writes land on the real branch;
a branch that never imported therefore resolves through `branch_level` ordering to the default
branch's fork-point value. That inheritance is the value the branch genuinely runs, and the new query
must reproduce it rather than return null. It is pinned by tests (own value, inherited value, after a
later default-branch import, after a rebase) before the resolver depends on it.

Read-only repositories may pin a different `ref` per branch (branch-aware attribute), so the ref
travels per row and is read by the same query.

**Boundary with IFC-3104**: that PRD owns the paginated, filterable `InfrahubRepositoryBranchStatus`
query, its server-side filters and count, and the periodic-sync refactor onto the same primitive. The
query built here is deliberately the single-repository case, which is all this feature needs; widening
it to many repositories for the sync job is that epic's own reviewed change, since the helper feeds
the once-a-minute sync. This feature does not touch `get_repositories_commit_per_branch`.

**Alternatives considered**: reusing `get_repositories_commit_per_branch` as-is (rejected above:
N+1 on a page load, and it returns every repository per branch); adding a repository filter to that
helper and keeping the per-branch loop (rejected: it fixes the result volume but not the query count,
so SC-005 still fails); nesting drift under `InfrahubBranch` (rejected: one worker call per row);
storing a per-branch remote head (ruled out by the spec); building the many-repository primitive here
(rejected: it puts the once-a-minute sync's read path in this feature's blast radius for no benefit
to this slice).

## Read-only refs check: scheduling, interval, on demand

**Decision**: One cron workflow `GIT_READ_ONLY_REPOSITORIES_CHECK_REFS` (`cron="* * * * *"`,
`concurrency_limit=1`, `ConcurrencyLimitStrategy.CANCEL_NEW`, exactly like `GIT_REPOSITORIES_SYNC`)
iterating read-only repositories from `get_repositories_commit_per_branch(kind=READONLYREPOSITORY)`.
For each repository it performs `service.cache.set(key=<due key for the repository>, value=...,
expires=<interval seconds>, not_exists=True)`; a failed set means the repository is not yet due and
is skipped. The interval is `config::GitSettings.read_only_refs_check_interval_mins` (default 15,
`ge=1`, env `INFRAHUB_GIT_READ_ONLY_REFS_CHECK_INTERVAL_MINS`). A second workflow
`GIT_READ_ONLY_REPOSITORY_CHECK_REFS` runs the per-repository body for one repository, bypassing the
due check, and is what the new mutation `InfrahubReadOnlyRepositoryCheckRefs` submits. Both paths
delegate to one shared body, so the scheduled and on-demand routes cannot drift apart.

Per-repository body, in `infrahub.git.tasks::check_read_only_repository_refs`, ordered so that the
network call holds no lock:

1. Claim the repository with `cache.set(key=<running key>, value=<this flow's run id>,
   not_exists=True)`; a failed claim means a check for this repository is already in flight, so the
   body returns the recorded run id and performs no remote work (FR-025). Released in a `finally`.
2. Resolve the tracked refs and read the local `origin/<ref>` or tag SHA. No lock: this reads git's
   own consistent object store.
3. `git ls-remote origin <ref>` on the main clone, **outside** the repository lock (credentials come
   from the worker's global git config exactly as for `fetch`; the ref is validated with
   `git check-ref-format --allow-onelevel` first, and the subprocess carries git's low-speed abort
   settings). If unchanged, stop: a refs listing and nothing more (FR-018).
4. Only if the ref moved, take `lock.registry.get(name=<repository_name>, namespace="repository")`
   around `InfrahubRepositoryBase.fetch()` (already `--prune --tags --prune-tags`) and the
   `RefreshGitFetch` broadcast, pinned to the tracked commit for each Infrahub branch that pins this
   ref, so every worker's copy converges while `update_commit_value=False` guarantees the pin does not
   move (FR-016, FR-017).

Failure of any step is caught per repository, recorded with the repository and the reason, and the
`git:refs_check:due:<id>` due key is deleted so the next tick retries rather than treating the repository
as checked (FR-026). The cycle continues with the other repositories and does not fail the flow run.

Holding the repository lock across `ls-remote`, as an earlier draft of this plan did, would let an
unreachable or hanging remote block that repository's imports and the fetch broadcast handler for as
long as git waits. Git applies no network timeout by default, so the exposure is unbounded. The
listing changes nothing locally, which is what makes moving it outside the lock safe.

The cron flow runs each due repository's body as a Prefect `@task` under its own flow run, with
bounded concurrency and a per-repository timeout, rather than awaiting them in sequence. Sequential
execution would let one slow remote consume the tick and delay every other repository, and a tick
running longer than a minute is cancelled by `CANCEL_NEW`, which would make the effective interval
drift. Submitting a separate user-visible flow run per repository per tick was the other option and
was rejected: it would fill the task list with routine background work. Running them as tasks keeps
the work nested under the tick. The burst is bounded by the due check, which already spreads
repositories across ticks: at the default interval roughly a fifteenth of read-only repositories come
due on any given tick.

Each tick records checked, moved, failed and duration; each movement records the repository, the ref
and both commits (FR-027).

**Rationale**: `WorkflowDefinition.cron` is the only scheduling mechanism (`infrahub.trigger.*` is
event-based, with no interval trigger type), schedules are created at startup by
`infrahub.workflows.initialization::setup_deployments`, and `config.SETTINGS` cannot be read at
`catalogue.py` import time (`ConfiguredSettings` raises `InitializationError` before
`load_and_exit`). A fixed frequent cron plus a runtime "is it due" check is exactly how
`CacheSettings.clean_up_deadlocks_interval_mins` is consumed, and it makes an interval change take
effect at the next tick with no deployment rewrite (User Story 2, scenario 6). The cache key with
`not_exists` gives a distributed due check for free. Locking on the repository name serialises the
steps that modify the local copy with imports and the fetch broadcast handler (FR-019).

The interval keeps the `ge=1` constraint of its analogue; there is no disabling value. An earlier
draft added one on the reasoning that an operator would otherwise be unable to stop the job, and that
was rejected on review as configurability for a hypothetical requirement (Principle VII). The
codebase is consistent on this point: of the five cron workflows in `workflows.catalogue`, only
`ANONYMOUS_TELEMETRY_SEND` can be turned off, through `main.telemetry_optout`, which is a privacy
opt-out rather than an operational kill switch. `GIT_REPOSITORIES_SYNC`, `CLEAN_UP_DEADLOCKS`,
`WEBHOOK_CONFIGURE` and `MERGE_WATCHER` have no equivalent, and
`clean_up_deadlocks_interval_mins` is itself `ge=1`. An idle repository costs one refs listing per
interval with no content transfer, strictly less than the every-minute sync already spends on each
read-write repository, so the load an off switch would relieve is smaller than load the product
already accepts without one. Lengthening the interval remains available for a check judged too
frequent.

`CANCEL_NEW` remains on the cron definition and bounds whole ticks; per-repository non-accumulation is
the in-flight cache key, because `CANCEL_NEW` is per deployment and would otherwise let one
repository's on-demand run cancel another's.

**Warning to carry into implementation**: `InfrahubReadOnlyRepository.get_commit_value` fetches on
every call and `update_latest_commit` writes the commit even when nothing synced. Neither may be used
by the check.

**Alternatives considered**: computing the cron from config inside `WorkflowDefinition.to_deployment`
(rejected: needs a restart to change and an interval-to-cron translation); a Prefect interval
schedule (rejected: same restart constraint and a new schedule type in `to_deployment`); a disabling
value or a separate boolean to switch the check off (rejected above: no comparable background job has
one, and the load is smaller than jobs that do not); relying on Prefect concurrency limits for
per-repository non-accumulation (rejected: the limit is per deployment, so one repository's run would
cancel another's, the same reason the warm-up flow does not use it); leaving the due key in place on
failure (rejected: a repository whose remote was briefly unreachable would then wait out a full
interval before anyone looked again).

## Tag moves and garbage collection (spec assumption to validate)

**Decision**: The assumption holds and FR-020 is testable. Findings: `create_commit_worktree` makes a
detached worktree at `commits/<sha>`, whose `HEAD` is a reachability root for `git gc`; no code in
`backend/infrahub/` runs `git gc` or `git worktree prune`, and
`InfrahubWorkerAsync.set_git_global_config` does not touch `gc.auto`, so only git's opportunistic
auto-gc runs during fetch, and it respects worktree roots. Today's fetch flags
(`prune=True, tags=True, prune_tags=True`) already force-update tags, so the check adds no new
object-deletion risk. Residual risks to pin with an integration test against a fixture remote whose
tag is moved: the old commit stays readable through its worktree on every worker, and a deleted
upstream tag makes the check report `NO_REMOTE` rather than raise
(`update_latest_commit` raises `ValueError("Ref ... not found")` in that case and must not be
reused).

## Permission model

**Decision**: Both queries load the repository with
`NodeManager.get_one_by_id_or_default_filter(kind=InfrahubKind.GENERICREPOSITORY, ...)` and call
`graphql_context.active_permissions.raise_for_permission(define_object_permission_from_branch(schema=<concrete kind>, action=PermissionAction.VIEW, branch_name=...))`.
The mutation requires `PermissionAction.UPDATE` on the concrete kind, mirroring
`infrahub.graphql.mutations.repository::ReadOnlyRepositoryImportLastCommit`.

**Rationale**: `infrahub.graphql.analyzer::InfrahubGraphQLQueryAnalyzer._get_operations` maps
top-level fields to schema kinds by exact name, so a custom query is invisible to
`ObjectPermissionChecker` and would be authorised for everyone. The imperative check with
`define_object_permission_from_branch` computes the same `ALLOW_DEFAULT` / `ALLOW_OTHER` decision
the checker would, which is what FR-009 means by "the same rule". The mutation is not added to
`QUERIES_REQUIRING_AUTHENTICATION`; anonymous sessions are already denied every mutation.

## GraphQL surface and naming

**Decision**: Top-level queries `InfrahubRepositoryCommits` and `InfrahubRepositoryBranchDrift`,
mutation `InfrahubReadOnlyRepositoryCheckRefs`, all registered on
`infrahub.graphql.schema::InfrahubBaseQuery` / `InfrahubBaseMutation`. Types in
`infrahub.graphql.types.repository` (new), enums wrapped with `graphene.Enum.from_enum` from
`InfrahubStringEnum` classes in `infrahub.core.constants`
(`RepositoryGitCondition`, `RepositoryCommitState`, `RepositoryGitUnavailableReason`). Pagination
is flat `limit` / `offset` with `edges { node }` and an optional `count`, matching
`infrahub.graphql.queries.task::Tasks`. Expensive fields are gated on selection with
`infrahub.graphql.field_extractor::extract_graphql_fields`, the way `queries.task::_build_fetch_options`
does. Descriptions are single-line (the SDL printer warning in `infrahub.graphql.types.preferences`).

**Rationale**: There is no per-kind object type override table; the one precedent for injecting a
custom field onto a generated type (`is_externally_managed` in
`GraphQLSchemaManager.generate_query_mixin`) edits the hashed, benchmarked schema-generation path and
still buys no permission derivation. Every comparable read in this domain is top-level
(`InfrahubTask`, `DiffTree`, `CoreProposedChangeAvailableActions`). `snake_case` wire names follow
from `auto_camelcase=False`.

## Frontend hand-off

**Decision**: The Phase A PR regenerates `schema/schema.graphql`,
`frontend/app/src/shared/api/graphql/generated/{graphql-env.d.ts,graphql-cache.d.ts,types.ts}`,
`schema/error-catalogue.json`, `frontend/app/src/shared/api/errors/catalogue.generated.ts`,
`docs/docs/reference/error-catalogue.mdx` and `docs/docs/reference/configuration.mdx`. The UI lands
as a `Commits` tab on the generic object detail page
(`frontend/app/src/entities/nodes/object/ui/object-details/object-details-tabs.tsx`, gated with
`isOfKind(GENERIC_REPOSITORY_KIND, ...)` like the existing `repository_objects` tab), backed by the
three-file query chain under `frontend/app/src/entities/repository/`, polling with
`refetchInterval` while `condition === "UNAVAILABLE"` (pattern:
`entities/branches/ui/queries/get-branch-action-state.query.ts`). The drift column has no rows to
annotate yet: IFC-3104 has not landed and no per-repository branch list exists in the frontend, so
User Story 3's UI waits for that card while its query ships now.

## Configuration additions

| Setting | Default | Env var | Consumer |
| --- | --- | --- | --- |
| `BrokerSettings.rpc_timeout` | 30 s | `INFRAHUB_BROKER_RPC_TIMEOUT` | every `InfrahubMessageBus.rpc` call |
| `GitSettings.read_only_refs_check_interval_mins` | 15 | `INFRAHUB_GIT_READ_ONLY_REFS_CHECK_INTERVAL_MINS` | `check_read_only_repositories_refs` due check |

Each requires `uv run invoke docs.generate` (configuration reference),
`uv run invoke release.validate-dockercomposeenv` (root compose env block) and a hand-added mapping
in `development/docker-compose.yml`.

## Convergence and the message-bus driver

Convergence assumes the worker fetch broadcast reaches every worker, which is what the RabbitMQ
adapter provides: each git worker declares an exclusive `worker-events-{WORKER_IDENTITY}` queue bound
to the broadcast routing keys. That is the supported deployment and the one this feature targets.

An unrelated gap in the alternative NATS adapter was noticed while verifying this and filed as
[opsmill/infrahub#10514](https://github.com/opsmill/infrahub/issues/10514). That driver is not in use
and is not currently supported, so it places no requirement on this feature: no caveat in the user
documentation, no constraint on the design, and nothing to fix here.
