from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from prefect import get_client
from prefect.runtime import flow_run

from infrahub.core.registry import registry
from infrahub.tasks.registry import refresh_branches

from .constants import WorkflowTag

if TYPE_CHECKING:
    import logging

    from infrahub.services import InfrahubServices


async def add_tags(tags: list[str]) -> None:
    client = get_client(sync_client=False)
    current_flow_run_id = flow_run.id
    current_tags: list[str] = flow_run.tags
    new_tags = current_tags + tags
    await client.update_flow_run(current_flow_run_id, tags=list(new_tags))


async def add_branch_tag(branch_name: str) -> None:
    tag = WorkflowTag.BRANCH.render(identifier=branch_name)
    await add_tags(tags=[tag])


async def add_related_node_tag(node_id: str) -> None:
    tag = WorkflowTag.RELATED_NODE.render(identifier=node_id)
    await add_tags(tags=[tag])


async def wait_for_schema_to_converge(
    branch_name: str, service: InfrahubServices, log: logging.Logger | logging.LoggerAdapter
) -> None:
    has_converged = False
    branch_id = branch_name
    if branch := registry.branch.get(branch_name):
        branch_id = branch.get_id()

    delay = 0.2
    max_iterations = delay * 5 * 30
    iteration = 0
    while not has_converged:
        workers = await service.component.list_workers(branch=branch_id, schema_hash=True)

        hashes = {worker.schema_hash for worker in workers if worker.active}
        if len(hashes) == 1:
            has_converged = True
        else:
            await asyncio.sleep(delay=delay)

        if iteration >= max_iterations:
            log.warning(
                f"Schema had not converged after {delay * iteration} seconds, refreshing schema on local worker manually"
            )
            async with service.database.start_session() as db:
                await refresh_branches(db=db)
            return

        iteration += 1

    log.info(f"Schema converged after {delay * iteration} seconds")
