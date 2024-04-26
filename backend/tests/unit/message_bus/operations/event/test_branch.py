from infrahub.message_bus import messages
from infrahub.message_bus.operations.event.branch import delete, rebased
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


async def test_rebased():
    """Validate that a rebased branch triggers a registry refresh and cancels open proposed changes"""

    message = messages.EventBranchRebased(branch="cr1234")

    recorder = BusRecorder()
    service = InfrahubServices(message_bus=recorder)

    await rebased(message=message, service=service)

    assert len(recorder.messages) == 2
    assert isinstance(recorder.messages[0], messages.RefreshRegistryRebasedBranch)
    assert isinstance(recorder.messages[1], messages.TriggerIpamReconciliation)
    refresh_message: messages.RefreshRegistryRebasedBranch = recorder.messages[0]
    assert refresh_message.branch == "cr1234"
