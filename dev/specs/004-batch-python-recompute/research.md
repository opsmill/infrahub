# Research: Batch Python Computed-Attribute Recompute

## R1 — Persistence path for batched values

**Decision**: Reuse `build_bulk_recompute_dispatcher()` → `BulkRecomputeDispatcher.dispatch(writes, coalesced=False)` → `BulkRecomputeWriter.write` (chunked `Node.save`, 100/transaction).

**Rationale**: The writer already provides everything FR-002/003/004 demand: bounded transactions, `node_changelog.has_changes` gating (no event, no cascade for no-ops), per-changed-node NodeUpdated events with live origin so genuinely-changed values still chain dependent recomputes. `coalesced=False` keeps live-event semantics (origin=LIVE, no coalesced chain), matching today's behavior for real changes.

**Alternatives considered**:
- *Keep per-node `InfrahubUpdateComputedAttribute` mutations* — rejected: the mutation wrapper (parse/validate/permissions per node) and its per-node event emission are the echo storm's fuel.
- *New raw-Cypher UNWIND bulk writer* — rejected: would fork branch/time-versioned write semantics, HFID/display-label cascades, and changelog computation into a second implementation; high correctness risk; violates reuse constraint.

## R2 — Per-node read + transform execution within the batch

**Decision**: SDK `InfrahubBatch` (`client.create_batch(return_exceptions=True)`), one plain-async callable per node returning an `AttributeValueWrite`; results partitioned into writes vs skipped.

**Rationale**: Bounded concurrency (semaphore, default 5) caps transient memory; `return_exceptions=True` is the isolation primitive FR-005 needs — one node's raised exception arrives as a result item instead of aborting the gather. Keeping the read as `query_gql_query(..., update_group=True, subscribers=[id])` preserves the reverse-index registration (FR-007).

**Alternatives considered**:
- *Keep one Prefect `@task` per node* — rejected: task-run creation/retention per node is pure orchestrator overhead at fan-out scale and is what makes the storm's task volume explode.
- *`asyncio.gather` directly* — rejected: unbounded concurrency; SDK batch already provides the semaphore + node-tagged result stream.

## R3 — Repository initialization sharing

**Decision**: `get_initialized_repo(...)` once per attribute batch, pass the repo object into every per-node callable.

**Rationale**: FR-001. The checkout is keyed by repository+commit — identical for every node in the batch; per-node init was redundant work plus worktree lock contention.

**Alternatives considered**: per-node init with an internal cache — rejected: the cache would still pay per-node lookup/validation and keeps the contention pattern; hoisting is simpler.

## R4 — Failure semantics for bad transform results

**Decision**: Partition results: `Exception` → skip (log reason, keep prior value); non-`str` value → skip (log reason); only `str` values persist. Flow completes green with warnings.

**Rationale**: FR-005 and the old path's contract: the mutation's `$value: String!` made non-string values fail loudly per node without touching siblings — silently writing `None`/garbage through the bulk path would be a data-corruption regression. Skip-and-log preserves siblings' progress and the failing node's last good value.

**Alternatives considered**: fail the whole flow on first error — rejected: regresses partial progress; one broken node would starve thousands. Write None on failure — rejected: destroys last good value.

## R5 — Task-list visibility of batch runs (branch filter)

**Decision**: Pass `tags=[WorkflowTag.BRANCH.render(identifier=branch_name)]` at `submit_workflow` time for every `COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM` submission.

**Rationale**: FR-006. The task API filters flow runs by the branch tag. Tag updates made *inside* a flow are rebuilt from the tags known at run creation — a later in-flow tag update (e.g. the dispatcher marking a database change) replaces the tag list and drops anything added mid-run. Only tags present at creation reliably survive, so the branch tag must ride the submission. (Deployment-static tags — namespace, workflow type, database-change — already come from the workflow definition.)

**Alternatives considered**: merge against live tags read from the orchestrator API inside `add_tags` — rejected: adds one API read to every tagged flow in the system; at storm concurrency this measurably slows the task manager (verified: drains that finish in minutes stopped finishing inside 300–900s bounds).

## R6 — What deliberately does not change

- Per-node GraphQL reads and per-node transform executions remain O(N): values are per-node functions of per-node data; the transform is opaque user code.
- Fan-out scoping (all-of-kind on schema/backfill paths, reverse-index on data paths) untouched — out of scope per spec.
- `InfrahubUpdateComputedAttribute` remains a public mutation (external users); it just stops being used internally.
- Submission chunking (`get_submission_chunk_size()`, ≈250 ids/run) unchanged; multiple batches per oversized fan-out (FR-008) already handled by the existing `_chunk_ids` submit loops.
