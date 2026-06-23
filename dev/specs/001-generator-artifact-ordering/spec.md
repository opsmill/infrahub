# Feature Spec: Generator-Before-Artifact Ordering in Proposed Change Pipeline

**Date**: 2026-04-10
**Status**: Draft

## Problem Statement

When a proposed change pipeline runs with `CheckType.ALL`, generators and artifacts are both dispatched as fire-and-forget workflows via `submit_workflow()`. This means artifact generation can start before generators have finished creating their objects. Artifacts that depend on generator-created data will produce stale or incomplete results.

## Current Behavior

In `run_generators()` (`backend/infrahub/proposed_change/tasks.py:322`):

1. Generator definition checks are submitted via `submit_workflow()` (non-blocking, returns immediately)
2. Artifact refresh is submitted via `submit_workflow()` (non-blocking, returns immediately)
3. Repository checks are submitted via `submit_workflow()` (non-blocking, returns immediately)

All three steps execute concurrently. There is no ordering guarantee.

The `submit_workflow()` method in the production adapter (`WorkflowWorkerExecution`) uses Prefect's `run_deployment(timeout=0)`, which is fire-and-forget. In contrast, `execute_workflow()` uses `run_deployment(poll_interval=1)`, which blocks until the workflow completes.

**Note:** In the local/test adapter (`WorkflowLocalExecution`), `submit_workflow` delegates to `execute_workflow`, making all calls blocking. This masks the race condition in tests.

## Desired Behavior

1. `run_generators()` becomes single-purpose: run generator definition checks (in parallel) and block until all complete
2. `run_proposed_change_pipeline()` owns the sequencing: block on generators, then dispatch artifact refresh and repo checks
3. Independent checks (data integrity, schema, user tests) run in parallel with generators
4. `RequestProposedChangeRunGenerators` model no longer carries `refresh_artifacts` / `do_repository_checks` flags

## Scope

### In Scope

- Modify `run_generators()` to use `execute_workflow` + `asyncio.gather` and remove artifact/repo check dispatch
- Modify `run_proposed_change_pipeline()` to own generator→artifact→repo-check sequencing
- Remove `refresh_artifacts` and `do_repository_checks` from `RequestProposedChangeRunGenerators`
- Add tests that verify the ordering guarantee

### Out of Scope

- Changes to the `WorkflowLocalExecution` or `WorkflowWorkerExecution` adapters
- Changes to the artifact generation logic itself
- Adding a general-purpose workflow dependency mechanism

## Requirements

1. **R1**: Artifact refresh MUST NOT begin until all generator definition checks have completed
2. **R2**: Repository checks MUST NOT begin until all generator definition checks have completed
3. **R3**: Generator definition checks SHOULD continue to run in parallel with each other
4. **R4**: Independent checks (data integrity, schema, user tests) SHOULD run in parallel with generators
5. **R5**: The fix MUST work in both local and worker execution modes
6. **R6**: Existing tests must continue to pass
7. **R7**: New tests must verify the ordering guarantee using the `WorkflowRecorder` test adapter

## Acceptance Criteria

- [ ] Generator workflows complete before artifact refresh is dispatched
- [ ] Generator workflows complete before repository checks are dispatched
- [ ] Multiple generator definitions still execute in parallel
- [ ] Independent checks (data, schema, tests) are not blocked by generators
- [ ] `run_generators()` no longer dispatches artifact or repo check workflows
- [ ] `RequestProposedChangeRunGenerators` has no artifact/repo-check fields
- [ ] Unit tests verify ordering using `WorkflowRecorder`
- [ ] Integration tests pass
