from enum import Flag, auto

from infrahub.utils import InfrahubStringEnum


class WorkflowType(Flag):
    INTERNAL = auto()
    CORE = auto()
    USER = auto()


TAG_NAMESPACE = "infrahub.app"


class WorkflowTag(InfrahubStringEnum):
    BRANCH = "branch/{identifier}"
    WORKFLOWTYPE = "workflow-type/{identifier}"
    DATABASE_CHANGE = "database-change"
    RELATED_NODE = "node/{identifier}"

    def render(self, identifier: str | None = None) -> str:
        if identifier is None:
            return f"{TAG_NAMESPACE}/{self.value}"
        rendered_value = str(self.value).format(identifier=identifier.lower())
        return f"{TAG_NAMESPACE}/{rendered_value}"


class WorkerType(InfrahubStringEnum):
    INFRAHUB_ASYNC = "infrahubasync"
    PROCESS = "process"
