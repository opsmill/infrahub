from __future__ import annotations

from prefect import flow

from infrahub.context import InfrahubContext  # noqa: TC001  needed for prefect flow
from infrahub.core import registry
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.models import RequestDiffUpdate  # noqa: TC001  needed for prefect flow
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.dependencies.registry import get_component_registry
from infrahub.log import get_logger
from infrahub.services import InfrahubServices  # noqa: TC001  needed for prefect flow
from infrahub.workflows.catalogue import DIFF_REFRESH
from infrahub.workflows.utils import add_tags

log = get_logger()


@flow(name="diff-update", flow_run_name="Update diff for branch {model.branch_name}")
async def update_diff(model: RequestDiffUpdate, service: InfrahubServices) -> None:
    await add_tags(branches=[model.branch_name])

    async with service.database.start_session(read_only=False) as db:
        component_registry = get_component_registry()
        base_branch = await registry.get_branch(db=db, branch=registry.default_branch)
        diff_branch = await registry.get_branch(db=db, branch=model.branch_name)

        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=diff_branch)

        await diff_coordinator.run_update(
            base_branch=base_branch,
            diff_branch=diff_branch,
            from_time=model.from_time,
            to_time=model.to_time,
            name=model.name,
        )


@flow(name="diff-refresh", flow_run_name="Recreate diff for branch {branch_name}")
async def refresh_diff(branch_name: str, diff_id: str, service: InfrahubServices) -> None:
    await add_tags(branches=[branch_name])

    async with service.database.start_session(read_only=False) as db:
        component_registry = get_component_registry()
        base_branch = await registry.get_branch(db=db, branch=registry.default_branch)
        diff_branch = await registry.get_branch(db=db, branch=branch_name)

        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=diff_branch)
        await diff_coordinator.recalculate(base_branch=base_branch, diff_branch=diff_branch, diff_id=diff_id)


@flow(name="diff-refresh-all", flow_run_name="Recreate all diffs for branch {branch_name}")
async def refresh_diff_all(branch_name: str, context: InfrahubContext, service: InfrahubServices) -> None:
    await add_tags(branches=[branch_name])

    async with service.database.start_session(read_only=True) as db:
        component_registry = get_component_registry()
        default_branch = registry.get_branch_from_registry()
        diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=default_branch)
        diff_roots_to_refresh = await diff_repository.get_roots_metadata(diff_branch_names=[branch_name])

        for diff_root in diff_roots_to_refresh:
            if diff_root.base_branch_name != diff_root.diff_branch_name:
                await service.workflow.submit_workflow(
                    workflow=DIFF_REFRESH,
                    context=context,
                    parameters={"branch_name": diff_root.diff_branch_name, "diff_id": diff_root.uuid},
                )
