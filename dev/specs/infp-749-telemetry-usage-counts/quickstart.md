# Quickstart: validate the usage counts in the daily telemetry report

**Date**: 2026-11-26 | **Plan**: [plan.md](plan.md) | **Contract**: [contracts/telemetry-payload.md](contracts/telemetry-payload.md)

Run every command from the repository root.

## Prerequisites

- Python dependencies installed: `uv sync --all-groups`
- A running Docker daemon. The component tests start Neo4j and the task manager through testcontainers.

## 1. Run the telemetry tests

```bash
uv run pytest backend/tests/unit/telemetry backend/tests/component/telemetry
```

Expected: every test passes. The tests that cover the new values:

- `backend/tests/unit/telemetry/test_task_manager.py::test_build_workflow_run_rows`: the rows per end state, the sum before rounding, the states that are left out, the order of the rows
- `backend/tests/component/telemetry/test_task_manager.py`:
  - `test_gather_workflow_runs_rows_per_workflow_and_end_state`: rows against a real task manager, the window, a workflow that is not reported
  - `test_gather_workflow_runs_reports_each_failed_read`: one row with null figures per workflow when every read fails
  - `test_gather_activity_24h_validators_started_per_kind`: the count per kind and `0` for a kind with no event
  - `test_count_started_validators_reads_the_kind_of_the_validator_only`: an event is counted under the kind of its own resource
- `backend/tests/component/telemetry/test_database.py`:
  - `test_gather_database_information_artifact_totals`
  - `test_gather_database_information_generator_instance_total`
  - `test_gather_database_information_survives_output_count_failure`
- `backend/tests/component/telemetry/test_tasks.py`:
  - `test_list_validator_kinds`: the six validator kinds
  - `test_gather_feature_information_counts_definitions_on_the_default_branch`
  - `test_gather_full_payload_fields_present`: the new fields are in the full report

## 2. Run the linters

```bash
uv run invoke format
```

```bash
uv run invoke backend.lint
```

Expected: no change from the formatter, and `ruff`, `ty` and `mypy` report no error.

## 3. Check the documentation

```bash
uv run invoke docs.lint
```

```bash
uv run invoke docs.validate
```

Expected: no error. `docs.lint` needs Vale and `markdownlint-cli2`. `docs.validate` compares the generated reference docs with the committed ones, so run it on a tree with the docs changes committed. The change regenerates no reference doc.

## 4. Read a report on a local deployment

1. Start a local deployment from the branch and wait until the `anonymous_telemetry_send` workflow has run once, or start the workflow by hand from the task manager.
2. Read the stored report with `infrahubctl telemetry export`, or with `GET /api/telemetry/snapshots`.
3. Compare the new keys with [contracts/telemetry-payload.md](contracts/telemetry-payload.md):
   - `activity_24h.workflow_runs` is a list. It is empty on a deployment where none of the 8 workflows ran on the previous UTC day.
   - `activity_24h.validators_started` has six keys, each `0` on a deployment with no proposed change on the previous UTC day.
   - `features` has the three definition keys.
   - `database.node_count` has the five new keys.
4. Confirm that `payload_format` is `20260628`.

To get rows in `workflow_runs`, run a generator or generate an artifact, then read the report of the next UTC day: a report covers the previous full UTC day only.

## 5. Confirm that a failed read does not stop the report

The component tests of step 1 cover this without a deployment:

- `test_gather_workflow_runs_reports_each_failed_read` for the run history
- `test_gather_database_information_survives_output_count_failure` for the read of artifacts and generator instances

[Research R16](research.md) lists the failure cases that have no test yet.
