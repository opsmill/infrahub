from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from prefect import get_client
from prefect.runtime import flow_run

from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.registry import registry
from infrahub.tasks.registry import refresh_branches

from .constants import TAG_NAMESPACE, WorkflowTag

if TYPE_CHECKING:
    import logging

    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubComponent


async def add_tags(
    branches: list[str] | None = None,
    nodes: list[str] | None = None,
    others: list[str] | None = None,
    namespace: bool = True,
    db_change: bool = False,
) -> None:
    client = get_client(sync_client=False)
    current_flow_run_id = flow_run.id
    current_tags: list[str] = flow_run.tags
    branch_tags = (
        [
            WorkflowTag.BRANCH.render(identifier=branch_name)
            for branch_name in branches
            if branch_name != GLOBAL_BRANCH_NAME
        ]
        if branches
        else []
    )
    node_tags = [WorkflowTag.RELATED_NODE.render(identifier=node_id) for node_id in nodes] if nodes else []
    others_tags = others or []
    new_tags = set(current_tags + branch_tags + node_tags + others_tags)
    if namespace:
        new_tags.add(TAG_NAMESPACE)
    if db_change:
        new_tags.add(WorkflowTag.DATABASE_CHANGE.render())
    await client.update_flow_run(current_flow_run_id, tags=list(new_tags))


async def add_branch_tag(branch_name: str) -> None:
    await add_tags(branches=[branch_name])


async def add_related_node_tag(node_id: str) -> None:
    await add_tags(nodes=[node_id])


async def wait_for_schema_to_converge(
    branch_name: str, component: InfrahubComponent, db: InfrahubDatabase, log: logging.Logger | logging.LoggerAdapter
) -> None:
    has_converged = False
    branch_id = branch_name
    if branch := registry.branch.get(branch_name):
        branch_id = str(branch.get_uuid())

    delay = 0.2
    max_iterations = delay * 5 * 30
    iteration = 0
    while not has_converged:
        workers = await component.list_workers(branch=branch_id, schema_hash=True)

        hashes = {worker.schema_hash for worker in workers if worker.active}
        if len(hashes) == 1:
            has_converged = True
        else:
            await asyncio.sleep(delay=delay)

        if iteration >= max_iterations:
            log.warning(
                f"Schema had not converged after {delay * iteration:.2f} seconds, refreshing schema on local worker manually"
            )
            await refresh_branches(db=db)
            return

        iteration += 1

    log.info(f"Schema converged after {delay * iteration:.2f} seconds")
