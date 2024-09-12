from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

from infrahub.core.branch import Branch
from infrahub.core.diff.model.path import BranchTrackingId, EnrichedDiffRoot
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.timestamp import Timestamp
from infrahub.dependencies.component.registry import ComponentDependencyRegistry
from infrahub.message_bus import messages
from infrahub.message_bus.operations.event.branch import delete, merge, rebased
from infrahub.services import InfrahubServices
from tests.adapters.message_bus import BusRecorder


async def test_delete():
    """Validate that a deleted branch triggers a registry refresh and cancels open proposed changes"""

    message = messages.EventBranchDelete(
        branch_id="40fb612f-eaaa-422b-9480-df269080c103", branch="cr1234", sync_with_git=True
    )

    recorder = BusRecorder()
    service = InfrahubServices(message_bus=recorder)

    await delete(message=message, service=service)

    assert len(recorder.messages) == 2
    assert isinstance(recorder.messages[0], messages.RefreshRegistryBranches)
    assert isinstance(recorder.messages[1], messages.TriggerProposedChangeCancel)
    trigger_cancel: messages.TriggerProposedChangeCancel = recorder.messages[1]
    assert trigger_cancel.branch == "cr1234"


async def test_merged(default_branch: Branch):
    source_branch_name = "cr1234"
    target_branch_name = "main"
    right_now = Timestamp()
    message = messages.EventBranchMerge(
        source_branch=source_branch_name, target_branch=target_branch_name, ipam_node_details=[]
    )

    recorder = BusRecorder()
    database = MagicMock()
    service = InfrahubServices(message_bus=recorder, database=database)
    tracked_diff_roots = [
        EnrichedDiffRoot(
            base_branch_name=target_branch_name,
            diff_branch_name=str(uuid4()),
            from_time=right_now,
            to_time=right_now,
            uuid=str(uuid4()),
            tracking_id=BranchTrackingId(name=str(uuid4())),
        )
        for _ in range(2)
    ]
    untracked_diff_roots = [
        EnrichedDiffRoot(
            base_branch_name=target_branch_name,
            diff_branch_name=str(uuid4()),
            from_time=right_now,
            to_time=right_now,
            uuid=str(uuid4()),
        )
        for _ in range(2)
    ]
    diff_repo = AsyncMock(spec=DiffRepository)
    diff_repo.get_empty_roots.return_value = untracked_diff_roots + tracked_diff_roots
    mock_component_registry = Mock(spec=ComponentDependencyRegistry)
    mock_get_component_registry = MagicMock(return_value=mock_component_registry)
    mock_component_registry.get_component.return_value = diff_repo

    with patch("infrahub.message_bus.operations.event.branch.get_component_registry", new=mock_get_component_registry):
        await merge(message=message, service=service)

    mock_component_registry.get_component.assert_awaited_once_with(DiffRepository, db=database, branch=default_branch)
    diff_repo.get_empty_roots.assert_awaited_once_with(base_branch_names=[target_branch_name])
    assert len(recorder.messages) == 6
    assert recorder.messages[0] == messages.RefreshRegistryBranches()
    assert recorder.messages[1] == messages.TriggerIpamReconciliation(branch=target_branch_name, ipam_node_details=[])
    assert recorder.messages[2] == messages.TriggerArtifactDefinitionGenerate(branch=target_branch_name)
    assert recorder.messages[3] == messages.TriggerGeneratorDefinitionRun(branch=target_branch_name)
    assert recorder.messages[4] == messages.RequestDiffUpdate(branch_name=tracked_diff_roots[0].diff_branch_name)
    assert recorder.messages[5] == messages.RequestDiffUpdate(branch_name=tracked_diff_roots[1].diff_branch_name)


async def test_rebased(default_branch: Branch):
    """Validate that a rebased branch triggers a registry refresh and cancels open proposed changes"""
    branch_name = "cr1234"
    right_now = Timestamp()
    message = messages.EventBranchRebased(branch=branch_name)

    recorder = BusRecorder()
    database = MagicMock()
    service = InfrahubServices(message_bus=recorder, database=database)
    diff_roots = [
        EnrichedDiffRoot(
            base_branch_name="main",
            diff_branch_name=branch_name,
            from_time=right_now,
            to_time=right_now,
            uuid=str(uuid4()),
        )
        for _ in range(2)
    ]
    diff_repo = AsyncMock(spec=DiffRepository)
    diff_repo.get_empty_roots.return_value = diff_roots
    mock_component_registry = Mock(spec=ComponentDependencyRegistry)
    mock_get_component_registry = MagicMock(return_value=mock_component_registry)
    mock_component_registry.get_component.return_value = diff_repo

    with patch("infrahub.message_bus.operations.event.branch.get_component_registry", new=mock_get_component_registry):
        await rebased(message=message, service=service)

    mock_component_registry.get_component.assert_awaited_once_with(DiffRepository, db=database, branch=default_branch)
    diff_repo.get_empty_roots.assert_awaited_once_with(diff_branch_names=[branch_name])
    assert len(recorder.messages) == 3
    assert isinstance(recorder.messages[0], messages.RefreshRegistryRebasedBranch)
    refresh_message: messages.RefreshRegistryRebasedBranch = recorder.messages[0]
    assert refresh_message.branch == "cr1234"
    assert recorder.messages[1] == messages.RequestDiffRefresh(branch_name=branch_name, diff_id=diff_roots[0].uuid)
    assert recorder.messages[2] == messages.RequestDiffRefresh(branch_name=branch_name, diff_id=diff_roots[1].uuid)
