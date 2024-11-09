from infrahub import lock
from infrahub.core.registry import registry
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices
from infrahub.tasks.registry import refresh_branches


async def branches(message: messages.RefreshRegistryBranches, service: InfrahubServices) -> None:  # pylint: disable=unused-argument
    async with service.database.start_session() as db:
        await refresh_branches(db=db)

    await service.component.refresh_schema_hash()


async def rebased_branch(message: messages.RefreshRegistryRebasedBranch, service: InfrahubServices) -> None:
    async with lock.registry.local_schema_lock():
        service.log.info("Refreshing rebased branch")
        registry.branch[message.branch] = await registry.branch_object.get_by_name(
            name=message.branch, db=service.database
        )
