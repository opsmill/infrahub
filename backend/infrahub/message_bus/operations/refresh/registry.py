from infrahub import lock
from infrahub.core.registry import registry
from infrahub.message_bus import messages
from infrahub.tasks.registry import refresh_branches
from infrahub.worker import WORKER_IDENTITY
from infrahub.workers.dependencies import get_component, get_database, get_log


async def branches(message: messages.RefreshRegistryBranches) -> None:
    if message.meta and message.meta.initiator_id == WORKER_IDENTITY:
        get_log().info("Ignoring refresh registry refresh request originating from self", worker=WORKER_IDENTITY)
        return

    database = await get_database()
    async with database.start_session(read_only=False) as db:
        await refresh_branches(db=db)

    component = await get_component()
    await component.refresh_schema_hash()


async def rebased_branch(message: messages.RefreshRegistryRebasedBranch) -> None:
    if message.meta and message.meta.initiator_id == WORKER_IDENTITY:
        get_log().info(
            "Ignoring refresh registry refreshed branch for request originating from self", worker=WORKER_IDENTITY
        )
        return

    async with lock.registry.local_schema_lock():
        get_log().info("Refreshing rebased branch")

        database = await get_database()
        async with database.start_session(read_only=True) as db:
            registry.branch[message.branch] = await registry.branch_object.get_by_name(name=message.branch, db=db)
