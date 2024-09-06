from infrahub.core import registry
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.model.path import deserialize_tracking_id
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
    await diff_coordinator.run_update(
        base_branch=base_branch,
        diff_branch=diff_branch,
        from_time=message.from_time,
        to_time=message.to_time,
        name=message.name,
    )


async def refresh(message: messages.RequestDiffRefresh, service: InfrahubServices) -> None:
    component_registry = get_component_registry()
    base_branch = await registry.get_branch(db=service.database, branch=registry.default_branch)
    diff_branch = await registry.get_branch(db=service.database, branch=message.branch_name)
    tracking_id = deserialize_tracking_id(tracking_id_str=message.tracking_id_str)

    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=service.database, branch=diff_branch)
    await diff_coordinator.recalculate_for_tracked_diff(
        base_branch=base_branch, diff_branch=diff_branch, tracking_id=tracking_id
    )
