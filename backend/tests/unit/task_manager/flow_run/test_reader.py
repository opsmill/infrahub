from datetime import UTC, timedelta
from uuid import UUID, uuid4

import pytest
from prefect.client.schemas.filters import ArtifactFilter, FlowFilter, FlowRunFilter, LogFilter
from prefect.client.schemas.objects import Artifact, Flow, FlowRun, Log
from prefect.client.schemas.sorting import FlowRunSort
from prefect.types import DateTime

from infrahub.task_manager.flow_run.constants import WEBHOOK_HTTP_ARTIFACT_KEY
from infrahub.task_manager.flow_run.reader import NB_LOGS_LIMIT, PREFECT_MAX_LOGS_PER_CALL, FlowRunReader


class FakeReaderClient:
    def __init__(
        self,
        logs: list[Log] | None = None,
        artifacts: list[Artifact] | None = None,
        flows: list[Flow] | None = None,
    ) -> None:
        self._logs = logs or []
        self._artifacts = artifacts or []
        self._flows = flows or []
        self._log_fetches: list[tuple[int, int]] = []
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
        return []

    async def read_logs(self, log_filter: LogFilter, offset: int, limit: int) -> list[Log]:
        self._log_fetches.append((offset, limit))
        return self._logs[offset : offset + limit]

    def assert_log_pages_fetched(self, pages: list[tuple[int, int]]) -> None:
        """Assert read_logs was invoked once per (offset, limit) page, in order."""
        assert self._log_fetches == pages

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


def make_http_artifact(flow_run_id: UUID, data: object, created: DateTime | None = None) -> Artifact:
    return Artifact(key=WEBHOOK_HTTP_ARTIFACT_KEY, type="result", flow_run_id=flow_run_id, data=data, created=created)


SAMPLE_CAPTURE = {
    "request": {"url": "http://target/hook", "headers": {"webhook-signature": "***"}},
    "response": {"status_code": 200, "body": "{}", "latency_ms": 4.0},
    "error": None,
}


class TestReadLogs:
    async def test_groups_logs_by_flow_run(self) -> None:
        flow_a, flow_b = uuid4(), uuid4()
        client = FakeReaderClient(logs=[make_log(flow_a), make_log(flow_a), make_log(flow_b)])

        result = await FlowRunReader(client=client).read_logs(
            flow_ids=[flow_a, flow_b], log_limit=None, log_offset=None
        )

        assert len(result.logs[flow_a]) == 2
        assert len(result.logs[flow_b]) == 1

    async def test_paginates_beyond_a_single_batch(self) -> None:
        flow_id = uuid4()
        total = PREFECT_MAX_LOGS_PER_CALL + 50
        client = FakeReaderClient(logs=[make_log(flow_id) for _ in range(total)])

        result = await FlowRunReader(client=client).read_logs(flow_ids=[flow_id], log_limit=None, log_offset=None)

        assert len(result.logs[flow_id]) == total
        client.assert_log_pages_fetched(
            [(0, PREFECT_MAX_LOGS_PER_CALL), (PREFECT_MAX_LOGS_PER_CALL, PREFECT_MAX_LOGS_PER_CALL)]
        )

    async def test_excludes_completed_finished_message(self) -> None:
        flow_id = uuid4()
        client = FakeReaderClient(
            logs=[make_log(flow_id, message="real work"), make_log(flow_id, message="Finished in state Completed()")]
        )

        result = await FlowRunReader(client=client).read_logs(flow_ids=[flow_id], log_limit=None, log_offset=None)

        assert [entry.message for entry in result.logs[flow_id]] == ["real work"]

    async def test_no_flow_ids_returns_empty_without_remote_call(self) -> None:
        client = FakeReaderClient(logs=[make_log(uuid4())])

        result = await FlowRunReader(client=client).read_logs(flow_ids=[], log_limit=None, log_offset=None)

        assert result.logs == {}
        client.assert_log_pages_fetched([])

    async def test_rejects_log_limit_above_max(self) -> None:
        with pytest.raises(ValueError, match=rf"^log_limit cannot be greater than {NB_LOGS_LIMIT}$"):
            await FlowRunReader(client=FakeReaderClient()).read_logs(
                flow_ids=[uuid4()], log_limit=NB_LOGS_LIMIT + 1, log_offset=None
            )


class TestReadProgress:
    async def test_maps_flow_run_to_progress(self) -> None:
        flow_a, flow_b = uuid4(), uuid4()
        client = FakeReaderClient(artifacts=[make_artifact(flow_a, 0.25), make_artifact(flow_b, 1.0)])

        result = await FlowRunReader(client=client).read_progress(flow_ids=[flow_a, flow_b])

        assert result.data == {flow_a: 0.25, flow_b: 1.0}

    async def test_keeps_first_artifact_on_duplicate(self) -> None:
        flow_id = uuid4()
        client = FakeReaderClient(artifacts=[make_artifact(flow_id, 0.1), make_artifact(flow_id, 0.9)])

        result = await FlowRunReader(client=client).read_progress(flow_ids=[flow_id])

        assert result.data == {flow_id: 0.1}

    async def test_ignores_non_float_data(self) -> None:
        flow_id = uuid4()
        client = FakeReaderClient(artifacts=[make_artifact(flow_id, "not-a-number")])

        result = await FlowRunReader(client=client).read_progress(flow_ids=[flow_id])

        assert result.data == {}

    async def test_no_flow_ids_returns_empty_without_remote_call(self) -> None:
        client = FakeReaderClient(artifacts=[make_artifact(uuid4(), 0.5)])

        result = await FlowRunReader(client=client).read_progress(flow_ids=[])

        assert result.data == {}
        assert client.read_artifacts_calls == []


class TestReadHttp:
    async def test_maps_flow_run_to_capture(self) -> None:
        flow_id = uuid4()
        client = FakeReaderClient(artifacts=[make_http_artifact(flow_id, SAMPLE_CAPTURE)])

        result = await FlowRunReader(client=client).read_http(flow_ids=[flow_id])

        assert result.data == {flow_id: SAMPLE_CAPTURE}

    async def test_ignores_non_dict_data(self) -> None:
        flow_id = uuid4()
        client = FakeReaderClient(artifacts=[make_http_artifact(flow_id, "not-a-capture")])

        result = await FlowRunReader(client=client).read_http(flow_ids=[flow_id])

        assert result.data == {}

    async def test_keeps_latest_capture_on_duplicate(self) -> None:
        flow_id = uuid4()
        older = make_http_artifact(flow_id, {"attempt": 1}, created=DateTime.now(tz=UTC))
        newer = make_http_artifact(flow_id, {"attempt": 2}, created=DateTime.now(tz=UTC) + timedelta(seconds=120))
        client = FakeReaderClient(artifacts=[newer, older])

        result = await FlowRunReader(client=client).read_http(flow_ids=[flow_id])

        assert result.data == {flow_id: {"attempt": 2}}

    async def test_no_flow_ids_returns_empty_without_remote_call(self) -> None:
        client = FakeReaderClient(artifacts=[make_http_artifact(uuid4(), SAMPLE_CAPTURE)])

        result = await FlowRunReader(client=client).read_http(flow_ids=[])

        assert result.data == {}
        assert client.read_artifacts_calls == []


class TestReadFlows:
    async def test_reads_all_when_no_ids_or_names(self) -> None:
        flows = [Flow(id=uuid4(), name="wf", labels={})]
        client = FakeReaderClient(flows=flows)

        result = await FlowRunReader(client=client).read_flows()

        assert result == flows
        assert client.read_flows_calls == [None]

    async def test_empty_ids_return_no_flows_without_remote_call(self) -> None:
        client = FakeReaderClient(flows=[Flow(id=uuid4(), name="wf", labels={})])

        result = await FlowRunReader(client=client).read_flows(ids=[])

        assert result == []
        assert client.read_flows_calls == []

    async def test_empty_names_return_no_flows_without_remote_call(self) -> None:
        client = FakeReaderClient(flows=[Flow(id=uuid4(), name="wf", labels={})])

        result = await FlowRunReader(client=client).read_flows(names=[])

        assert result == []
        assert client.read_flows_calls == []

    async def test_filters_by_names(self) -> None:
        client = FakeReaderClient()

        await FlowRunReader(client=client).read_flows(names=["wf_a", "wf_b"])

        flow_filter = client.read_flows_calls[0]
        assert flow_filter is not None
        assert flow_filter.name is not None
        assert flow_filter.name.any_ == ["wf_a", "wf_b"]
        assert flow_filter.id is None

    async def test_filters_by_ids(self) -> None:
        ids = [uuid4()]
        client = FakeReaderClient()

        await FlowRunReader(client=client).read_flows(ids=ids)

        flow_filter = client.read_flows_calls[0]
        assert flow_filter is not None
        assert flow_filter.id is not None
        assert flow_filter.id.any_ == ids
