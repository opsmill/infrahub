# Data Model: Usage counts in the daily telemetry report

**Date**: 2026-11-26 | **Plan**: [plan.md](plan.md) | **Research**: [research.md](research.md)

The change adds no node, attribute or relationship to the graph. The data model is the payload of the daily report, defined by the Pydantic models in `backend/infrahub/telemetry/models.py`, plus three internal types that carry the result of a read.

## Payload models

### `TelemetryWorkflowRunData` (new)

The runs of one workflow that ended in one state on the previous UTC day.

| Field | Type | Meaning |
|-------|------|---------|
| `workflow` | `str` | The workflow name, one of the 8 names in `task_manager.py::REPORTED_WORKFLOW_NAMES`. Never a run name. |
| `state` | `WorkflowRunState \| None` | The end state, a string enum in `constants.py` with the values `COMPLETED`, `FAILED`, `CRASHED` and `CANCELLED`. `None` when the read for the workflow failed. |
| `runs` | `int \| None` | The number of runs that ended in the state. `None` when the read failed. |
| `run_seconds` | `int \| None` | The time those runs spent running, in whole seconds, rounded after the sum. `None` when the read failed. |

Rules:

- `state`, `runs` and `run_seconds` are all set or all `None`. The model rejects a row that sets only some of them, and a negative `runs` or `run_seconds`.
- A workflow has at most one row per end state, and exactly one row when its read failed or was not answered within 60 seconds.
- A workflow with no run in an end state has no row.
- Rows are ordered by workflow, in the order of `REPORTED_WORKFLOW_NAMES`, then by state, in the order `COMPLETED`, `FAILED`, `CRASHED`, `CANCELLED`.

### `TelemetryActivity24hData` (two new fields)

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `validators_started` | `dict[str, int \| None] \| None` | `None` | The number of started validators per validator kind for the previous UTC day. |
| `workflow_runs` | `list[TelemetryWorkflowRunData] \| None` | `None` | The run rows for the previous UTC day. |

Rules for `validators_started`:

- The keys are the kinds that inherit from `CoreValidator` in the schema of the default branch, sorted by name.
- A kind with no started validator has the value `0`.
- A kind whose count failed, was not answered within 60 seconds, or got a response with an unexpected shape has the value `None`.
- The map is `None` when the kinds could not be read from the schema, or when the whole activity gather failed.

Rules for `workflow_runs`:

- An empty list when no named workflow had a run in an end state.
- `None` only when the whole activity gather failed, for example when the task manager client could not be created.

The existing fields of the model are not changed. `checks_started` still counts every started validator of all kinds.

### `TelemetryData.features` (type widened)

- Before: `dict[str, int]`. After: `dict[str, int | None]`.
- Three new keys: `CoreArtifactDefinition`, `CoreCheckDefinition`, `CoreGeneratorDefinition`.
- Each new key counts the nodes of the kind that exist on the default branch. A kind with no node has the value `0`.
- The three new keys are `None` together when their read failed.
- The existing keys keep their values and are never `None`. They count the graph vertices with the label on every branch, deleted nodes included.

### `TelemetryDatabaseData.node_count` (five new keys)

The type is already `dict[str, int | None]`.

| Key | Meaning | `None` when |
|-----|---------|-------------|
| `artifact_target` | Nodes on the default branch whose kind inherits from `CoreArtifactTarget`. `0` when no kind inherits from it. | The count failed. |
| `with_artifact` | Nodes on the default branch with at least one artifact node. | The artifact read failed. |
| `with_generated_artifact` | Nodes on the default branch with at least one artifact whose `storage_id` is set. | The artifact read failed. |
| `generated_artifact` | Artifacts on the default branch whose `storage_id` is set. | The artifact read failed. |
| `with_generator_instance` | Nodes on the default branch with at least one generator instance, whatever its status. | The generator instance read failed. |

Rules:

- `with_generated_artifact` is never larger than `with_artifact`, and never larger than `generated_artifact`.
- A deleted node, a deleted artifact, a deleted generator instance, and an artifact or instance that exists only on another branch are not counted.

## Internal types

### `RunHistoryState` and `RunHistoryInterval` (`task_manager.py`)

Pydantic models for the response of `POST /flow_runs/history`. The response is a list of intervals, and each interval has a list of states.

| Model | Field | Type | Source |
|-------|-------|------|--------|
| `RunHistoryState` | `state_type` | `StateType` | `state_type` of the entry |
| `RunHistoryState` | `count_runs` | `int` | `count_runs` |
| `RunHistoryState` | `sum_estimated_run_time` | `timedelta` | `sum_estimated_run_time`, a decimal number of seconds |
| `RunHistoryInterval` | `states` | `list[RunHistoryState]` | `states` |

A response that lacks one of these fields fails validation, and the read for that workflow counts as failed.

### `EventCountBucket` (`task_manager.py`)

Pydantic model for one bucket of the response of `POST /events/count-by/event` and `POST /events/count-by/resource`. It has one field, `count: int`. A response that is not a list of such buckets fails validation, and the event count that reads it counts as failed.

### `NodesWithOutputCount` (`queries.py`)

Frozen dataclass returned by `CountNodesWithOutputQuery.get_data()`.

| Field | Type | Meaning |
|-------|------|---------|
| `nodes` | `int` | Target nodes with at least one active output node. |
| `nodes_with_content` | `int` | Target nodes with at least one output whose content attribute is set. `0` when the query has no content attribute. |
| `outputs_with_content` | `int` | Output nodes whose content attribute is set. `0` when the query has no content attribute. |

Mapping to the payload:

- Output kind `CoreArtifact`, content attribute `storage_id`: `nodes` is `with_artifact`, `nodes_with_content` is `with_generated_artifact`, `outputs_with_content` is `generated_artifact`.
- Output kind `CoreGeneratorInstance`, no content attribute: `nodes` is `with_generator_instance`.

## What `null`, `0` and an empty list mean

| Value | Nothing to count | The read failed |
|-------|------------------|-----------------|
| `workflow_runs` | Empty list | One row per failed workflow with `state`, `runs` and `run_seconds` set to `null` |
| A key of `validators_started` | `0` | `null` |
| `validators_started` as a whole | Map with every kind at `0` | `null` when the kinds could not be read |
| The three new `features` keys | `0` | `null` together |
| `artifact_target` | `0` | `null` |
| `with_artifact`, `with_generated_artifact`, `generated_artifact` | `0` | `null` together |
| `with_generator_instance` | `0` | `null` |

## State transitions

None. Each report is computed from the current state of the task manager and of the graph, and no value depends on an earlier report.
