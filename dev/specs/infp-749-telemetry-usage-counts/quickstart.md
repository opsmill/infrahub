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

- `backend/tests/unit/telemetry/test_task_manager.py`:
  - `test_build_workflow_run_rows`: the rows per end state, the sum before rounding, the states that are left out, the order of the rows
  - `test_gather_workflow_runs_keeps_the_other_rows_when_one_read_fails` and `test_count_started_validators_keeps_the_other_kinds_when_one_count_fails`: one failed read among reads that succeed, with a task manager client on a scripted HTTP transport
- `backend/tests/component/telemetry/test_task_manager.py`:
  - `test_gather_workflow_runs_rows_per_workflow_and_end_state`: rows against a real task manager, the window, a workflow that is not reported
  - `test_gather_workflow_runs_reports_each_failed_read`: one row with null figures per workflow when every read fails
  - `test_gather_activity_24h_validators_started_per_kind`: the count per kind and `0` for a kind with no event
  - `test_count_started_validators_reads_the_kind_of_the_validator_only`: an event is counted under the kind of its own resource
  - `test_gather_activity_24h_unreadable_validator_kinds_nulls_only_the_count_per_kind`: a failed read of the validator kinds leaves the other activity values
- `backend/tests/component/telemetry/test_database.py`:
  - `test_gather_database_information_artifact_totals`
  - `test_gather_database_information_generator_instance_total`
  - `test_gather_database_information_survives_output_count_failure`
  - `test_gather_database_information_failed_artifact_read_nulls_only_the_artifact_totals`
- `backend/tests/component/telemetry/test_tasks.py`:
  - `test_list_validator_kinds`: the six validator kinds
  - `test_gather_feature_information_counts_definitions_on_the_default_branch`
  - `test_gather_full_payload_fields_present`: the new fields are in the full report
  - `test_gather_feature_information_failed_definition_read_nulls_only_the_definitions`
  - `test_gather_full_report_contains_no_customer_defined_name`: a full report on customer-defined kinds with an artifact and a generator instance

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

## 5. Run the workflows once for real

[Research R5](research.md) says what one run means and which state a run ends in when the work fails. Both were read in the code. This step checks them on a deployment, without waiting for the next UTC day.

1. On the local deployment, run one generator that succeeds and one that raises, and generate one artifact that succeeds and one whose transformation raises. Do each of the four outside a proposed change and inside a proposed change.
2. In a Python shell in the task worker container, call `infrahub.telemetry.task_manager.gather_workflow_runs` with a task manager client and the window of the current UTC day.
3. Compare the rows with the paragraph about end states in User Story 1 of [spec.md](spec.md), and record the rows in research R5.

## 6. Confirm that a failed read does not stop the report

The tests of step 1 cover this without a deployment: one test for each failure case of User Story 4 in [spec.md](spec.md).
