import logging
from collections.abc import Iterable
from uuid import UUID, uuid4

import pytest
from prefect.client.schemas.filters import FlowFilter, FlowRunFilter
from prefect.client.schemas.objects import TERMINAL_STATES, FlowRun
from prefect.client.schemas.sorting import FlowRunSort

from infrahub.log import get_run_logger
from infrahub.task_manager.flow_run.branch_cleanup import BranchFlowRunDetacher
from infrahub.task_manager.flow_run.filters import FlowRunFilterBuilder
from infrahub.task_manager.flow_run.prefect_client import BranchCleanupPrefectClient
from infrahub.workflows.constants import TAG_NAMESPACE

BRANCH_NAME = "feature-x"
BRANCH_ID = "18a3c0f2-6b1d-4c3e-9f7a-2d5e8b1c4a90"
LOGGER_NAME = "infrahub.tasks"

BRANCH_TAG = "infrahub.app/branch/feature-x"
DELETED_BRANCH_TAG = "infrahub.app/deleted-branch/feature-x"
DELETED_BRANCH_ID_TAG = f"infrahub.app/deleted-branch-id/{BRANCH_ID}"


def make_run(extra_tags: list[str] | None = None) -> FlowRun:
    return FlowRun(flow_id=uuid4(), name="run", tags=[TAG_NAMESPACE, BRANCH_TAG, *(extra_tags or [])])


class InMemoryDetachClient:
    """A faithful in-memory client: a run whose tags no longer hold every filtered tag drops out of the next read."""

    def __init__(self, flow_runs: list[FlowRun] | None = None) -> None:
        self.runs: list[FlowRun] = list(flow_runs or [])
        self.read_filters: list[FlowRunFilter | None] = []
        self.updated: list[UUID] = []

    async def read_flow_runs(
        self,
        flow_filter: FlowFilter | None = None,
        flow_run_filter: FlowRunFilter | None = None,
        limit: int | None = None,
        offset: int = 0,
        sort: FlowRunSort | None = None,
    ) -> list[FlowRun]:
        self.read_filters.append(flow_run_filter)
        required_tags = set(flow_run_filter.tags.all_ or []) if flow_run_filter and flow_run_filter.tags else set()
        return [run for run in self.runs if required_tags.issubset(run.tags)][:limit]

    def run_by_id(self, flow_run_id: UUID) -> FlowRun:
        return next(run for run in self.runs if run.id == flow_run_id)

    async def update_flow_run(self, flow_run_id: UUID, tags: list[str]) -> None:
        self.updated.append(flow_run_id)
        self.runs = [run.model_copy(update={"tags": tags}) if run.id == flow_run_id else run for run in self.runs]


class FailingUpdateDetachClient(InMemoryDetachClient):
    """Tag updates raise for the given ids, so those runs keep the branch tag and keep being returned."""

    def __init__(self, flow_runs: list[FlowRun], failing_ids: Iterable[UUID]) -> None:
        super().__init__(flow_runs)
        self.failing_ids = set(failing_ids)
        self.update_attempts: list[UUID] = []

    async def update_flow_run(self, flow_run_id: UUID, tags: list[str]) -> None:
        self.update_attempts.append(flow_run_id)
        if flow_run_id in self.failing_ids:
            raise RuntimeError("update boom")
        await super().update_flow_run(flow_run_id=flow_run_id, tags=tags)


class FailingReadDetachClient:
    """Every read raises, standing in for a Prefect backend that is unreachable."""

    def __init__(self) -> None:
        self.updated: list[UUID] = []

    async def read_flow_runs(
        self,
        flow_filter: FlowFilter | None = None,
        flow_run_filter: FlowRunFilter | None = None,
        limit: int | None = None,
        offset: int = 0,
        sort: FlowRunSort | None = None,
    ) -> list[FlowRun]:
        raise RuntimeError("read boom")

    async def update_flow_run(self, flow_run_id: UUID, tags: list[str]) -> None:
        self.updated.append(flow_run_id)


class PersistingTagsDetachClient(InMemoryDetachClient):
    """The tag update reports success but the tags stay, as under eventual consistency."""

    async def update_flow_run(self, flow_run_id: UUID, tags: list[str]) -> None:
        self.updated.append(flow_run_id)


class ReadFailsAfterFirstDetachClient(InMemoryDetachClient):
    """The first read (and its updates) succeed; the re-read that would confirm the detach fails."""

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


def _detacher(client: BranchCleanupPrefectClient, batch_size: int = 100) -> BranchFlowRunDetacher:
    return BranchFlowRunDetacher(
        client=client, filter_builder=FlowRunFilterBuilder(), log=get_run_logger(), batch_size=batch_size
    )


def _messages(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.name == LOGGER_NAME and record.levelno == level]


def _assert_filter_scopes_to_branch_terminal_states(flow_run_filter: FlowRunFilter | None) -> None:
    """Assert the read filter selects only the branch's runs that are in a terminal state."""
    assert flow_run_filter is not None
    assert flow_run_filter.tags is not None
    assert flow_run_filter.tags.all_ == [TAG_NAMESPACE, BRANCH_TAG]
    assert flow_run_filter.state is not None
    assert flow_run_filter.state.type is not None
    assert flow_run_filter.state.type.any_ is not None
    assert set(flow_run_filter.state.type.any_) == set(TERMINAL_STATES)


class TestBranchFlowRunDetacher:
    async def test_detaches_every_matching_run_without_deleting_it(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger=LOGGER_NAME)
        node_tag = "infrahub.app/node/abc"
        runs = [make_run(extra_tags=[node_tag]) for _ in range(3)]
        client = InMemoryDetachClient(flow_runs=runs)

        await _detacher(client).detach_for_branch(branch_name=BRANCH_NAME, branch_id=BRANCH_ID)

        assert [run.id for run in client.runs] == [run.id for run in runs]
        assert client.updated == [run.id for run in runs]
        for run in client.runs:
            assert sorted(run.tags) == sorted([TAG_NAMESPACE, node_tag, DELETED_BRANCH_TAG, DELETED_BRANCH_ID_TAG])
        assert _messages(caplog, logging.WARNING) == []
        assert _messages(caplog, logging.INFO) == ["Detached 3 flow run(s) from deleted branch 'feature-x'"]

    async def test_run_with_two_branch_tags_keeps_the_surviving_branch(self) -> None:
        surviving_tag = "infrahub.app/branch/main"
        run = make_run(extra_tags=[surviving_tag])
        client = InMemoryDetachClient(flow_runs=[run])

        await _detacher(client).detach_for_branch(branch_name=BRANCH_NAME, branch_id=BRANCH_ID)

        assert sorted(client.run_by_id(run.id).tags) == sorted(
            [TAG_NAMESPACE, surviving_tag, DELETED_BRANCH_TAG, DELETED_BRANCH_ID_TAG]
        )

    async def test_omits_the_branch_id_tag_when_no_id_is_given(self) -> None:
        run = make_run()
        client = InMemoryDetachClient(flow_runs=[run])

        await _detacher(client).detach_for_branch(branch_name=BRANCH_NAME)

        assert sorted(client.run_by_id(run.id).tags) == sorted([TAG_NAMESPACE, DELETED_BRANCH_TAG])

    async def test_omits_the_branch_id_tag_when_the_id_is_empty(self) -> None:
        run = make_run()
        client = InMemoryDetachClient(flow_runs=[run])

        await _detacher(client).detach_for_branch(branch_name=BRANCH_NAME, branch_id="")

        assert sorted(client.run_by_id(run.id).tags) == sorted([TAG_NAMESPACE, DELETED_BRANCH_TAG])

    async def test_scopes_to_the_branch_tag_and_terminal_states(self) -> None:
        client = InMemoryDetachClient(flow_runs=[make_run()])

        await _detacher(client).detach_for_branch(branch_name=BRANCH_NAME, branch_id=BRANCH_ID)

        _assert_filter_scopes_to_branch_terminal_states(client.read_filters[0])

    async def test_pages_through_multiple_batches(self) -> None:
        runs = [make_run() for _ in range(3)]
        client = InMemoryDetachClient(flow_runs=runs)

        await _detacher(client, batch_size=2).detach_for_branch(branch_name=BRANCH_NAME, branch_id=BRANCH_ID)

        assert client.updated == [run.id for run in runs]
        # Reads: batch of 2, batch of 1, then an empty read that ends the loop.
        assert len(client.read_filters) == 3

    async def test_a_failing_update_is_isolated_and_the_rest_still_detach(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.INFO, logger=LOGGER_NAME)
        runs = [make_run() for _ in range(3)]
        client = FailingUpdateDetachClient(flow_runs=runs, failing_ids=[runs[1].id])

        await _detacher(client).detach_for_branch(branch_name=BRANCH_NAME, branch_id=BRANCH_ID)

        assert client.updated == [runs[0].id, runs[2].id]
        assert sorted(client.run_by_id(runs[1].id).tags) == sorted([TAG_NAMESPACE, BRANCH_TAG])
        # The stuck run is retried once on the next read, then the no-progress guard stops the loop.
        failure = f"Failed to detach flow run {runs[1].id} from deleted branch 'feature-x': update boom"
        assert _messages(caplog, logging.WARNING) == [
            failure,
            failure,
            "Stopped detaching flow runs from deleted branch 'feature-x': 1 run(s) kept the branch tag",
        ]
        assert _messages(caplog, logging.INFO) == ["Detached 2 flow run(s) from deleted branch 'feature-x'"]

    async def test_never_loops_forever_when_no_run_can_be_updated(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger=LOGGER_NAME)
        runs = [make_run() for _ in range(2)]
        client = FailingUpdateDetachClient(flow_runs=runs, failing_ids=[run.id for run in runs])

        await _detacher(client).detach_for_branch(branch_name=BRANCH_NAME, branch_id=BRANCH_ID)

        # Nothing left the branch filter, so the batch made no progress and the loop stopped after one pass.
        assert client.updated == []
        assert client.update_attempts == [run.id for run in runs]
        assert _messages(caplog, logging.WARNING) == [
            f"Failed to detach flow run {runs[0].id} from deleted branch 'feature-x': update boom",
            f"Failed to detach flow run {runs[1].id} from deleted branch 'feature-x': update boom",
            "Stopped detaching flow runs from deleted branch 'feature-x': 2 run(s) kept the branch tag",
        ]
        assert _messages(caplog, logging.INFO) == ["Detached 0 flow run(s) from deleted branch 'feature-x'"]

    async def test_stops_when_updates_report_success_but_tags_persist(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger=LOGGER_NAME)
        runs = [make_run() for _ in range(2)]
        client = PersistingTagsDetachClient(flow_runs=runs)

        await _detacher(client).detach_for_branch(branch_name=BRANCH_NAME, branch_id=BRANCH_ID)

        # The runs never leave the branch filter, so the loop stops instead of updating them forever, and
        # the count reflects that nothing was actually detached.
        assert client.updated == [run.id for run in runs]
        assert len(client.read_filters) == 2
        assert _messages(caplog, logging.WARNING) == [
            "Stopped detaching flow runs from deleted branch 'feature-x': 2 run(s) kept the branch tag"
        ]
        assert _messages(caplog, logging.INFO) == ["Detached 0 flow run(s) from deleted branch 'feature-x'"]

    async def test_counts_detaches_when_the_confirming_read_fails(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger=LOGGER_NAME)
        runs = [make_run() for _ in range(2)]
        client = ReadFailsAfterFirstDetachClient(flow_runs=runs)

        await _detacher(client).detach_for_branch(branch_name=BRANCH_NAME, branch_id=BRANCH_ID)

        # Both updates succeeded before the confirming re-read failed, so they are still counted.
        assert client.updated == [run.id for run in runs]
        assert _messages(caplog, logging.WARNING) == [
            "Failed to read flow runs for deleted branch 'feature-x': read boom"
        ]
        assert _messages(caplog, logging.INFO) == ["Detached 2 flow run(s) from deleted branch 'feature-x'"]

    async def test_a_read_failure_does_not_propagate(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger=LOGGER_NAME)
        client = FailingReadDetachClient()

        await _detacher(client).detach_for_branch(branch_name=BRANCH_NAME, branch_id=BRANCH_ID)

        assert client.updated == []
        assert _messages(caplog, logging.WARNING) == [
            "Failed to read flow runs for deleted branch 'feature-x': read boom"
        ]
        assert _messages(caplog, logging.INFO) == []
