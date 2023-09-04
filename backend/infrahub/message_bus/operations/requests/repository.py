from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices

log = get_logger()


async def check(message: messages.RequestRepositoryChecks, service: InfrahubServices):
    """Request to start validation checks on a specific repository."""
    log.info("Running repository checks", repository_id=message.repository, proposed_change_id=message.proposed_change)
    repository = await service.client.get(kind="CoreRepository", id=message.repository, branch=message.source_branch)
    proposed_change = await service.client.get(
        kind="CoreProposedChange", id=message.proposed_change, branch=message.source_branch
    )
    await proposed_change.validations.fetch()
    validator_name = f"Repository Validator: {repository.name.value}"
    validator = None

    for relationship in proposed_change.validations.peers:
        existing_validator = relationship.peer

        if (
            existing_validator.typename == "CoreRepositoryValidator"
            and existing_validator.repository.id == message.repository
        ):
            validator = existing_validator

    if validator:
        validator.conclusion.value = "unknown"
        validator.state.value = "queued"
        await validator.save()
    else:
        validator = await service.client.create(
            kind="CoreRepositoryValidator",
            data={"name": validator_name, "proposed_change": message.proposed_change, "repository": message.repository},
        )
        await validator.save()

    msg = messages.CheckRepositoryMergeConflicts(
        validator_id=validator.id,
        proposed_change=message.proposed_change,
        repository_id=message.repository,
        repository_name=repository.name.value,
        source_branch=message.source_branch,
        target_branch=message.target_branch,
    )
    msg.assign_meta(parent=message)
    await service.send(message=msg)
