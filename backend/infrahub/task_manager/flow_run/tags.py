from prefect.client.schemas.objects import FlowRun

from infrahub.workflows.constants import WorkflowTag


class WorkflowTagDecoder:
    """Recover Infrahub metadata that is encoded into Prefect flow-run tags."""

    def branch_name(self, flow: FlowRun) -> str | None:
        prefix = WorkflowTag.BRANCH.render(identifier="")
        names = [tag.replace(prefix, "") for tag in flow.tags if tag.startswith(prefix)]
        return names[0] if names else None

    def related_node_ids(self, flow: FlowRun) -> list[str]:
        prefix = WorkflowTag.RELATED_NODE.render(identifier="")
        return [tag.replace(prefix, "") for tag in flow.tags if tag.startswith(prefix)]
