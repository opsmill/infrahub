from prefect import get_client, task
from prefect.runtime import flow_run

from .constants import WorkflowTag


@task(name="add-branch-tag")
async def add_branch_tag(branch_name: str) -> None:
    client = get_client(sync_client=False)
    current_flow_run_id = flow_run.id
    current_tags: list[str] = flow_run.tags
    new_tags = current_tags + [WorkflowTag.BRANCH.render(identifier=branch_name)]
    await client.update_flow_run(current_flow_run_id, tags=list(new_tags))
