from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices

log = get_logger()


async def mutated(
    message: messages.EventNodeMutated,
    service: InfrahubServices,  # pylint: disable=unused-argument
) -> None:
    log.debug(
        "Mutation on node",
        branch=message.branch,
        node_id=message.node_id,
        action=message.action,
        kind=message.kind,
        data=message.data,
    )
