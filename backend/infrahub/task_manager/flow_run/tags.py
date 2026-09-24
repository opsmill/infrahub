from prefect.client.schemas.objects import FlowRun

from infrahub.workflows.constants import WorkflowTag, WorkflowType


class WorkflowTagDecoder:
    """Recover Infrahub metadata that is encoded into Prefect flow-run tags."""

    def workflow_type(self, flow: FlowRun) -> WorkflowType | None:
        return self.workflow_type_from_tags(tags=flow.tags)

    def workflow_type_from_tags(self, tags: list[str]) -> WorkflowType | None:
        """Decode the workflow type from a tag list, returning None when absent or unrecognised."""
        prefix = WorkflowTag.WORKFLOWTYPE.render(identifier="")
        values = [tag.removeprefix(prefix) for tag in tags if tag.startswith(prefix)]
        for value in values:
            try:
                return WorkflowType(value)
            except ValueError:
                continue
        return None

    def branch_name(self, flow: FlowRun) -> str | None:
        prefix = WorkflowTag.BRANCH.render(identifier="")
        names = [tag.replace(prefix, "") for tag in flow.tags if tag.startswith(prefix)]
        return names[0] if names else None

    def related_node_ids(self, flow: FlowRun) -> list[str]:
        prefix = WorkflowTag.RELATED_NODE.render(identifier="")
        return [tag.replace(prefix, "") for tag in flow.tags if tag.startswith(prefix)]
