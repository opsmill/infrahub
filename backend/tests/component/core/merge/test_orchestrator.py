from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from infrahub import config
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.changelog.models import NodeChangelog
from infrahub.core.constants import DiffAction
from infrahub.core.diff.ipam_diff_parser import IpamDiffParser
from infrahub.core.diff.model.path import BranchTrackingId, EnrichedDiffRoot
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.diff.summary_cache import DiffSummaryCache
from infrahub.core.diff.summary_serializer import DiffSummarySerializer
from infrahub.core.initialization import create_branch
from infrahub.core.merge.graph_merger import GraphMerger
from infrahub.core.merge.orchestrator import BranchMergeOrchestrator
from infrahub.core.merge.post_merge import PostMergeDispatcher
from infrahub.core.merge.rollback_handler import MergeRollbackHandler, PreMergeState
from infrahub.core.merge.schema_analyzer import MergeSchemaAnalyzer
from infrahub.core.merge.write_blocker import MergeProtection, MergeProtectionState, MergeWriteBlocker
from infrahub.core.registry import registry
from infrahub.core.rollback import GraphRollbacker
from infrahub.core.schema.update_coordinator import SchemaUpdateCoordinator
from infrahub.core.timestamp import Timestamp
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from tests.adapters.cache import MemoryCache

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

    from infrahub.core.branch import Branch
    from infrahub.core.diff.model.path import TrackingId
    from infrahub.core.diff.query.filters import EnrichedDiffQueryFilters
    from infrahub.core.ipam.model import IpamNodeDetails
    from infrahub.core.models import SchemaDiff
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


class _ProbingGraphMerger(GraphMerger):
    """Graph merger that writes nothing and records the write protection in force while it runs."""

    def __init__(self, merge_write_blocker: MergeWriteBlocker) -> None:
        self._merge_write_blocker = merge_write_blocker
        self.protection_during_merge: MergeProtection | None = None

    async def merge(self, at: Timestamp, user_id: str = "") -> None:
        self.protection_during_merge = await self._merge_write_blocker.get()


class _NoSchemaChangeAnalyzer(MergeSchemaAnalyzer):
    def __init__(self) -> None:
        pass

    async def has_schema_changes(self) -> bool:
        return False


class _StaticDiffRepository(DiffRepository):
    """Serves one prebuilt diff and treats the post-merge diff bookkeeping as done."""

    def __init__(self, diff: EnrichedDiffRoot) -> None:
        self._diff = diff

    async def get_one(
        self,
        diff_branch_name: str,
        tracking_id: TrackingId | None = None,
        diff_id: str | None = None,
        filters: EnrichedDiffQueryFilters | None = None,
        include_parents: bool = True,
    ) -> EnrichedDiffRoot:
        return self._diff

    async def mark_tracking_ids_merged(self, tracking_ids: list[TrackingId]) -> None:
        pass

    async def freeze_diffs_for_branch(self, branch_name: str) -> None:
        pass


class _EmptyIpamDiffParser(IpamDiffParser):
    def __init__(self) -> None:
        pass

    async def get_changed_ipam_node_details(
        self, source_branch_name: str, target_branch_name: str
    ) -> list[IpamNodeDetails]:
        return []


class _RecordingRollbackHandler(MergeRollbackHandler):
    def __init__(self) -> None:
        self.calls = 0

    async def rollback(self, *, merge_started_at: Timestamp, pre_merge_state: PreMergeState, user_id: str) -> bool:
        self.calls += 1
        return True


class _RecordingPostMergeDispatcher(PostMergeDispatcher):
    def __init__(self, steps: list[str]) -> None:
        self._steps = steps
        self.dispatched_node_events: list[Sequence[tuple[DiffAction, NodeChangelog]]] = []

    async def run_follow_ups(
        self,
        *,
        branch: Branch,
        context: InfrahubContext,
        proposed_change_id: str | None,
        ipam_node_details: list[IpamNodeDetails] | None,
        merge_diff_cache_key: str | None = None,
    ) -> None:
        self._steps.append("follow_ups")

    async def dispatch_events(
        self,
        *,
        branch: Branch,
        proposed_change_id: str | None,
        node_events: Sequence[tuple[DiffAction, NodeChangelog]],
        context: InfrahubContext,
        schema_diff: SchemaDiff | None = None,
        schema_hash: str | None = None,
    ) -> None:
        self._steps.append("dispatch_events")
        self.dispatched_node_events.append(node_events)


class _ProbingChangelogCollector:
    """Collector that records the write protection in force when it is asked to collect."""

    def __init__(self, merge_write_blocker: MergeWriteBlocker, steps: list[str]) -> None:
        self._merge_write_blocker = merge_write_blocker
        self._steps = steps
        self.protection_during_collect: MergeProtection | None = None
        self.events = [
            (
                DiffAction.UPDATED,
                NodeChangelog(node_id=str(uuid4()), node_kind="TestCar", display_label="volt #444444"),
            )
        ]

    async def collect_changelogs(self) -> Sequence[tuple[DiffAction, NodeChangelog]]:
        self._steps.append("collect_changelogs")
        self.protection_during_collect = await self._merge_write_blocker.get()
        return self.events


class _RaisingChangelogCollector:
    async def collect_changelogs(self) -> Sequence[tuple[DiffAction, NodeChangelog]]:
        raise RuntimeError("changelog collection failed")


class _RecordingCollectorFactory:
    """Hands out one collector and records the diff and branch it was asked to collect for."""

    def __init__(self, collector: _ProbingChangelogCollector | _RaisingChangelogCollector) -> None:
        self._collector = collector
        self.diff: EnrichedDiffRoot | None = None
        self.branch: Branch | None = None

    def __call__(
        self, *, diff: EnrichedDiffRoot, db: InfrahubDatabase, branch: Branch
    ) -> _ProbingChangelogCollector | _RaisingChangelogCollector:
        self.diff = diff
        self.branch = branch
        return self._collector


def _diff_root(source_branch: Branch, destination_branch: Branch) -> EnrichedDiffRoot:
    now = Timestamp()
    return EnrichedDiffRoot(
        base_branch_name=destination_branch.name,
        diff_branch_name=source_branch.name,
        from_time=now,
        to_time=now,
        uuid=str(uuid4()),
        tracking_id=BranchTrackingId(name=source_branch.name),
    )


def _context(default_branch: Branch) -> InfrahubContext:
    return InfrahubContext.init(
        branch=default_branch,
        account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
    )


class _Harness:
    """A merge orchestrator whose collaborators write nothing and record what they were asked."""

    def __init__(
        self,
        db: InfrahubDatabase,
        source_branch: Branch,
        destination_branch: Branch,
        collector: _ProbingChangelogCollector | _RaisingChangelogCollector,
        merge_write_blocker: MergeWriteBlocker,
        cache: MemoryCache,
        steps: list[str],
    ) -> None:
        self.merge_write_blocker = merge_write_blocker
        self.steps = steps
        self.graph_merger = _ProbingGraphMerger(merge_write_blocker=merge_write_blocker)
        self.rollback_handler = _RecordingRollbackHandler()
        self.post_merge_dispatcher = _RecordingPostMergeDispatcher(steps=self.steps)
        self.collector_factory = _RecordingCollectorFactory(collector=collector)
        self.diff = _diff_root(source_branch=source_branch, destination_branch=destination_branch)
        serializer = DiffSummarySerializer()
        self.orchestrator = BranchMergeOrchestrator(
            db=db,
            source_branch=source_branch,
            destination_branch=destination_branch,
            graph_merger=self.graph_merger,
            schema_analyzer=_NoSchemaChangeAnalyzer(),
            schema_manager=registry.schema,
            schema_update_coordinator=SchemaUpdateCoordinator(
                db=db,
                schema_manager=registry.schema,
                rollbacker=GraphRollbacker(db=db),
                workflow=WorkflowLocalExecution(),
            ),
            rollback_handler=self.rollback_handler,
            post_merge_dispatcher=self.post_merge_dispatcher,
            merge_write_blocker=merge_write_blocker,
            ipam_diff_parser=_EmptyIpamDiffParser(),
            diff_repository=_StaticDiffRepository(diff=self.diff),
            diff_serializer=serializer,
            diff_summary_cache=DiffSummaryCache(cache=cache, serializer=serializer, key_namespace="branch_merge"),
            changelog_collector_factory=self.collector_factory,
        )


@pytest.fixture
def full_regeneration_after_merge() -> Generator[None, None, None]:
    """Skip the diff summary capture; the merge diff here carries no nodes to summarize."""
    original = config.SETTINGS.main.selective_execution_after_merge
    config.SETTINGS.main.selective_execution_after_merge = False
    yield
    config.SETTINGS.main.selective_execution_after_merge = original


class TestMergeChangelogCollection:
    """The node changelogs of a merge are collected once the merge is committed and writes are allowed again.

    Collecting them reads the graph, so it must not extend the write-protected window, and it must not be
    able to roll back a merge that has already succeeded. The node events drive the post-merge recompute,
    so a collection failure is reported rather than dispatched as an empty event set.
    """

    async def test_collects_once_write_protection_is_lifted(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_schema: SchemaBranch,
        full_regeneration_after_merge: None,
    ) -> None:
        source_branch = await create_branch(branch_name="feature", db=db)
        cache = MemoryCache()
        merge_write_blocker = MergeWriteBlocker(cache=cache)
        steps: list[str] = []
        collector = _ProbingChangelogCollector(merge_write_blocker=merge_write_blocker, steps=steps)
        harness = _Harness(
            db=db,
            source_branch=source_branch,
            destination_branch=default_branch,
            collector=collector,
            merge_write_blocker=merge_write_blocker,
            cache=cache,
            steps=steps,
        )

        await harness.orchestrator.merge(context=_context(default_branch))

        # The graph merge ran under protection, and the collection ran after it was lifted but before
        # the follow-ups, which may schedule the deletion of the branch it reads.
        assert harness.graph_merger.protection_during_merge == MergeProtection(
            branch=source_branch.name, state=MergeProtectionState.MERGING
        )
        assert collector.protection_during_collect is None
        assert harness.steps == ["collect_changelogs", "follow_ups", "dispatch_events"]

        assert harness.collector_factory.diff is harness.diff
        assert harness.collector_factory.branch is source_branch
        assert harness.post_merge_dispatcher.dispatched_node_events == [collector.events]
        assert harness.rollback_handler.calls == 0
        assert source_branch.status == BranchStatus.MERGED

    async def test_collection_failure_is_reported_on_the_committed_merge(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_schema: SchemaBranch,
        full_regeneration_after_merge: None,
    ) -> None:
        source_branch = await create_branch(branch_name="feature", db=db)
        cache = MemoryCache()
        merge_write_blocker = MergeWriteBlocker(cache=cache)
        harness = _Harness(
            db=db,
            source_branch=source_branch,
            destination_branch=default_branch,
            collector=_RaisingChangelogCollector(),
            merge_write_blocker=merge_write_blocker,
            cache=cache,
            steps=[],
        )

        with pytest.raises(RuntimeError, match=r"^changelog collection failed$"):
            await harness.orchestrator.merge(context=_context(default_branch))

        # The merge stays committed and unprotected, and the follow-ups that do not depend on the
        # node events have run; only the event dispatch is withheld.
        assert harness.rollback_handler.calls == 0
        assert source_branch.status == BranchStatus.MERGED
        assert await merge_write_blocker.get() is None
        assert harness.steps == ["follow_ups"]
        assert harness.post_merge_dispatcher.dispatched_node_events == []
