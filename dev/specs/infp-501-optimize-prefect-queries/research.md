# Phase 0 Research: Optimize Automated Task Query Performance

**Feature**: infp-501-optimize-prefect-queries
**Date**: 2026-04-29
**Branch**: `optimize-prefect-queries-infp-501`

## Decision Log

### Decision 1: Query Execution Approach

**Decision**: Use the existing `infrahub_sdk.graphql.Query` builder combined with `client.execute_graphql()` for all custom queries.

**Rationale**: This pattern is already established in `hfid/models.py` (`HFIDGraphQL` class) and `display_labels/models.py` (`DisplayLabelJinja2GraphQL` class). It provides:
- Typed query models with `render_query()` / `parse_response()` methods
- Branch parameter passed via `client.execute_graphql(branch_name=...)` (branch-safe by default)
- No new dependencies required

**Alternatives considered**:
- Raw f-string GraphQL queries: Rejected — not typed, harder to test in isolation, does not follow existing project patterns
- New generic query abstraction layer: Rejected — YAGNI; only justified if 3+ callers share identical structure (Principle VII)

---

### Decision 2: Migration Strategy

**Decision**: Migrate tasks one at a time, prioritising the three tasks explicitly flagged with `# NOTE` comments indicating overfetching.

**Priority order**:
1. `backend/infrahub/display_labels/tasks.py` — `client.all()` fetches full nodes when only `id` is needed
2. `backend/infrahub/hfid/tasks.py` — same pattern, same comment
3. `backend/infrahub/computed_attribute/tasks.py` — explicit `# NOTE we need to optimize the query here` comment

Additional tasks to be identified from a full audit of `client.all()` and `client.filters()` calls across the 29 task files.

**Rationale**: The flagged tasks are already understood to be problematic. Starting there delivers measurable improvement immediately and validates the migration pattern before applying it broadly.

**Alternatives considered**:
- Big-bang migration of all tasks at once: Rejected — high risk, harder to verify correctness, contradicts FR-003 (independent deployment per task)

---

### Decision 3: Query Model Structure

**Decision**: Each domain that requires optimized queries gets a typed Pydantic/dataclass query model in its existing `models.py` file (or a new `queries.py` if the models file is already large). The model exposes:
- `render_query() -> str` — returns the GraphQL query string
- `parse_response(response: dict) -> list[...]` — returns a typed result

**Rationale**: Mirrors the `HFIDGraphQL` pattern already in the codebase. Keeps query logic co-located with domain logic, testable in unit tests without a running backend.

---

### Decision 4: Testing Approach

**Decision**: Two test levels per migrated task:
1. **Unit test** for the query model: `render_query()` produces valid GraphQL; `parse_response()` returns expected typed output for a fixture response dict.
2. **Functional test** for the task: run the task against a live test database, compare output before and after optimization.

Existing functional test fixtures and schemas MUST be reused (Principle IV).

**Rationale**: Unit tests validate the query model in isolation (fast, no DB). Functional tests validate the output equivalence guarantee (FR-002, FR-007).

---

### Decision 5: Scope Boundary

**Decision**: This feature covers read-query optimizations only (`client.all()`, `client.get()`, `client.filters()` calls that overfetch). Write operations (`client.create()`, `client.save()`) and mutation queries are out of scope for this iteration.

**Rationale**: Write operations were not identified as performance bottlenecks in the problem statement. Mixing concerns would increase risk without proportional benefit.

---

## Inventory of Overfetching Sites (T001 Audit — 2026-04-29)

Audit performed across all 29 task files. Calls are ranked by severity (estimated data reduction potential).

### Priority 1 — HIGH (`client.all()`, only `id` used)

| File | Line | Current Pattern | Needed Fields | Notes |
|------|------|-----------------|---------------|-------|
| `display_labels/tasks.py` | 202 | `client.all(kind, branch, exclude=attr+rel names)` | `id` | Flagged with `# NOTE` comment; exclude still returns HFID |
| `hfid/tasks.py` | 199 | `client.all(kind, branch, exclude=attr+rel names)` | `id` | Flagged with `# NOTE` comment; same pattern |
| `computed_attribute/tasks.py` | 313 | `client.all(kind, branch)` — no exclude at all | `id` | Flagged with `# NOTE` comment; worst case — no exclusions |

All three dispatch `node.id` as a workflow parameter and use nothing else from the returned node objects.

### Priority 2 — MEDIUM (`client.filters()` returning full objects, few fields used)

| File | Line | Current Pattern | Needed Fields | Notes |
|------|------|-----------------|---------------|-------|
| `git/tasks.py` | 145 | `client.filters(kind=CoreRepository)` | `id`, `name`, `location` | Fan-out for branch creation across all repos |
| `git/tasks.py` | 167 | `client.filters(kind=CoreRepository)` | `id`, `name` | Fan-out for branch deletion |
| `generators/tasks.py` | 112 | `client.filters(kind=CoreGeneratorInstance, definition__ids=..., object__ids=...)` | `id` | Used only to update `.status`; full object fetched |

### Priority 3 — LOW (already partially optimized or need most fields)

| File | Line | Current Pattern | Notes |
|------|------|-----------------|-------|
| `proposed_change/tasks.py` | 276, 282 | `client.filters(..., include=["id", "source_branch"])` | Already restricts fields via `include=` — already partially optimized |
| `artifacts/tasks.py` | 58 | `client.filters(kind=ARTIFACTCHECK, ...)` | Uses 7+ fields (`created_at`, `conclusion`, `severity`, `changed`, `checksum`, `artifact_id`, `storage_id`) — minimal gain |
| `generators/tasks.py` | 192 | `client.filters(kind=GENERATORINSTANCE, include=["object"])` | Uses `instance.object.peer.id` — already uses `include=` |
| `actions/tasks.py` | 233 | `client.filters(kind, ids=..., populate_store=False)` | Used for variable extraction across arbitrary node kinds — fields unknown at call time; skip |

### `client.get()` Candidates

`client.get()` optimization is viable only for pure-read cases — when the fetched node is never passed to `.save()` / `.update()` / `.fetch()`. All other calls require the full SDK object for mutation and are not candidates.

| File | Line | Optimization | Details |
|------|------|--------------|---------|
| `computed_attribute/tasks.py` | 95 | Replace with targeted query returning `commit` only | Pure read — `repo_node.commit.value` is the only field used |
| `computed_attribute/tasks.py` | 84 | Narrow `prefetch_relationships=True` to `include=["repository", "query"]` | Pure read — only `repository.peer.*` and `query.id` consumed |

---

## Baseline Measurement Approach (T002 / T003)

Actual numbers require a running Infrahub instance. Run the following against a live environment **before** any migration code is merged to capture pre-optimization baselines.

### Execution Time Baseline (T002)

Add a timing wrapper around the three `client.all()` call sites before migration:

```python
import time
start = time.perf_counter()
nodes = await client.all(kind=..., branch=...)
elapsed = time.perf_counter() - start
print(f"[BASELINE] client.all({kind}) on branch={branch}: {len(nodes)} nodes in {elapsed:.3f}s")
```

Alternatively, run the component tests with `--benchmark` if `pytest-benchmark` is available:

```bash
uv run pytest backend/tests/component/display_labels/ -v --benchmark-only
uv run pytest backend/tests/component/computed_attribute/ -v --benchmark-only
```

Record: `(domain, node_count, elapsed_seconds)` for each of the three tasks.

### Data Volume Baseline (T003)

Patch `InfrahubClient.execute_graphql` or the underlying HTTP transport temporarily to log response payload size:

```python
# In a test or dev environment — DO NOT merge to main
import sys, json
original = client._client.execute
async def logged(*args, **kwargs):
    result = await original(*args, **kwargs)
    print(f"[BASELINE] payload bytes: {sys.getsizeof(json.dumps(result))}", file=sys.stderr)
    return result
client._client.execute = logged
```

Record: `(domain, node_count, payload_bytes)` for a representative run of each task.

### Results Table (fill in when run)

| Domain | Node Count | Execution Time (s) | Payload Size (bytes) | Date |
|--------|------------|-------------------|----------------------|------|
| `display_labels` | — | — | — | — |
| `hfid` | — | — | — | — |
| `computed_attribute` | — | — | — | — |

---

## Resolved Unknowns

| Unknown | Resolution |
|---------|------------|
| How is branch context passed to custom queries? | Via `client.execute_graphql(branch_name=branch_name)` — already used in hfid and display_labels tasks |
| Is there an existing query builder? | Yes: `infrahub_sdk.graphql.Query` with `.render()` method |
| How is the SDK client obtained in tasks? | Via `get_client()` from `infrahub.workers.dependencies` (dependency injection, singleton per context) |
| Do any tasks already use optimized queries? | hfid and display_labels mutations already use `execute_graphql()`; their read queries are the ones to optimize |
| How many tasks total? | 149 `@flow`/`@task` instances across 29 files; ~3 explicitly flagged, full audit needed |
