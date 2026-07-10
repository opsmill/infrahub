from enum import StrEnum

EVENT_NAMESPACE = "infrahub"
ACCOUNT_EVENT_PREFIX = f"{EVENT_NAMESPACE}.account."
NODE_ORIGIN_LABEL = f"{EVENT_NAMESPACE}.node.origin"


class NodeMutationOrigin(StrEnum):
    """How a node mutation event was produced: a live edit, or a replay by a merge or rebase."""

    LIVE = "live"
    MERGE = "merge"
    REBASE = "rebase"


class EventSortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"
