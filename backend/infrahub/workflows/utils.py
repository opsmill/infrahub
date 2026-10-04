from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from prefect.context import AsyncClientContext
from prefect.runtime import flow_run

from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.registry import registry
from infrahub.tasks.registry import refresh_branches

from .constants import TAG_NAMESPACE, WorkflowTag

if TYPE_CHECKING:
    import logging

    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubComponent


def render_tags(
    branches: list[str] | None = None,
    nodes: list[str] | None = None,
    others: list[str] | None = None,
    namespace: bool = True,
    db_change: bool = False,
) -> set[str]:
    """Render the Prefect flow run tags for branches, related nodes and flags.

    Args:
        branches: Branch names to tag. Each becomes a WorkflowTag.BRANCH tag.
            Global branch is excluded.
        nodes: Node IDs to tag. Each becomes a WorkflowTag.RELATED_NODE tag.
        others: Arbitrary string tags to add as-is.
        namespace: Whether to add the TAG_NAMESPACE tag (default True).
        db_change: Whether to add a WorkflowTag.DATABASE_CHANGE tag, indicating
            the flow run modifies the database.

    """
    tags = {
        WorkflowTag.BRANCH.render(identifier=branch_name)
        for branch_name in branches or []
        if branch_name != GLOBAL_BRANCH_NAME
    }
    tags.update(WorkflowTag.RELATED_NODE.render(identifier=node_id) for node_id in nodes or [])
    tags.update(others or [])
    if namespace:
        tags.add(TAG_NAMESPACE)
    if db_change:
        tags.add(WorkflowTag.DATABASE_CHANGE.render())
    return tags


def merge_tags(current: list[str], tags: set[str]) -> list[str] | None:
    """Return the full tag list to set on a flow run, or None when it already carries every tag."""
    if tags.issubset(current):
        return None
    return sorted(tags.union(current))


async def add_tags(
    branches: list[str] | None = None,
    nodes: list[str] | None = None,
    others: list[str] | None = None,
    namespace: bool = True,
    db_change: bool = False,
) -> None:
    """Add metadata tags to the current Prefect flow run for observability and filtering.

    Tags are applied via the Prefect API and appear in the Prefect UI, enabling operators
    to filter flow runs by branch, related node, or custom labels. The update goes through
    the running flow's Prefect client, so it opens no connection of its own, and is skipped
    when the flow run already carries every tag.

    Args:
        branches: Branch names to tag. Each becomes a WorkflowTag.BRANCH tag.
            Global branch is excluded.
        nodes: Node IDs to tag. Each becomes a WorkflowTag.RELATED_NODE tag.
        others: Arbitrary string tags to add as-is.
        namespace: Whether to add the TAG_NAMESPACE tag (default True).
        db_change: Whether to add a WorkflowTag.DATABASE_CHANGE tag, indicating
            the flow run modifies the database.

    """
    tags = merge_tags(
        current=flow_run.tags,
        tags=render_tags(branches=branches, nodes=nodes, others=others, namespace=namespace, db_change=db_change),
    )
    if tags is None:
        return
    async with AsyncClientContext.get_or_create() as client_ctx:
        await client_ctx.client.update_flow_run(flow_run_id=flow_run.id, tags=tags)


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
