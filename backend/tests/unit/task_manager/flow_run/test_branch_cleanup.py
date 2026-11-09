import logging
from collections.abc import Iterable
from uuid import UUID, uuid4

import pytest
from prefect import State
from prefect.client.schemas.filters import FlowFilter, FlowRunFilter
from prefect.client.schemas.objects import TERMINAL_STATES, FlowRun, StateType
from prefect.client.schemas.sorting import FlowRunSort

from infrahub.log import get_run_logger
from infrahub.task_manager.flow_run.branch_cleanup import BranchFlowRunPurger
from infrahub.task_manager.flow_run.filters import FlowRunFilterBuilder
from infrahub.task_manager.flow_run.prefect_client import RetentionPrefectClient
from infrahub.workflows.constants import TAG_NAMESPACE, WorkflowTag

BRANCH_NAME = "feature-x"
LOGGER_NAME = "infrahub.tasks"


def make_run() -> FlowRun:
    return FlowRun(flow_id=uuid4(), name="run")


class InMemoryPurgeClient:
    """A faithful in-memory client: a deleted run no longer matches the filter on the next read."""

    def __init__(self, flow_runs: list[FlowRun] | None = None) -> None:
        self.runs: list[FlowRun] = list(flow_runs or [])
        self.read_filters: list[FlowRunFilter | None] = []
        self.deleted: list[UUID] = []

    async def read_flow_runs(
        self,
        flow_filter: FlowFilter | None = None,
        flow_run_filter: FlowRunFilter | None = None,
        limit: int | None = None,
        offset: int = 0,
        sort: FlowRunSort | None = None,
    ) -> list[FlowRun]:
        self.read_filters.append(flow_run_filter)
        return self.runs[:limit]

    async def delete_flow_run(self, flow_run_id: UUID) -> None:
        self.deleted.append(flow_run_id)
        self.runs = [run for run in self.runs if run.id != flow_run_id]

    async def set_flow_run_state(self, flow_run_id: UUID, state: State, force: bool) -> StateType | None:
        raise NotImplementedError


class FailingDeletePurgeClient(InMemoryPurgeClient):
    """Deletes raise for the given ids, so those runs stay in the store and keep being returned."""

    def __init__(self, flow_runs: list[FlowRun], failing_ids: Iterable[UUID]) -> None:
        super().__init__(flow_runs)
        self.failing_ids = set(failing_ids)
        self.delete_attempts: list[UUID] = []

    async def delete_flow_run(self, flow_run_id: UUID) -> None:
        self.delete_attempts.append(flow_run_id)
        if flow_run_id in self.failing_ids:
            raise RuntimeError("delete boom")
        self.deleted.append(flow_run_id)
        self.runs = [run for run in self.runs if run.id != flow_run_id]


class FailingReadPurgeClient:
    """Every read raises, standing in for a Prefect backend that is unreachable."""

    def __init__(self) -> None:
        self.deleted: list[UUID] = []

    async def read_flow_runs(
        self,
        flow_filter: FlowFilter | None = None,
        flow_run_filter: FlowRunFilter | None = None,
        limit: int | None = None,
        offset: int = 0,
        sort: FlowRunSort | None = None,
    ) -> list[FlowRun]:
        raise RuntimeError("read boom")

    async def delete_flow_run(self, flow_run_id: UUID) -> None:
        self.deleted.append(flow_run_id)

    async def set_flow_run_state(self, flow_run_id: UUID, state: State, force: bool) -> StateType | None:
        raise NotImplementedError


class PersistingDeletePurgeClient(InMemoryPurgeClient):
    """delete_flow_run reports success but the run stays, as under eventual consistency."""

    async def delete_flow_run(self, flow_run_id: UUID) -> None:
        self.deleted.append(flow_run_id)


class ReadFailsAfterFirstPurgeClient(InMemoryPurgeClient):
    """The first read (and its deletes) succeed; the re-read that would confirm the removals fails."""

    def __init__(self, flow_runs: list[FlowRun]) -> None:
        super().__init__(flow_runs)
        self._reads = 0

    async def read_flow_runs(
        self,
        flow_filter: FlowFilter | None = None,
        flow_run_filter: FlowRunFilter | None = None,
        limit: int | None = None,
        offset: int = 0,
        sort: FlowRunSort | None = None,
    ) -> list[FlowRun]:
        self._reads += 1
        if self._reads >= 2:
            raise RuntimeError("read boom")
        return await super().read_flow_runs(flow_run_filter=flow_run_filter, limit=limit)


def _purger(client: RetentionPrefectClient, batch_size: int = 100) -> BranchFlowRunPurger:
    return BranchFlowRunPurger(
        client=client, filter_builder=FlowRunFilterBuilder(), log=get_run_logger(), batch_size=batch_size
    )


def _messages(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.name == LOGGER_NAME and record.levelno == level]


def _assert_filter_scopes_to_branch_terminal_states(flow_run_filter: FlowRunFilter | None, *, branch_name: str) -> None:
    """Assert the read filter selects only the given branch's runs that are in a terminal state."""
    assert flow_run_filter is not None
    assert flow_run_filter.tags is not None
    assert flow_run_filter.tags.all_ == [TAG_NAMESPACE, WorkflowTag.BRANCH.render(identifier=branch_name)]
    assert flow_run_filter.state is not None
    assert flow_run_filter.state.type is not None
    assert flow_run_filter.state.type.any_ is not None
    assert set(flow_run_filter.state.type.any_) == set(TERMINAL_STATES)


class TestBranchFlowRunPurger:
    async def test_purges_every_matching_run(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger=LOGGER_NAME)
        runs = [make_run() for _ in range(3)]
        client = InMemoryPurgeClient(flow_runs=runs)

        await _purger(client).purge_for_branch(branch_name=BRANCH_NAME)

        assert client.deleted == [run.id for run in runs]
        assert client.runs == []
        assert _messages(caplog, logging.WARNING) == []
        assert _messages(caplog, logging.INFO) == ["Purged 3 flow run(s) for deleted branch 'feature-x'"]

    async def test_scopes_to_the_branch_tag_and_terminal_states(self) -> None:
        client = InMemoryPurgeClient(flow_runs=[make_run()])

        await _purger(client).purge_for_branch(branch_name=BRANCH_NAME)

        _assert_filter_scopes_to_branch_terminal_states(client.read_filters[0], branch_name=BRANCH_NAME)

    async def test_pages_through_multiple_batches(self) -> None:
        runs = [make_run() for _ in range(3)]
        client = InMemoryPurgeClient(flow_runs=runs)

        await _purger(client, batch_size=2).purge_for_branch(branch_name=BRANCH_NAME)

        assert client.deleted == [run.id for run in runs]
        # Reads: batch of 2, batch of 1, then an empty read that ends the loop.
        assert len(client.read_filters) == 3

    async def test_a_failing_delete_is_isolated_and_the_rest_still_purge(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.INFO, logger=LOGGER_NAME)
        runs = [make_run() for _ in range(3)]
        client = FailingDeletePurgeClient(flow_runs=runs, failing_ids=[runs[1].id])

        await _purger(client).purge_for_branch(branch_name=BRANCH_NAME)

        assert client.deleted == [runs[0].id, runs[2].id]
        assert runs[1].id not in client.deleted
        # The stuck run is retried once on the next read, then the no-progress guard stops the loop.
        failure = f"Failed to delete flow run {runs[1].id} for deleted branch 'feature-x': delete boom"
        assert _messages(caplog, logging.WARNING) == [
            failure,
            failure,
            "Stopped purging flow runs for deleted branch 'feature-x': 1 run(s) could not be removed",
        ]
        assert _messages(caplog, logging.INFO) == ["Purged 2 flow run(s) for deleted branch 'feature-x'"]

    async def test_never_loops_forever_when_no_run_can_be_deleted(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger=LOGGER_NAME)
        runs = [make_run() for _ in range(2)]
        client = FailingDeletePurgeClient(flow_runs=runs, failing_ids=[run.id for run in runs])

        await _purger(client).purge_for_branch(branch_name=BRANCH_NAME)

        # Nothing left the store, so the batch made no progress and the loop stopped after one pass.
        assert client.deleted == []
        assert client.delete_attempts == [run.id for run in runs]
        assert _messages(caplog, logging.WARNING) == [
            f"Failed to delete flow run {runs[0].id} for deleted branch 'feature-x': delete boom",
            f"Failed to delete flow run {runs[1].id} for deleted branch 'feature-x': delete boom",
            "Stopped purging flow runs for deleted branch 'feature-x': 2 run(s) could not be removed",
        ]
        assert _messages(caplog, logging.INFO) == ["Purged 0 flow run(s) for deleted branch 'feature-x'"]

    async def test_stops_when_deletes_report_success_but_runs_persist(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger=LOGGER_NAME)
        runs = [make_run() for _ in range(2)]
        client = PersistingDeletePurgeClient(flow_runs=runs)

        await _purger(client).purge_for_branch(branch_name=BRANCH_NAME)

        # The runs never leave the store, so the loop stops instead of deleting them forever, and the
        # count reflects that nothing was actually removed.
        assert client.deleted == [run.id for run in runs]
        assert len(client.read_filters) == 2
        assert _messages(caplog, logging.WARNING) == [
            "Stopped purging flow runs for deleted branch 'feature-x': 2 run(s) could not be removed"
        ]
        assert _messages(caplog, logging.INFO) == ["Purged 0 flow run(s) for deleted branch 'feature-x'"]

    async def test_counts_removals_when_the_confirming_read_fails(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger=LOGGER_NAME)
        runs = [make_run() for _ in range(2)]
        client = ReadFailsAfterFirstPurgeClient(flow_runs=runs)

        await _purger(client).purge_for_branch(branch_name=BRANCH_NAME)

        # Both deletes succeeded before the confirming re-read failed, so they are still counted.
        assert client.deleted == [run.id for run in runs]
        assert _messages(caplog, logging.WARNING) == [
            "Failed to read flow runs for deleted branch 'feature-x': read boom"
        ]
        assert _messages(caplog, logging.INFO) == ["Purged 2 flow run(s) for deleted branch 'feature-x'"]

    async def test_a_read_failure_does_not_propagate(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger=LOGGER_NAME)
        client = FailingReadPurgeClient()

        await _purger(client).purge_for_branch(branch_name=BRANCH_NAME)

        assert client.deleted == []
        assert _messages(caplog, logging.WARNING) == [
            "Failed to read flow runs for deleted branch 'feature-x': read boom"
        ]
        assert _messages(caplog, logging.INFO) == []
