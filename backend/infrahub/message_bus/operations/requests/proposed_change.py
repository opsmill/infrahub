from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices

log = get_logger()


async def data_integrity(
    message: messages.RequestProposedChangeDataIntegrity, service: InfrahubServices  # pylint: disable=unused-argument
) -> None:
    log.info(f"Got a request to process data integrity defined in proposed_change: {message.proposed_change}")


async def schema_integrity(
    message: messages.RequestProposedChangeSchemaIntegrity, service: InfrahubServices  # pylint: disable=unused-argument
) -> None:
    log.info(f"Got a request to process schema integrity defined in proposed_change: {message.proposed_change}")


async def repository_checks(message: messages.RequestProposedChangeRepositoryChecks, service: InfrahubServices) -> None:
    log.info(f"Got a request to process checks defined in proposed_change: {message.proposed_change}")
    change_proposal = await service.client.get(kind="CoreProposedChange", id=message.proposed_change)

    repositories = await service.client.all(kind="CoreRepository", branch=change_proposal.source_branch.value)
    for repository in repositories:
        msg = messages.RequestRepositoryChecks(
            proposed_change=message.proposed_change,
            repository=repository.id,
            branch=change_proposal.source_branch.value,
        )
        await service.send(message=msg)
