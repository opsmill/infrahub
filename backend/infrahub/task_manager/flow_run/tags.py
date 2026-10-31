from prefect.client.schemas.objects import FlowRun

from infrahub.workflows.constants import WorkflowTag


class WorkflowTagDecoder:
    """Recover Infrahub metadata that is encoded into Prefect flow-run tags."""

    def branch_name(self, flow: FlowRun) -> str | None:
        # A run tagged with two branches keeps showing the one that still exists after the other is deleted.
        for tag_kind in (WorkflowTag.BRANCH, WorkflowTag.DELETED_BRANCH):
            prefix = tag_kind.render(identifier="")
            name = next((tag.removeprefix(prefix) for tag in flow.tags if tag.startswith(prefix)), None)
            if name is not None:
                return name
        return None

    def related_node_ids(self, flow: FlowRun) -> list[str]:
        prefix = WorkflowTag.RELATED_NODE.render(identifier="")
        return [tag.replace(prefix, "") for tag in flow.tags if tag.startswith(prefix)]
