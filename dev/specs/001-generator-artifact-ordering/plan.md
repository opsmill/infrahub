# Implementation Plan: Generator-Before-Artifact Ordering

**Branch**: `001-generator-artifact-ordering` | **Date**: 2026-04-10 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-generator-artifact-ordering/spec.md`

## Summary

Fix a race condition where artifact generation and repository checks can start before generators finish creating objects during a proposed change pipeline. The fix moves sequencing responsibility to `run_proposed_change_pipeline()` (the natural orchestrator) and makes `run_generators()` single-purpose — it runs generators and blocks until they complete, nothing else.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, Prefect (workflow engine), Pydantic 2.10, infrahub-sdk
**Storage**: Neo4j 5.28 (graph database)
**Testing**: pytest 9.0 (unit + integration)
**Target Platform**: Linux server (Docker containers)
**Project Type**: Web application (backend focus for this change)
**Performance Goals**: No regression in pipeline throughput. Generator definitions remain parallelized. Independent checks (data integrity, schema, user tests) remain parallel with generators.
**Constraints**: Must work with both `WorkflowLocalExecution` (tests) and `WorkflowWorkerExecution` (production/Prefect workers)
**Scale/Scope**: 3 files modified, 1 new test file. ~50 lines changed, ~30 lines removed.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution is unconfigured (template only). No gates to enforce.

**Post-design re-check**: No constitution gates exist. Design proceeds without constraint.

## Project Structure

### Documentation (this feature)

```text
specs/001-generator-artifact-ordering/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Root cause analysis and decision log
├── data-model.md        # Entity documentation (no schema changes)
└── quickstart.md        # Verification guide
```

### Source Code (repository root)

```text
backend/
├── infrahub/
│   └── proposed_change/
│       ├── tasks.py            # PRIMARY: modify run_generators() + run_proposed_change_pipeline()
│       └── models.py           # Remove refresh_artifacts/do_repository_checks fields
└── tests/
    ├── adapters/
    │   └── workflow.py          # Enhance WorkflowRecorder with ordered tracking
    └── unit/proposed_change/
        └── test_run_generators.py  # NEW: ordering tests
```

**Structure Decision**: Backend-only change. Modifies two production files, enhances one test adapter, adds one test file.

## Implementation Steps

### Step 1: Simplify `RequestProposedChangeRunGenerators` model

**File**: `backend/infrahub/proposed_change/models.py`

Remove the `refresh_artifacts` and `do_repository_checks` fields. These flags coupled generator execution with artifact/repo check dispatch. That responsibility moves to the pipeline.

**Before** (lines 27-33):
```python
class RequestProposedChangeRunGenerators(BaseProposedChangeWithDiffMessage):
    """Sent trigger the generators that are impacted by the proposed change to run."""

    refresh_artifacts: bool = Field(..., description="Whether to regenerate artifacts after the generators are run")
    do_repository_checks: bool = Field(
        ..., description="Whether to run repository and user checks after the generators are run"
    )
```

**After**:
```python
class RequestProposedChangeRunGenerators(BaseProposedChangeWithDiffMessage):
    """Sent to trigger the generators that are impacted by the proposed change to run."""
```

### Step 2: Make `run_generators()` single-purpose and blocking

**File**: `backend/infrahub/proposed_change/tasks.py`, function `run_generators()` (line 322)

Changes:
1. Change generator definition check dispatch from `submit_workflow` to `execute_workflow`
2. Use `asyncio.gather` to run all generator checks in parallel but wait for all to complete
3. Remove artifact refresh dispatch (lines 393-405)
4. Remove repository checks dispatch (lines 407-419)

**Current code** (lines 357-419):
```python
    for generator_definition in generator_definitions:
        # ... selection logic ...
        if select:
            await get_workflow().submit_workflow(
                workflow=REQUEST_GENERATOR_DEFINITION_CHECK,
                parameters={"model": request_generator_def_check_model},
                context=context,
            )

    if model.refresh_artifacts:
        # ... build model ...
        await get_workflow().submit_workflow(
            workflow=REQUEST_PROPOSED_CHANGE_REFRESH_ARTIFACTS, ...)

    if model.do_repository_checks:
        # ... build model ...
        await get_workflow().submit_workflow(
            workflow=REQUEST_PROPOSED_CHANGE_REPOSITORY_CHECKS, ...)
```

**New code**:
```python
    generator_check_coroutines: list[Coroutine] = []
    for generator_definition in generator_definitions:
        # ... selection logic unchanged ...
        if select:
            request_generator_def_check_model = RequestGeneratorDefinitionCheck(...)
            generator_check_coroutines.append(
                get_workflow().execute_workflow(
                    workflow=REQUEST_GENERATOR_DEFINITION_CHECK,
                    parameters={"model": request_generator_def_check_model},
                    context=context,
                )
            )

    if generator_check_coroutines:
        await asyncio.gather(*generator_check_coroutines, return_exceptions=True)
```

Note `return_exceptions=True`: if one generator definition fails, we still collect all results rather than aborting. This preserves the current behavior where a failing generator doesn't prevent other generators from running.

Add `import asyncio` at top of file if not already present.

### Step 3: Restructure `run_proposed_change_pipeline()` for sequencing

**File**: `backend/infrahub/proposed_change/tasks.py`, function `run_proposed_change_pipeline()` (line 1159)

For `CheckType.ALL`, the pipeline must:
1. Dispatch independent checks (fire-and-forget) — these run in parallel with generators
2. Block on generator execution
3. After generators complete, dispatch artifact refresh and repo checks

**Current flow** (lines 1203-1293):
```python
    if model.check_type is CheckType.ARTIFACT:
        await submit_workflow(REFRESH_ARTIFACTS, ...)

    if model.check_type in [CheckType.ALL, CheckType.GENERATOR]:
        await submit_workflow(RUN_GENERATORS, ...,
            refresh_artifacts=model.check_type is CheckType.ALL,
            do_repository_checks=model.check_type is CheckType.ALL)

    if model.check_type in [CheckType.ALL, CheckType.DATA]:
        await submit_workflow(DATA_INTEGRITY, ...)

    if model.check_type in [CheckType.REPOSITORY, CheckType.USER]:
        await submit_workflow(REPO_CHECKS, ...)

    if model.check_type in [CheckType.ALL, CheckType.SCHEMA]:
        await submit_workflow(SCHEMA_INTEGRITY, ...)

    if model.check_type in [CheckType.ALL, CheckType.TEST]:
        await submit_workflow(USER_TESTS, ...)
```

**New flow**:
```python
    # --- Phase 1: Dispatch standalone artifact refresh (CheckType.ARTIFACT only) ---

    if model.check_type is CheckType.ARTIFACT:
        await submit_workflow(REFRESH_ARTIFACTS, ...)

    # --- Phase 2: Dispatch checks independent of generators (fire-and-forget) ---

    if model.check_type in [CheckType.ALL, CheckType.DATA] and has_node_changes(...):
        await submit_workflow(DATA_INTEGRITY, ...)

    if model.check_type in [CheckType.REPOSITORY, CheckType.USER]:
        await submit_workflow(REPO_CHECKS, ...)

    if model.check_type in [CheckType.ALL, CheckType.SCHEMA] and has_data_changes(...):
        await submit_workflow(SCHEMA_INTEGRITY, ...)

    if model.check_type in [CheckType.ALL, CheckType.TEST]:
        await submit_workflow(USER_TESTS, ...)

    # --- Phase 3: Run generators and WAIT for completion ---

    if model.check_type in [CheckType.ALL, CheckType.GENERATOR]:
        model_run_generators = RequestProposedChangeRunGenerators(
            proposed_change=model.proposed_change,
            source_branch=model.source_branch,
            source_branch_sync_with_git=model.source_branch_sync_with_git,
            destination_branch=model.destination_branch,
            branch_diff=branch_diff,
        )
        await get_workflow().execute_workflow(
            workflow=REQUEST_PROPOSED_CHANGE_RUN_GENERATORS,
            context=context,
            parameters={"model": model_run_generators},
        )

    # --- Phase 4: Dispatch generator-dependent checks (fire-and-forget) ---

    if model.check_type is CheckType.ALL:
        request_refresh_artifact_model = RequestProposedChangeRefreshArtifacts(
            proposed_change=model.proposed_change,
            source_branch=model.source_branch,
            source_branch_sync_with_git=model.source_branch_sync_with_git,
            destination_branch=model.destination_branch,
            branch_diff=branch_diff,
        )
        await get_workflow().submit_workflow(
            workflow=REQUEST_PROPOSED_CHANGE_REFRESH_ARTIFACTS,
            parameters={"model": request_refresh_artifact_model},
            context=context,
        )

        model_proposed_change_repo_checks = RequestProposedChangeRepositoryChecks(
            proposed_change=model.proposed_change,
            source_branch=model.source_branch,
            source_branch_sync_with_git=model.source_branch_sync_with_git,
            destination_branch=model.destination_branch,
            branch_diff=branch_diff,
        )
        await get_workflow().submit_workflow(
            workflow=REQUEST_PROPOSED_CHANGE_REPOSITORY_CHECKS,
            context=context,
            parameters={"model": model_proposed_change_repo_checks},
        )
```

Key points:
- `CheckType.ARTIFACT` (standalone artifact refresh, no generators involved) remains unchanged at the top
- Independent checks dispatch before the blocking generator call so they run concurrently
- `CheckType.ALL` dispatches artifacts and repo checks in Phase 4 — after generators complete
- `RequestProposedChangeRunGenerators` no longer carries `refresh_artifacts`/`do_repository_checks`

### Step 4: Enhance `WorkflowRecorder` for ordered tracking

**File**: `backend/tests/adapters/workflow.py`

Add an `all_calls` list that records every call in submission order with a type discriminator:

```python
class WorkflowRecorder(InfrahubWorkflow):
    def __init__(self) -> None:
        self.execute_calls: list[dict[str, Any]] = []
        self.submit_calls: list[dict[str, Any]] = []
        self.all_calls: list[dict[str, Any]] = []  # NEW: ordered log

    async def execute_workflow(self, ...):
        record = {"workflow": workflow, "parameters": parameters or {}, "type": "execute"}
        self.execute_calls.append(record)
        self.all_calls.append(record)
        ...

    async def submit_workflow(self, ...):
        record = {"workflow": workflow, "parameters": parameters or {}, "type": "submit"}
        self.submit_calls.append(record)
        self.all_calls.append(record)
        ...
```

### Step 5: Add unit tests for ordering guarantee

**File**: `backend/tests/unit/proposed_change/test_run_generators.py` (NEW)

Test cases:

1. **test_generators_use_execute_workflow**: Verify `REQUEST_GENERATOR_DEFINITION_CHECK` calls appear in `execute_calls` (not `submit_calls`) on the `WorkflowRecorder`
2. **test_no_artifact_dispatch_from_run_generators**: Verify `run_generators` does not submit `REQUEST_PROPOSED_CHANGE_REFRESH_ARTIFACTS`
3. **test_no_repo_check_dispatch_from_run_generators**: Verify `run_generators` does not submit `REQUEST_PROPOSED_CHANGE_REPOSITORY_CHECKS`
4. **test_pipeline_dispatches_artifacts_after_generators**: Verify that in the `all_calls` log, `REFRESH_ARTIFACTS` appears after `RUN_GENERATORS`
5. **test_pipeline_generator_only_no_artifacts**: For `CheckType.GENERATOR`, verify no artifact refresh is dispatched
6. **test_pipeline_artifact_only_no_generators**: For `CheckType.ARTIFACT`, verify artifact refresh is dispatched without waiting for generators

### Step 6: Verify existing tests pass

```bash
uv run invoke backend.test-unit
uv run pytest backend/tests/integration/message_bus/operations/request/test_proposed_change.py -v
```

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Prefect slot exhaustion from `execute_workflow` nesting | Low | Medium | Typical deployments have few generator definitions (1-5). Monitor work pool utilization in staging. |
| Generator failure blocks artifact dispatch | Medium | Low | `asyncio.gather(return_exceptions=True)` collects all results. Pipeline proceeds to Phase 4 regardless. |
| Pipeline flow lifetime increases | Expected | Low | `run_proposed_change_pipeline` now blocks for generator duration. This is intentional and correct — the pipeline should reflect actual completion state. |
| `WorkflowLocalExecution` behavior difference | None | None | `execute_workflow` already blocks in local mode. `submit_workflow` delegates to `execute_workflow`. No behavioral change. |
| Existing tests break from model field removal | Medium | Low | Tests that construct `RequestProposedChangeRunGenerators` with `refresh_artifacts`/`do_repository_checks` need updating. Grep for usages. |

## Complexity Tracking

No constitution violations to justify.
