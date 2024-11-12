from prefect import get_client
from prefect.runtime import flow_run

from .constants import WorkflowTag


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
