# Research: Generator-Before-Artifact Ordering

## Root Cause Analysis

### The Race Condition

**File**: `backend/infrahub/proposed_change/tasks.py`

Two functions collaborate to create the race:

**`run_proposed_change_pipeline()` (line 1159)** dispatches `REQUEST_PROPOSED_CHANGE_RUN_GENERATORS` via `submit_workflow()` (fire-and-forget). For `CheckType.ALL`, it passes `refresh_artifacts=True` and `do_repository_checks=True`, delegating artifact and repo check orchestration to `run_generators`.

**`run_generators()` (line 322)** then dispatches three categories of work, all via `submit_workflow()` (fire-and-forget):

1. Generator definition checks (lines 378-391)
2. Artifact refresh (lines 393-405) if `refresh_artifacts=True`
3. Repository checks (lines 407-419) if `do_repository_checks=True`

All three run concurrently. `run_generators()` returns immediately after submitting them. Artifact generation can start before generators have created their objects.

### Why `submit_workflow` is Fire-and-Forget

In the production adapter `WorkflowWorkerExecution` (`backend/infrahub/services/adapters/workflow/worker.py:87`):

```python
async def submit_workflow(self, ...):
    async with AsyncClientContext(...):
        flow_run = await run_deployment(name=workflow.full_name, timeout=0, ...)
    return WorkflowInfo.from_flow(flow_run=flow_run)
```

`timeout=0` means return immediately without waiting. In contrast, `execute_workflow` uses `poll_interval=1` and blocks until completion.

### Why Tests Don't Catch This

`WorkflowLocalExecution` (`backend/infrahub/services/adapters/workflow/local.py:33`) implements `submit_workflow` by delegating to `execute_workflow`:

```python
async def submit_workflow(self, ...):
    await self.execute_workflow(workflow=workflow, context=context, parameters=parameters)
    return WorkflowInfo(id=uuid.uuid4())
```

All workflows execute synchronously in tests, masking the concurrency issue.

### Design Issue: Mixed Responsibilities

`run_generators()` currently has two responsibilities:
1. Execute generators (its stated purpose)
2. Orchestrate what happens after generators (artifact refresh, repo checks)

This coupling means the function name doesn't reflect what it does, and the sequencing between generators and artifacts is buried inside a function that callers don't expect to handle artifacts. The pipeline function `run_proposed_change_pipeline()` — which is the natural orchestrator — has no visibility into this ordering dependency.

## Decision: Fix Approach

### Decision: Pipeline-level sequencing with single-purpose `run_generators`

Move the generator→artifact ordering to `run_proposed_change_pipeline()` where all pipeline orchestration belongs. Make `run_generators()` single-purpose: run generators, wait for them, return.

**Changes:**

1. **`run_generators()`**: Remove artifact and repo check dispatch. Change generator definition check submissions from `submit_workflow` to `execute_workflow` + `asyncio.gather` so the function blocks until all generators complete.

2. **`RequestProposedChangeRunGenerators`**: Remove `refresh_artifacts` and `do_repository_checks` fields (no longer needed).

3. **`run_proposed_change_pipeline()`**: For `CheckType.ALL`:
   - Dispatch independent checks first (data integrity, schema, user tests) — fire-and-forget, run in parallel with generators
   - Use `execute_workflow` (blocking) for `REQUEST_PROPOSED_CHANGE_RUN_GENERATORS`
   - After generators complete, dispatch artifact refresh and repo checks — fire-and-forget

**Rationale over the simpler "block inside run_generators" approach:**

| Concern | Block inside run_generators | Pipeline-level sequencing |
|---------|---------------------------|--------------------------|
| Prefect slot deadlock | run_generators holds slot while waiting for N children | Same, but pipeline is already long-lived; no extra nesting concern |
| Responsibility | run_generators does 3 things | run_generators does 1 thing |
| Visibility | Ordering hidden inside generator flow | Ordering visible at pipeline level |
| Model coupling | Generator model carries artifact/repo flags | Generator model is about generators only |
| Independent check parallelism | Data/schema/test checks already parallel via pipeline | Same, plus explicit in code flow |
| Cascading failure | Generator failure in gather blocks artifacts | Same — but clearer where to add error handling |

### Alternatives considered

1. **Block inside `run_generators` only** (original plan): Simpler diff, but keeps the mixed responsibility. `run_generators` becomes a blocking compound orchestrator that still dispatches artifacts. The function name misleads about what it does. The Prefect slot concern is identical (need `execute_workflow` for generator def checks either way).

2. **Workflow dependency graph / DAG**: Over-engineered. Would require infrastructure changes to the workflow system for a single ordering dependency.

3. **Polling/status-checking loop**: Fragile. `submit_workflow` returns a `WorkflowInfo` with a flow run ID, but polling for completion reimplements what `execute_workflow` already does with worse ergonomics.

4. **Event-driven callback**: Complex distributed state tracking for "all generators done" with no clear benefit over synchronous waiting.

## Decision: Test Strategy

### Decision: Enhance `WorkflowRecorder` with ordered call tracking

The `WorkflowRecorder` test adapter (`backend/tests/adapters/workflow.py`) records `execute_calls` and `submit_calls` separately. After the fix:

- Generator definition checks appear in `execute_calls` (blocking)
- Artifact refresh and repo checks appear in `submit_calls` (fire-and-forget)
- Pipeline-level generator call appears in `execute_calls`

Add an `all_calls` list that records every call in order (both execute and submit) with a discriminator. Tests can assert:
1. All `REQUEST_GENERATOR_DEFINITION_CHECK` calls are `execute` type
2. `REQUEST_PROPOSED_CHANGE_RUN_GENERATORS` at pipeline level is `execute` type
3. `REQUEST_PROPOSED_CHANGE_REFRESH_ARTIFACTS` appears after all generator calls

Note: This proves call-type correctness but not temporal ordering in production. The actual race only manifests with the worker adapter's async Prefect dispatching. Integration tests against real Prefect workers would be needed for full confidence.

## Decision: Repository Checks Ordering

### Decision: Repository checks also wait for generators

Repository checks (user-defined Python checks) may reference generator-created objects. Same ordering guarantee applies. Artifacts and repo checks are independent of each other and can run concurrently after generators complete.

## Workflow Execution Flow (After Fix)

### CheckType.ALL

```
run_proposed_change_pipeline()
  │
  ├─ [fire-and-forget] submit_workflow(DATA_INTEGRITY)          ─┐
  ├─ [fire-and-forget] submit_workflow(SCHEMA_INTEGRITY)         ├─ run in parallel
  ├─ [fire-and-forget] submit_workflow(USER_TESTS)              ─┘    with generators
  │
  ├─ [BLOCKING] execute_workflow(RUN_GENERATORS)
  │     └─ run_generators()
  │          ├─ [parallel] execute_workflow(GEN_DEF_CHECK) × N
  │          └─ asyncio.gather() waits for all N
  │          └─ returns
  │
  ├─ ← generators complete ─┤
  │
  ├─ [fire-and-forget] submit_workflow(REFRESH_ARTIFACTS)
  └─ [fire-and-forget] submit_workflow(REPO_CHECKS)
```

### CheckType.GENERATOR (unchanged behavior)

```
run_proposed_change_pipeline()
  └─ [fire-and-forget] submit_workflow(RUN_GENERATORS)
       └─ run_generators() — submit generator checks, return immediately
```

Wait — this raises a question. For `CheckType.GENERATOR`, should `run_generators` still be fire-and-forget? There are no artifacts to wait for, so the ordering doesn't matter. But `run_generators` itself should still wait for its generator checks to complete so that it accurately reflects generator completion status. Changed to `execute_workflow` + gather for consistency.

### CheckType.ARTIFACT (unchanged)

```
run_proposed_change_pipeline()
  └─ [fire-and-forget] submit_workflow(REFRESH_ARTIFACTS)
```

## Key Files

| File | Change |
|------|--------|
| `backend/infrahub/proposed_change/tasks.py` | Modify `run_generators()` (remove artifact/repo dispatch, use execute_workflow + gather) and `run_proposed_change_pipeline()` (add sequencing) |
| `backend/infrahub/proposed_change/models.py` | Remove `refresh_artifacts` and `do_repository_checks` from `RequestProposedChangeRunGenerators` |
| `backend/tests/adapters/workflow.py` | Add ordered call tracking to `WorkflowRecorder` |
| `backend/tests/unit/proposed_change/test_run_generators.py` | NEW: ordering tests |
| `backend/infrahub/services/adapters/workflow/worker.py` | No changes |
| `backend/infrahub/services/adapters/workflow/__init__.py` | No changes |
| `backend/infrahub/core/validators/checks_runner.py` | No changes (reference pattern) |
| `backend/infrahub/workflows/catalogue.py` | No changes |
