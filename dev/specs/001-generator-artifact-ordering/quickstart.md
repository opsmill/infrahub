# Quickstart: Verifying Generator-Before-Artifact Ordering

## Run Unit Tests

```bash
# Run new ordering tests
uv run pytest backend/tests/unit/proposed_change/test_run_generators.py -v

# Run all backend unit tests to check for regressions
uv run invoke backend.test-unit
```

## Run Existing Integration Tests

```bash
# Proposed change pipeline tests
uv run pytest backend/tests/integration/message_bus/operations/request/test_proposed_change.py -v
```

## Manual Verification (Production/Staging)

To verify the fix in a running instance:

1. **Set up a generator and artifact that share data:**
   - Create a `GeneratorDefinition` that creates objects (e.g., interface configs)
   - Create an `ArtifactDefinition` whose query reads those generator-created objects
   - Both should be configured with `execute_in_proposed_change=True`

2. **Create a proposed change that triggers both:**
   - Make a data change on a branch that affects both the generator's query models and the artifact's query models
   - Open a proposed change targeting that branch

3. **Observe Prefect flow runs:**
   - `proposed-changed-pipeline` should show `proposed-changed-run-generator` completing BEFORE `proposed-changed-refresh-artifacts` starts
   - Independent checks (data integrity, schema, user tests) should start concurrently with generators

4. **Verify artifact content:**
   - The generated artifact should include data from generator-created objects
   - Previously, the artifact might have been generated with stale/missing data

## What Changed

| Component | Before | After |
|-----------|--------|-------|
| `run_generators()` | Dispatches generator checks, artifact refresh, and repo checks — all fire-and-forget | Single-purpose: dispatches generator checks via `execute_workflow` + `asyncio.gather`, blocks until complete |
| `run_proposed_change_pipeline()` | Delegates artifact/repo dispatch to `run_generators` | Owns sequencing: blocks on generators, then dispatches artifacts + repo checks |
| `RequestProposedChangeRunGenerators` | Carries `refresh_artifacts` and `do_repository_checks` flags | Generator-only model, no artifact/repo coupling |
| Independent checks | Dispatched after generators in code order (but all fire-and-forget so irrelevant) | Explicitly dispatched before the generator blocking call so they run concurrently |

## Key Files

- `backend/infrahub/proposed_change/tasks.py` — `run_generators()` and `run_proposed_change_pipeline()`
- `backend/infrahub/proposed_change/models.py` — `RequestProposedChangeRunGenerators`
- `backend/tests/adapters/workflow.py` — `WorkflowRecorder`
