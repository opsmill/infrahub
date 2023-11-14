from infrahub.message_bus import messages
from infrahub.message_bus.operations.event.branch import delete
from infrahub.services import InfrahubServices


async def test_delete(helper):
    """Validate that a deleted branch triggers a registry refresh and cancels open proposed changes"""

    message = messages.EventBranchDelete(
        branch_id="40fb612f-eaaa-422b-9480-df269080c103", branch="cr1234", data_only=False
    )

    recorder = helper.get_message_bus_recorder()
    service = InfrahubServices(message_bus=recorder)

    await delete(message=message, service=service)

    assert len(recorder.messages) == 2
    assert isinstance(recorder.messages[0], messages.RefreshRegistryBranches)
    assert isinstance(recorder.messages[1], messages.TriggerProposedChangeCancel)
    trigger_cancel: messages.TriggerProposedChangeCancel = recorder.messages[1]
    assert trigger_cancel.branch == "cr1234"
