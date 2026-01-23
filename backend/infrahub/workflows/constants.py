from infrahub.utils import InfrahubStringEnum


class WorkflowType(InfrahubStringEnum):
    INTERNAL = "internal"
    CORE = "core"
    USER = "user"


TAG_NAMESPACE = "infrahub.app"
TAG_CONCURRENCY_LIMIT_PER_WORKER = f"{TAG_NAMESPACE}/concurrency_limit_per_worker"


class WorkflowTag(InfrahubStringEnum):
    BRANCH = "branch/{identifier}"
    WORKFLOWTYPE = "workflow-type/{identifier}"
    DATABASE_CHANGE = "database-change"
    RELATED_NODE = "node/{identifier}"

    def render(self, identifier: str | None = None) -> str:
        if identifier is None:
            return f"{TAG_NAMESPACE}/{self.value}"
        rendered_value = str(self.value).format(identifier=identifier)
        return f"{TAG_NAMESPACE}/{rendered_value}"
