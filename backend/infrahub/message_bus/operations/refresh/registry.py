from infrahub import lock
from infrahub.core.registry import registry
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices
from infrahub.tasks.registry import refresh_branches
from infrahub.worker import WORKER_IDENTITY


async def branches(message: messages.RefreshRegistryBranches, service: InfrahubServices) -> None:
    if message.meta and message.meta.initiator_id == WORKER_IDENTITY:
        service.log.info("Ignoring refresh registry refresh request originating from self", worker=WORKER_IDENTITY)
        return

    async with service.database.start_session(read_only=True) as db:
        await refresh_branches(db=db)

    await service.component.refresh_schema_hash()


async def rebased_branch(message: messages.RefreshRegistryRebasedBranch, service: InfrahubServices) -> None:
    if message.meta and message.meta.initiator_id == WORKER_IDENTITY:
        service.log.info(
            "Ignoring refresh registry refreshed branch for request originating from self", worker=WORKER_IDENTITY
        )
        return

    async with lock.registry.local_schema_lock():
        service.log.info("Refreshing rebased branch")

        async with service.database.start_session(read_only=True) as db:
            registry.branch[message.branch] = await registry.branch_object.get_by_name(name=message.branch, db=db)
