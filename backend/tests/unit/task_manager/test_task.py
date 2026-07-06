from datetime import UTC
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from prefect.client.schemas.filters import ArtifactFilter, FlowFilter, FlowRunFilter, LogFilter
from prefect.client.schemas.objects import Artifact, Flow, FlowRun, Log
from prefect.client.schemas.sorting import FlowRunSort
from prefect.types import DateTime

from infrahub.exceptions import ValidationError
from infrahub.task_manager.task import NB_LOGS_LIMIT, PREFECT_MAX_LOGS_PER_CALL, PrefectTask

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient


class FakePrefectClient:
    """Minimal Prefect client stand-in that records the read calls PrefectTask makes."""

    def __init__(
        self,
        logs: list[Log] | None = None,
        artifacts: list[Artifact] | None = None,
        flows: list[Flow] | None = None,
        flow_runs: list[FlowRun] | None = None,
    ) -> None:
        self._logs = logs or []
        self._artifacts = artifacts or []
        self._flows = flows or []
        self._flow_runs = flow_runs or []
        self.read_logs_calls: list[tuple[int, int]] = []
        self.read_artifacts_calls: list[FlowRunFilter] = []
        self.read_flows_calls: list[FlowFilter | None] = []

    async def read_flow_runs(
        self,
        flow_filter: FlowFilter | None = None,
        flow_run_filter: FlowRunFilter | None = None,
        limit: int | None = None,
        offset: int = 0,
        sort: FlowRunSort | None = None,
    ) -> list[FlowRun]:
        return self._flow_runs

    async def read_logs(self, log_filter: LogFilter, offset: int, limit: int) -> list[Log]:
        self.read_logs_calls.append((offset, limit))
        return self._logs[offset : offset + limit]

    async def read_artifacts(self, artifact_filter: ArtifactFilter, flow_run_filter: FlowRunFilter) -> list[Artifact]:
        self.read_artifacts_calls.append(flow_run_filter)
        return self._artifacts

    async def read_flows(self, flow_filter: FlowFilter | None = None) -> list[Flow]:
        self.read_flows_calls.append(flow_filter)
        return self._flows


def make_log(flow_run_id: UUID | None, message: str = "log line") -> Log:
    return Log(name="task", level=20, message=message, timestamp=DateTime.now(tz=UTC), flow_run_id=flow_run_id)


def make_artifact(flow_run_id: UUID, data: object) -> Artifact:
    return Artifact(type="progress", flow_run_id=flow_run_id, data=data)


class TestQueryLogSelection:
    async def test_logs_count_alone_fetches_logs(self) -> None:
        """A `logs { count }` selection without edges still triggers the log fetch."""
        client = FakePrefectClient(flow_runs=[FlowRun(id=uuid4(), flow_id=uuid4(), name="r1")])
        fields: dict[str, Any] = {"edges": {"node": {"logs": {"count": {}}}}}

        with patch("infrahub.task_manager.task.get_client") as mock_get_client:
            mock_get_client.return_value.__aenter__.return_value = client
            mock_get_client.return_value.__aexit__.return_value = None
            await PrefectTask.query(db=MagicMock(), fields=fields)

        assert client.read_logs_calls != []


class TestGenerateFlowRunFilter:
    def test_ids_are_converted_to_uuid(self) -> None:
        id_a = "00000000-0000-0000-0000-000000000001"
        id_b = "00000000-0000-0000-0000-000000000002"

        flow_run_filter = PrefectTask._generate_flow_run_filter(ids=[id_a, id_b])

        assert flow_run_filter.id is not None
        assert flow_run_filter.id.any_ == [UUID(id_a), UUID(id_b)]

    def test_invalid_id_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError, match=r"^'not-a-uuid' is not a valid task id$"):
            PrefectTask._generate_flow_run_filter(ids=["not-a-uuid"])

    def test_null_id_raises_validation_error(self) -> None:
        # ids=List(String) in GraphQL permits null elements, which reach UUID() as None.
        with pytest.raises(ValidationError, match=r"^'None' is not a valid task id$"):
            PrefectTask._generate_flow_run_filter(ids=cast("list[str]", [None]))


class TestGetLogs:
    async def test_no_flow_ids_returns_empty_without_remote_call(self) -> None:
        client = FakePrefectClient(logs=[make_log(uuid4())])

        result = await PrefectTask._get_logs(
            client=cast("PrefectClient", client), flow_ids=[], log_limit=None, log_offset=None
        )

        assert result.logs == {}
        assert client.read_logs_calls == []

    async def test_paginates_beyond_a_single_batch(self) -> None:
        flow_id = uuid4()
        total = PREFECT_MAX_LOGS_PER_CALL + 50
        client = FakePrefectClient(logs=[make_log(flow_id) for _ in range(total)])

        result = await PrefectTask._get_logs(
            client=cast("PrefectClient", client), flow_ids=[flow_id], log_limit=None, log_offset=None
        )

        assert len(result.logs[flow_id]) == total
        assert client.read_logs_calls == [
            (0, PREFECT_MAX_LOGS_PER_CALL),
            (PREFECT_MAX_LOGS_PER_CALL, PREFECT_MAX_LOGS_PER_CALL),
        ]

    async def test_rejects_log_limit_above_max(self) -> None:
        with pytest.raises(ValueError, match=rf"^log_limit cannot be greater than {NB_LOGS_LIMIT}$"):
            await PrefectTask._get_logs(
                client=cast("PrefectClient", FakePrefectClient()),
                flow_ids=[uuid4()],
                log_limit=NB_LOGS_LIMIT + 1,
                log_offset=None,
            )


class TestGetProgress:
    async def test_no_flow_ids_returns_empty_without_remote_call(self) -> None:
        client = FakePrefectClient(artifacts=[make_artifact(uuid4(), 0.5)])

        result = await PrefectTask._get_progress(client=cast("PrefectClient", client), flow_ids=[])

        assert result.data == {}
        assert client.read_artifacts_calls == []


class TestGetFlows:
    async def test_reads_all_when_no_ids_or_names(self) -> None:
        flows = [Flow(id=uuid4(), name="wf", labels={})]
        client = FakePrefectClient(flows=flows)

        result = await PrefectTask._get_flows(client=cast("PrefectClient", client))

        assert result == flows
        assert client.read_flows_calls == [None]

    async def test_empty_ids_return_no_flows_without_remote_call(self) -> None:
        client = FakePrefectClient(flows=[Flow(id=uuid4(), name="wf", labels={})])

        result = await PrefectTask._get_flows(client=cast("PrefectClient", client), ids=[])

        assert result == []
        assert client.read_flows_calls == []

    async def test_empty_names_return_no_flows_without_remote_call(self) -> None:
        client = FakePrefectClient(flows=[Flow(id=uuid4(), name="wf", labels={})])

        result = await PrefectTask._get_flows(client=cast("PrefectClient", client), names=[])

        assert result == []
        assert client.read_flows_calls == []
