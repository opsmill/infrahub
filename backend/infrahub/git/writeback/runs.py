from __future__ import annotations

from infrahub.workflows.constants import WorkflowTag


def delivery_run_tags(repository_id: str) -> list[str]:
    """Return the tags that a delivery run of the repository carries from its submission.

    A run that waits in the queue has not started, so only the tags of its submission find it.
    """
    return [WorkflowTag.RELATED_NODE.render(identifier=repository_id), WorkflowTag.REPOSITORY_DELIVERY.render()]
