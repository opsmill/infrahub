from infrahub.message_bus import messages
from infrahub.services import InfrahubServices


async def mutated(
    message: messages.EventNodeMutated,
    service: InfrahubServices,
) -> None:
    """Event posted when a node is mutated"""
    # Note for now this is only kept to facilitate publishing to other queues in the future
    # This operation doesn't have a flow defined to avoid having the workers need to register
    # the results in Prefect when they don't actually do anything aside from add noise.
    service.log.debug(
        "Mutation on node",
        branch=message.branch,
        node_id=message.node_id,
        action=message.action,
        kind=message.kind,
        data=message.data,
    )
