from infrahub.core import registry
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.timestamp import Timestamp
from infrahub.dependencies.registry import get_component_registry
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices

log = get_logger()


async def update(message: messages.RequestDiffUpdate, service: InfrahubServices) -> None:
    component_registry = get_component_registry()
    base_branch = await registry.get_branch(db=service.database, branch=registry.default_branch)
    diff_branch = await registry.get_branch(db=service.database, branch=message.branch_name)

    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=service.database, branch=diff_branch)

    branch_start_timestamp = Timestamp(diff_branch.get_created_at())
    if message.from_time:
        from_timestamp = Timestamp(message.from_time)
    else:
        from_timestamp = branch_start_timestamp
    if message.to_time:
        to_timestamp = Timestamp(message.to_time)
    else:
        to_timestamp = Timestamp()

    await diff_coordinator.update_diffs(
        base_branch=base_branch,
        diff_branch=diff_branch,
        from_time=from_timestamp,
        to_time=to_timestamp,
    )
