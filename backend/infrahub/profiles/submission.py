from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.events.limits import get_submission_chunk_size
from infrahub.utilities.chunks import chunked
from infrahub.workflows.catalogue import PROFILE_REFRESH_MULTIPLE
from infrahub.workflows.constants import WorkflowTag

if TYPE_CHECKING:
    from infrahub.events.models import EventContext
    from infrahub.services.adapters.workflow import InfrahubWorkflow


async def submit_profile_refresh(
    workflow: InfrahubWorkflow,
    branch_name: str,
    node_ids: list[str],
    context: EventContext,
    profile_id: str | None = None,
) -> None:
    """Submit one profile refresh flow for each chunk of ``node_ids``.

    The runs link to ``profile_id`` and not to each node. Every tag of a run becomes a related resource
    on each event of that run, and one tag for each node would exceed the budget for them.
    """
    tags = [WorkflowTag.BRANCH.render(identifier=branch_name)]
    if profile_id is not None:
        tags.append(WorkflowTag.RELATED_NODE.render(identifier=profile_id))

    for chunk in chunked(node_ids, get_submission_chunk_size()):
        await workflow.submit_workflow(
            workflow=PROFILE_REFRESH_MULTIPLE,
            context=context,
            parameters={"branch_name": branch_name, "node_ids": chunk, "context": context},
            # Must be creation tags: in-flow tag updates drop tags added mid-run.
            tags=tags,
        )
