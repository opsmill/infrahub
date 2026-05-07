# Phase 0 — Research

This document records design decisions, alternatives considered, and factual corrections to the source material that informed the plan.

## Section A — Factual Snapshot of Today's Coordination

These findings come from a code survey at `branch-merge-locking-ifc-2562@HEAD` (2026-05-07). They are the ground truth that the plan is built on; they correct two assumptions that floated into earlier discussion.

### A.1 `global_graph_lock()` at `backend/infrahub/lock.py:341`

**Finding**: `global_graph_lock()` returns an `InfrahubMultiLock` over three lock names: `LOCAL_SCHEMA_LOCK`, `GLOBAL_SCHEMA_LOCK`, `GLOBAL_GRAPH_LOCK`. None of those names contain a branch identifier — they are branch-agnostic by name. Therefore, while a merge holds `global_graph_lock()` (acquired at `backend/infrahub/core/branch/tasks.py:390`), any subsequent call to acquire any of the three names from any caller (any branch, any process) will block.

**Corrects**: An author-provided observation suggested that today's system already permits unrelated-branch writes during a merge. That is not what the lock-name structure implies. There may be a behavioral reason this isn't the user-visible experience (merges may complete fast enough that contention is rare, or callers may not actually exercise these paths), but the lock as written is global.

**Decision**: The spec's clarification stands as authorial intent. This work treats unrelated-branch behavior as a non-regression invariant — we do not change the behavior of `global_graph_lock` and we do not promise an improvement in unrelated-branch productivity as a deliverable. Cleanup of the legacy lock is explicitly punted to a follow-up after the new coordination is proven in production.

**Implication for the plan**: Keep `global_graph_lock()` and `MergeLocker.acquire_global_lock()` in place around `_do_merge_branch`. The new `BranchLocker` layers underneath both. SC-001 ("no regression on unrelated branches") is trivially satisfied because we do not remove the lock that produces today's behavior.

### A.2 `BranchStatus.MERGING` is checked by middleware

**Finding**: `backend/infrahub/graphql/middleware.py:7` defines `raise_on_mutation_for_branch_status` and applies it as a GraphQL middleware to all mutations. Line 14 calls `BranchStatusChecker.check_merge_status(branch=info.context.branch)` for every mutation except a small allowlist (`BranchDelete`). Therefore, when `branchA` is in `MERGING` status, *all* GraphQL mutations against `branchA` already raise — not just `BranchRebase` / `BranchMerge`.

**Corrects**: The source plan text claimed "only `BranchRebase` and `BranchMerge` mutations check that status; regular node/relationship/schema mutations do not." That is wrong as stated. What is true: those *specific mutation classes* contain explicit per-class status checks (`branch.py:240, 339`, `proposed_change.py:112`), but the middleware is the actual blanket protection.

**Implication for the plan**: The new `BranchLocker.acquire_write` is not redundant — it covers cases the middleware doesn't:
1. **Target-branch writes** (e.g., `main` while `branchA → main` is merging). The target branch is *not* in `MERGING` status during a merge — only the source branch is. The middleware therefore lets `main` writes through; `global_graph_lock` is what currently stops them, and that's exactly the sledgehammer we want to replace.
2. **Async-task writes that originate from before the merge but commit after**. A workflow's GraphQL/REST origin call returned and the branch transitioned to `MERGING` after; the workflow's eventual write goes through `acquire_write` (which catches `merge_intent`), not through middleware (the workflow does not redo the GraphQL mutation).
3. **Writes via REST and direct workflow paths** that bypass GraphQL middleware entirely (`api/schema.py POST /load`, `api/artifact.py POST /generate`, all writer Prefect flows).
4. **In-flight writers at merge start**. The middleware fires synchronously per request; it does not provide a "drain" semantics. `acquire_merge` does.

So the new locker complements `MERGING`, not replaces it. We keep both.

### A.3 NATS cache adapter has bucket-level TTL only

**Finding**: `backend/infrahub/services/adapters/cache/nats.py:34` carries a `FIXME: remove once NATS supports TTL for keys`. Implementation uses one KV bucket per pre-registered TTL value: `ONE`, `TEN`, `FIFTEEN`, `ONE_MINUTE`, `TWO_HOURS` (registered at `backend/infrahub/message_bus/types.py:31-35`). A `set(key, value, expires=KVTTL.X)` call routes to bucket `X`, and the bucket's fixed TTL governs eviction. Re-writing a key (`set` again, or `kv.put`) effectively resets the TTL because the KV stores the latest message in the bucket.

Redis has straightforward per-key `EX` and atomic `NX` set-if-absent.

**Decision**: Add two new bucket TTLs to NATS — `TWO_MINUTES` and `FIVE_MINUTES` — corresponding to the writer-key TTL and merge-intent TTL respectively. This keeps the existing pattern intact and avoids a deeper change to the NATS adapter (which carries its own FIXME for the underlying limitation).

**Alternatives considered**:
- **Reuse `TWO_HOURS` for writer keys**: Strands a crashed writer's claim for two hours, blocking merges that drain on it. Rejected — defeats SC-004.
- **Reuse `ONE_MINUTE`**: A 30-second heartbeat with a 60-second TTL leaves zero margin for a slow heartbeat or a network blip; a 30-second heartbeat with a 120-second TTL is comfortable. Rejected for being too tight.
- **Use sub-second TTL by triggering eviction manually**: Reintroduces the very bug TTLs prevent — if the eviction caller dies, the key is stuck. Rejected.
- **Wait for upstream NATS per-key TTL**: Out of scope; the FIXME is unowned. Rejected as a blocker.

**Defaults selected** (configurable via `config.merge.*`):
- Writer key TTL: 120s, heartbeat every 30s
- Merge intent TTL: 300s, heartbeat every 60s
- Drain timeout: 30s

### A.4 `InfrahubLock` and ContextVar conventions

**Finding**: `backend/infrahub/lock.py:142` already uses one `ContextVar` per `InfrahubLock` instance for recursion-depth tracking, with token reset on exit. Another existing pattern is at `backend/infrahub/core/creation_context.py:10-46`, where a single module-level `ContextVar[NodeCreationContext | None]` is set/reset via `__enter__`/`__exit__`.

**Decision**: Follow the creation-context pattern for `MergeHolder` — a module-level `ContextVar[MergeHolder | None]` set by `acquire_merge` on entry and reset on exit, never read in user code, only consumed by `acquire_write`. This keeps the surface area minimal and matches the established convention.

## Section B — Coordination Mechanism Decisions

### B.1 Why a "gate" mutex plus separate state keys, not a single mutex per branch

**Decision**: Use `branch.{name}.gate` (an `InfrahubLock` mutex) as a brief critical section for the atomic check-and-claim. State (`merge_intent`, per-writer keys) lives in the cache adapter, not under the gate's lock.

**Rationale**: Holding the gate during the entire write or the entire merge would re-create the very sledgehammer we are removing — every write would serialize on the gate. The gate is held only long enough to atomically read intent and register a writer (or set intent and enumerate writers). The actual write or merge proceeds without the gate.

**Alternatives considered**:
- **Cache-only with CAS**: Atomic compare-and-swap loops are workable on Redis (`SET NX`) but the multi-key invariant ("intent is set AND no writers exist") cannot be CAS'd as a single op. Rejected.
- **Per-branch shared/exclusive lock primitive**: `InfrahubLock` is mutex-only and supporting shared/exclusive across Redis + NATS would require non-trivial new code. Rejected — out of scope.
- **Hold the gate for the duration of the operation**: Defeats purpose (see above). Rejected.

### B.2 Per-writer keys vs. a writer counter

**Decision**: Each writer creates `branch.{name}.writers.{writer_id}` with its own TTL and a heartbeat task that renews it.

**Rationale**: A counter (`INCR`/`DECR`) cannot survive a writer crash — a crashed writer's increment is never decremented and the merge waits forever or until a manual reset. Per-writer keys with TTLs let crashed writers be forgotten automatically.

**Alternatives considered**:
- **Set member with single TTL on the set**: Redis `SADD` with `EXPIRE` on the set evicts ALL members at once, not individuals. NATS KV has no set primitive. Rejected.
- **Counter + crash-recovery cron**: Adds an out-of-band recovery component for a problem that TTLs solve elegantly. Rejected per Constitution VII.

### B.3 In-flight writes: drain-with-timeout (not kill, not queue)

**Decision**: `acquire_merge` sets `merge_intent` first (no new writers can register), then polls writer keys until empty or timeout (configurable, default 30s). On timeout, the merge fails cleanly and `merge_intent` is cleared.

**Rationale**: Recorded as a pre-spec clarification — drain semantics chosen over kill; reject-not-queue chosen over queue-and-replay. Documented in spec Assumptions.

### B.4 Merge's own writes: ContextVar + Prefect parameter

**Decision**: `acquire_merge` sets a module-level `ContextVar[MergeHolder | None]`. `acquire_write` checks the ContextVar and the cache-stored `merge_intent` value: if either matches the holder id for the branch under inspection, the write bypasses the merge_intent check and proceeds without registering a writer key.

For Prefect sub-flows submitted from `_do_merge_branch`, the merge passes its `holder_id` as a flow parameter (new `merge_holder_id: str | None = None` field on the flow's parameter model). The flow's `acquire_write` call receives the parameter and presents it to the locker.

**Rationale**: ContextVars do not propagate across processes — Prefect sub-flows run in a different worker and would otherwise deadlock on the merge's own claim. An in-process-only mechanism is a latent deadlock; a parameter-only mechanism widens the blast radius across every internal call site. Both together are minimal: in-process callers need no changes, cross-process callers carry one parameter.

**Alternatives considered**:
- **Skip the bypass; let the merge release the claim around its sub-flows**: Releases mid-merge, defeats coordination. Rejected.
- **Use Prefect contexts (e.g., `prefect.context`)**: Specific to Prefect, not portable to non-flow callers, and Prefect contexts also do not cross worker boundaries automatically without explicit parameter passing. No win over our explicit parameter. Rejected.

### B.5 Crash recovery: TTL with heartbeat, not lease renewal protocol

**Decision**: Both `merge_intent` and writer keys use a fixed cache TTL (configurable). A heartbeat task started inside `acquire_merge` / `acquire_write` rewrites the key (resets the TTL window) at half the TTL interval. On graceful exit, the heartbeat is cancelled and the key is deleted.

**Rationale**: Simplest mechanism that delivers SC-003 and SC-004. The cache backend already supports it (Redis natively; NATS via overwrite into a TTL'd bucket).

**Alternatives considered**:
- **Lease tokens that callers must explicitly renew via API**: Requires a renewal RPC and lease-id bookkeeping in callers — more code for callers, no gain over heartbeat. Rejected.
- **Process-supervisor signaling for cleanup**: External to the locker; doesn't help cross-process callers. Rejected.

## Section C — Scope Decisions

### C.1 Coverage: GraphQL chokepoint vs. per-mutation wrapping

**Decision**: Wrap `InfrahubMutationMixin.mutate()` once (covers the bulk of generated CRUD mutations and all mixin-extending classes — `InfrahubProfileMutation`, `InfrahubProposedChangeMutation`, `InfrahubRepositoryMutation`, `InfrahubIPNamespaceMutation`, `InfrahubIPAddressMutation`, `InfrahubIPPrefixMutation`, `InfrahubArtifactDefinitionMutation`, `InfrahubNumberPoolMutation`, `InfrahubWebhookMutation`, `InfrahubTriggerRuleMutation`, `InfrahubCoreMenuMutation`, `InfrahubGraphQLQueryMutation`). Then explicitly wrap the mutation classes that bypass the mixin: `RelationshipAdd`, `RelationshipRemove`, the four `SchemaDropdown*` / `SchemaEnum*` classes, `UpdateComputedAttribute`, `RecomputeComputedAttribute`, `ResolveDiffConflict`, `UpdateHFID`, `UpdateDisplayLabel`, `ProposedChangeReview`, `InfrahubProfilesRefresh`.

**Excluded from wrapping**: Branch operation mutations (`BranchCreate`, `BranchUpdate`, `BranchRebase`, `BranchMerge`, `BranchValidate`, `BranchDelete`, `ProposedChangeMerge`) per FR-009 — they are the operations that establish coordination, not subjects of it. Their existing `BranchStatus.MERGING` checks remain in place. Account/auth mutations are not branch-scoped and need no wrapping.

### C.2 Async writer flows requiring `acquire_write` + `merge_holder_id` parameter

The known writer flows (from `backend/infrahub/workflows/catalogue.py`) — each gets `acquire_write` at body entry and an optional `merge_holder_id` parameter on its model:

- `BRANCH_MIGRATE` (schema migration)
- `BRANCH_MERGE_POST_PROCESS` (submitted from inside `_do_merge_branch`)
- `BRANCH_MERGED` (post-merge consumer)
- `BRANCH_CANCEL_PROPOSED_CHANGES` (submitted from inside `_do_merge_branch`)
- `IPAM_RECONCILIATION` (submitted from inside `_do_merge_branch`)
- `REQUEST_GENERATOR_RUN`, `REQUEST_GENERATOR_DEFINITION_RUN`, `TRIGGER_GENERATOR_DEFINITION_RUN`
- `GIT_REPOSITORIES_SYNC`, `GIT_REPOSITORIES_CREATE_BRANCH`, `GIT_REPOSITORIES_DELETE_BRANCH`, `GIT_REPOSITORY_ADD`, `GIT_REPOSITORY_ADD_READ_ONLY`, `GIT_REPOSITORIES_MERGE`
- `PROFILE_REFRESH_MULTIPLE`, `PROFILE_REFRESH`
- `SCHEMA_APPLY_MIGRATION`
- `COMPUTED_ATTRIBUTE_PROCESS_JINJA2`, `COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM`, `DISPLAY_LABELS_PROCESS_JINJA2`
- `REQUEST_PROPOSED_CHANGE_PIPELINE`
- `DIFF_UPDATE`
- `BRANCH_DELETE` (submitted from inside `_do_merge_branch` only when `delete_branch_after_merge` is set — accepts `merge_holder_id` for the bypass)

**Excluded** (not branch-scoped writes or read-only):
- `BRANCH_CREATE`, `BRANCH_REBASE`, `BRANCH_VALIDATE`, `BRANCH_MERGE_MUTATION` — branch operations themselves (FR-009).
- Any read-only flows surfaced in `catalogue.py` that don't hit the mutation path.

The PR description for the workflow-wrapping PR (PR 6) carries this enumeration as a checklist with the writer/reader status of every entry in `catalogue.py`, so reviewers can verify nothing was missed.

### C.3 Single-merge serialization is preserved

Per FR-015 and the spec Assumption: `MergeLocker.acquire_global_lock()` continues to wrap the new locker. One merge runs at a time globally during this rollout. The architecture supports relaxing this, but doing so is a follow-up.

## Section D — Test Strategy Decisions

### D.1 Where each scenario tests

| Test level | Concerns | Files |
|---|---|---|
| Unit (`backend/tests/unit/core/branch/test_branch_locker.py`) | Locker behavior in isolation against a real cache backend (NATS or Redis fixture); race semantics; TTL/heartbeat; ContextVar-vs-holder-id matching | New file |
| Functional (`backend/tests/functional/merge/test_branch_locker_wraps.py`) | Each wrap site in isolation: a mutation rejected when intent is set; a merge that drains a single in-flight functional writer | New file |
| Integration_docker (`backend/tests/integration_docker/test_branch_merge_coordination.py`) | Cross-process scenarios: a merge in one worker, mutations and async tasks in another; crash recovery via TTL expiry; end-to-end merge with internal-write bypass on real Prefect | New file |

### D.2 Existing merge integration tests

All existing tests under `backend/tests/integration_docker/` covering merge, rebase, post-merge schema migration, and IPAM reconciliation continue to run unchanged. They serve as the regression bar for SC-007.

### D.3 Cache-backend coverage

Unit tests parametrize on cache backend (`local`, `redis`, `nats`) where the test infrastructure supports it, to catch backend-specific bugs (especially the NATS bucket-TTL pathway).

## Section E — Open Questions Deferred to Implementation

These are details that do not affect the spec or the high-level design and are settled in code review during the relevant PR:

- Exact log message format for `BranchLockedError` (kept terse per Constitution VI; format chosen during PR 1 review).
- Whether the heartbeat task uses `asyncio.create_task` directly or routes through an existing helper. (Followed whatever pattern `lock.py` uses.)
- Whether the writer-key naming includes a process/worker identifier alongside the per-call UUID. (Default: per-call UUID is sufficient; process id is not needed because TTL covers crashed-process cleanup.)

No NEEDS CLARIFICATION markers remain.
