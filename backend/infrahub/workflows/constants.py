from infrahub.utils import InfrahubStringEnum


class WorkflowType(InfrahubStringEnum):
    INTERNAL = "internal"
    CORE = "core"
    USER = "user"


class WorkflowPriority(InfrahubStringEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def queue_name(self) -> str:
        return self.value

    @property
    def queue_priority(self) -> int:
        """Prefect work-queue precedence integer, where a lower number means higher precedence."""
        match self:
            case WorkflowPriority.HIGH:
                return 1
            case WorkflowPriority.MEDIUM:
                return 2
            case WorkflowPriority.LOW:
                return 3


TAG_NAMESPACE = "infrahub.app"


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
