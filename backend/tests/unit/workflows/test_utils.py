from unittest.mock import AsyncMock, MagicMock, patch

from infrahub.workflows.constants import TAG_NAMESPACE, WorkflowTag
from infrahub.workflows.utils import add_tags


async def test_add_tags_does_not_grant_namespace_tag() -> None:
    client = MagicMock()
    client.update_flow_run = AsyncMock()

    with (
        patch("infrahub.workflows.utils.get_client", return_value=client),
        patch("infrahub.workflows.utils.get_http"),
        patch("infrahub.workflows.utils.flow_run") as mock_flow_run,
    ):
        mock_flow_run.id = "run-id"
        mock_flow_run.tags = [WorkflowTag.WORKFLOWTYPE.render(identifier="internal")]
        await add_tags(branches=["branch-1"], nodes=["node-1"])

    tags = client.update_flow_run.call_args.kwargs["tags"]
    assert TAG_NAMESPACE not in tags
    assert set(tags) == {
        WorkflowTag.WORKFLOWTYPE.render(identifier="internal"),
        WorkflowTag.BRANCH.render(identifier="branch-1"),
        WorkflowTag.RELATED_NODE.render(identifier="node-1"),
    }


async def test_add_tags_preserves_existing_namespace_tag() -> None:
    client = MagicMock()
    client.update_flow_run = AsyncMock()

    with (
        patch("infrahub.workflows.utils.get_client", return_value=client),
        patch("infrahub.workflows.utils.get_http"),
        patch("infrahub.workflows.utils.flow_run") as mock_flow_run,
    ):
        mock_flow_run.id = "run-id"
        mock_flow_run.tags = [TAG_NAMESPACE]
        await add_tags(branches=["branch-1"])

    assert TAG_NAMESPACE in client.update_flow_run.call_args.kwargs["tags"]
