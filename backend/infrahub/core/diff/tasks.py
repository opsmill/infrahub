from prefect import flow

from infrahub.core import registry
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.models import RequestDiffRefresh, RequestDiffUpdate
from infrahub.dependencies.registry import get_component_registry
from infrahub.log import get_logger
from infrahub.services import services
from infrahub.workflows.utils import add_branch_tag

log = get_logger()


@flow(name="diff-update", flow_run_name="Update diff for branch {model.branch_name}")
async def update_diff(model: RequestDiffUpdate) -> None:
    service = services.service
    await add_branch_tag(branch_name=model.branch_name)

    component_registry = get_component_registry()
    base_branch = await registry.get_branch(db=service.database, branch=registry.default_branch)
    diff_branch = await registry.get_branch(db=service.database, branch=model.branch_name)

    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=service.database, branch=diff_branch)

    await diff_coordinator.run_update(
        base_branch=base_branch,
        diff_branch=diff_branch,
        from_time=model.from_time,
        to_time=model.to_time,
        name=model.name,
    )


@flow(name="diff-refresh", flow_run_name="Recreate diff for branch {model.branch_name}")
async def refresh_diff(model: RequestDiffRefresh) -> None:
    service = services.service
    await add_branch_tag(branch_name=model.branch_name)

    component_registry = get_component_registry()
    base_branch = await registry.get_branch(db=service.database, branch=registry.default_branch)
    diff_branch = await registry.get_branch(db=service.database, branch=model.branch_name)

    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=service.database, branch=diff_branch)
    await diff_coordinator.recalculate(base_branch=base_branch, diff_branch=diff_branch, diff_id=model.diff_id)
