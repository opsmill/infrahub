from dataclasses import dataclass, field
from datetime import UTC
from typing import Any
from uuid import uuid4

import pytest
from prefect.client.schemas.objects import FlowRun, StateType
from prefect.client.schemas.objects import Log as PrefectLog
from prefect.types import DateTime

from infrahub.core.constants import TaskConclusion
from infrahub.graphql.queries.task import FlowRunConnectionSerializer, _build_fetch_options
from infrahub.task_manager.flow_run.models import (
    EnrichedFlowRun,
    FlowRunFetchOptions,
    FlowRunQueryResult,
    RelatedNodeInfo,
)

TIMESTAMP = DateTime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)


def make_flow_run(
    *,
    state_name: str | None = "Completed",
    state_type: StateType | None = StateType.COMPLETED,
    parameters: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    timestamp: DateTime | None = TIMESTAMP,
) -> FlowRun:
    return FlowRun(
        flow_id=uuid4(),
        name="my-run",
        state_name=state_name,
        state_type=state_type,
        parameters=parameters or {},
        tags=tags or [],
        created=timestamp,
        updated=timestamp,
        start_time=timestamp,
    )


class TestFlowRunConnectionSerializer:
    def test_empty_result_returns_count_and_no_edges(self) -> None:
        result = FlowRunQueryResult(count=0, runs=[])

        serialized = FlowRunConnectionSerializer().serialize(result=result)

        assert serialized == {"count": 0, "edges": []}

    def test_count_is_passed_through_independently_of_runs(self) -> None:
        result = FlowRunQueryResult(count=42, runs=[EnrichedFlowRun(flow_run=make_flow_run())])

        serialized = FlowRunConnectionSerializer().serialize(result=result)

        assert serialized["count"] == 42
        assert len(serialized["edges"]) == 1

    def test_fully_populated_node_is_mapped(self) -> None:
        flow = make_flow_run(parameters={"a": 1}, tags=["t1", "t2"])
        related = [RelatedNodeInfo(id="node-1", kind="TestThing"), RelatedNodeInfo(id="node-2", kind="OtherThing")]
        log = PrefectLog(name="task", level=30, message="hello", timestamp=TIMESTAMP, flow_run_id=flow.id)
        run = EnrichedFlowRun(
            flow_run=flow,
            branch="main",
            related_nodes=related,
            workflow_name="my_workflow",
            progress=0.42,
            logs=[log],
        )

        node = FlowRunConnectionSerializer().serialize(result=FlowRunQueryResult(count=1, runs=[run]))["edges"][0][
            "node"
        ]

        assert node == {
            "title": "my-run",
            "conclusion": TaskConclusion.SUCCESS.value,
            "state": StateType.COMPLETED,
            "progress": 0.42,
            "parameters": {"a": 1},
            "branch": "main",
            "tags": ["t1", "t2"],
            "workflow": "my_workflow",
            "related_node": "node-1",
            "related_node_kind": "TestThing",
            "related_nodes": [
                {"id": "node-1", "kind": "TestThing"},
                {"id": "node-2", "kind": "OtherThing"},
            ],
            "created_at": TIMESTAMP.isoformat(),
            "updated_at": TIMESTAMP.isoformat(),
            "start_time": TIMESTAMP.isoformat(),
            "id": flow.id,
            "logs": {
                "edges": [{"node": {"message": "hello", "severity": "warning", "timestamp": TIMESTAMP.isoformat()}}],
                "count": 1,
            },
        }

    def test_unknown_state_name_falls_back_to_unknown_conclusion(self) -> None:
        run = EnrichedFlowRun(flow_run=make_flow_run(state_name="Surprise"))

        node = FlowRunConnectionSerializer().serialize(result=FlowRunQueryResult(count=1, runs=[run]))["edges"][0][
            "node"
        ]

        assert node["conclusion"] == TaskConclusion.UNKNOWN.value

    def test_unknown_log_level_falls_back_to_error_severity(self) -> None:
        flow = make_flow_run()
        log = PrefectLog(name="task", level=99, message="weird", timestamp=TIMESTAMP, flow_run_id=flow.id)
        run = EnrichedFlowRun(flow_run=flow, logs=[log])

        node = FlowRunConnectionSerializer().serialize(result=FlowRunQueryResult(count=1, runs=[run]))["edges"][0][
            "node"
        ]

        assert node["logs"]["edges"][0]["node"]["severity"] == "error"

    def test_missing_optionals_serialize_to_none(self) -> None:
        flow = make_flow_run(state_name=None, state_type=None, timestamp=None)
        run = EnrichedFlowRun(flow_run=flow)

        node = FlowRunConnectionSerializer().serialize(result=FlowRunQueryResult(count=1, runs=[run]))["edges"][0][
            "node"
        ]

        assert node["conclusion"] == TaskConclusion.UNKNOWN.value
        assert node["related_node"] is None
        assert node["related_node_kind"] is None
        assert node["related_nodes"] == []
        assert node["created_at"] is None
        assert node["updated_at"] is None
        assert node["start_time"] is None
        assert node["logs"] == {"edges": [], "count": 0}


@dataclass
class FetchOptionsCase:
    name: str
    fields: dict[str, Any]
    expected: FlowRunFetchOptions = field(default_factory=FlowRunFetchOptions)


FETCH_OPTIONS_CASES = [
    FetchOptionsCase(
        name="count_only",
        fields={"count": {}},
        expected=FlowRunFetchOptions(include_count=True),
    ),
    FetchOptionsCase(
        name="node_fields_enable_runs",
        fields={"edges": {"node": {"title": {}}}},
        expected=FlowRunFetchOptions(include_runs=True),
    ),
    FetchOptionsCase(
        name="logs_enable_logs_and_runs",
        fields={"edges": {"node": {"logs": {"edges": {"node": {"message": {}}}}}}},
        expected=FlowRunFetchOptions(include_runs=True, include_logs=True),
    ),
    FetchOptionsCase(
        name="progress_enables_progress",
        fields={"edges": {"node": {"progress": {}}}},
        expected=FlowRunFetchOptions(include_runs=True, include_progress=True),
    ),
    FetchOptionsCase(
        name="related_node_enables_related_nodes",
        fields={"edges": {"node": {"related_node": {}}}},
        expected=FlowRunFetchOptions(include_runs=True, include_related_nodes=True),
    ),
    FetchOptionsCase(
        name="related_node_kind_enables_related_nodes",
        fields={"edges": {"node": {"related_node_kind": {}}}},
        expected=FlowRunFetchOptions(include_runs=True, include_related_nodes=True),
    ),
    FetchOptionsCase(
        name="related_nodes_enables_related_nodes",
        fields={"edges": {"node": {"related_nodes": {}}}},
        expected=FlowRunFetchOptions(include_runs=True, include_related_nodes=True),
    ),
    FetchOptionsCase(
        name="workflow_enables_workflow",
        fields={"edges": {"node": {"workflow": {}}}},
        expected=FlowRunFetchOptions(include_runs=True, include_workflow=True),
    ),
    FetchOptionsCase(
        name="empty_selection_enables_nothing",
        fields={},
        expected=FlowRunFetchOptions(),
    ),
]


class TestBuildFetchOptions:
    @pytest.mark.parametrize("case", FETCH_OPTIONS_CASES, ids=[c.name for c in FETCH_OPTIONS_CASES])
    def test_field_selection_maps_to_fetch_options(self, case: FetchOptionsCase) -> None:
        assert _build_fetch_options(fields=case.fields, log_limit=None, log_offset=None) == case.expected

    def test_log_limit_and_offset_are_passed_through(self) -> None:
        options = _build_fetch_options(fields={}, log_limit=50, log_offset=10)

        assert options.log_limit == 50
        assert options.log_offset == 10
