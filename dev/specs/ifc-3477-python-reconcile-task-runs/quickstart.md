# Quickstart: Validate that a branch deletion records a fixed number of task runs

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Contract**: [contracts/task-runs-and-messages.md](contracts/task-runs-and-messages.md)

## Prerequisites

- `uv sync --all-groups` has been run.
- A running Docker daemon, because component tests start their services with testcontainers.

## 1. Run the new and changed component tests

```bash
uv run pytest backend/tests/component/computed_attribute/test_reconcile_task_runs.py -v
uv run pytest backend/tests/component/computed_attribute/test_gather.py -v
```

Expected:

- The task-run counts with 2 and with 10 branches are equal and greater than zero, for:
  - a branch deletion;
  - a schema update;
  - a Python transform create, update and delete.
- After the deletion, the node-input automations equal the set the gather produces, and none belongs to the deleted branch.
- The missing-transform warning names the branch and the transform.
- A failure on one branch raises the original exception with a note that names the branch.

## 2. Show that the guard works

Put `@task(name="gather-python-transform-attributes", task_run_name="Gather Python transform attributes for {branch_name}", cache_policy=NONE)` back on `gather_python_transform_attributes` and re-run step 1. The count comparisons must fail. Remove the decorator again.

## 3. Run the existing computed-attribute suites

```bash
uv run pytest backend/tests/component/computed_attribute/ -v
uv run pytest backend/tests/functional/computed_attributes/ -v
```

The integration Docker tests that run the reconcile are `backend/tests/integration_docker/test_computed_attributes.py` and `test_merge_recompute.py`. CI runs them in its integration Docker job with `uv run pytest backend/tests/integration_docker/`.

Expected: all pass with no change to their assertions.

## 4. Optional: check on a running instance

1. Start a development instance (`uv run invoke dev.start`) and load a schema with at least one Python computed attribute.
2. Create 10 branches, then delete one.
3. In the task list of the web interface, open the `Setup computed attributes for Python transforms in task-manager` run that the deletion started.
4. Expected: 4 task runs, and no task run named `Gather Python transform attributes for <branch>`.
5. Delete a second branch with 50 branches open. The new run also holds 4 task runs.
6. Record the observed count in the pull request.

On `stable`, the `branch-purge-tasks` flow that a branch deletion starts deletes the flow runs tagged with the deleted branch. It can remove the setup run before you open it. If the run is gone, delete another branch and open its run as soon as it completes.

## 5. Lint and the changelog

```bash
uv run invoke format
uv run invoke lint
uv run ruff check . --exclude python_sdk
uv run towncrier build --draft --version 0.0.0 | grep -A3 "11165"
```

Expected: no lint errors, and the draft changelog shows the `fixed` entry for #11165.
