from uuid import UUID, uuid4

from prefect import State
from prefect.client.schemas.filters import FlowRunFilter
from prefect.client.schemas.objects import FlowRun, StateType

from infrahub.task_manager.flow_run.retention import FlowRunRetention


def make_run() -> FlowRun:
    return FlowRun(flow_id=uuid4(), name="run")


class InMemoryRetentionClient:
    """A faithful in-memory retention client: deletes and state changes remove runs from the store.

    A flow run that is deleted, or whose state is forced out of the queried set, no longer matches
    the filter on the next read - mirroring how the real Prefect backend pages through results.
    """

    def __init__(self, flow_runs: list[FlowRun] | None = None) -> None:
        self.runs: list[FlowRun] = list(flow_runs or [])
        self.read_calls: list[int] = []
        self.deleted: list[UUID] = []
        self.state_changes: list[tuple[UUID, State, bool]] = []

    async def read_flow_runs(self, flow_run_filter: FlowRunFilter, limit: int) -> list[FlowRun]:
        self.read_calls.append(limit)
        return self.runs[:limit]

    async def delete_flow_run(self, flow_run_id: UUID) -> None:
        self.deleted.append(flow_run_id)
        self.runs = [run for run in self.runs if run.id != flow_run_id]

    async def set_flow_run_state(self, flow_run_id: UUID, state: State, force: bool) -> None:
        self.state_changes.append((flow_run_id, state, force))
        self.runs = [run for run in self.runs if run.id != flow_run_id]


class StuckRetentionClient:
    """A client whose runs never leave the store, so successive reads keep returning the same ids."""

    def __init__(self, flow_runs: list[FlowRun]) -> None:
        self.runs = list(flow_runs)
        self.deleted: list[UUID] = []

    async def read_flow_runs(self, flow_run_filter: FlowRunFilter, limit: int) -> list[FlowRun]:
        return self.runs[:limit]

    async def delete_flow_run(self, flow_run_id: UUID) -> None:
        self.deleted.append(flow_run_id)

    async def set_flow_run_state(self, flow_run_id: UUID, state: State, force: bool) -> None:
        raise NotImplementedError


class TestFlowRunRetention:
    async def test_delete_removes_every_matching_run(self) -> None:
        runs = [make_run() for _ in range(3)]
        client = InMemoryRetentionClient(flow_runs=runs)

        await FlowRunRetention(client=client).purge(batch_size=100)

        assert client.deleted == [run.id for run in runs]
        assert client.state_changes == []
        assert client.runs == []

    async def test_without_delete_forces_crashed_state(self) -> None:
        runs = [make_run() for _ in range(3)]
        client = InMemoryRetentionClient(flow_runs=runs)

        await FlowRunRetention(client=client).purge(states=[StateType.RUNNING], delete=False, batch_size=100)

        assert client.deleted == []
        assert [flow_run_id for flow_run_id, _, _ in client.state_changes] == [run.id for run in runs]
        assert all(state.type == StateType.CRASHED for _, state, _ in client.state_changes)
        assert all(force is True for _, _, force in client.state_changes)
        assert client.runs == []

    async def test_pages_through_multiple_batches(self) -> None:
        runs = [make_run() for _ in range(3)]
        client = InMemoryRetentionClient(flow_runs=runs)

        await FlowRunRetention(client=client).purge(batch_size=2)

        assert client.deleted == [run.id for run in runs]
        # Reads: batch of 2, batch of 1, then an empty read that ends the loop.
        assert len(client.read_calls) == 3

    async def test_aborts_when_the_same_runs_keep_returning(self) -> None:
        runs = [make_run() for _ in range(2)]
        client = StuckRetentionClient(flow_runs=runs)

        await FlowRunRetention(client=client).purge(batch_size=100)

        # Each run is handled exactly once: the loop detects the repeat read and stops.
        assert client.deleted == [run.id for run in runs]
