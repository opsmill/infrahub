from enum import StrEnum

EVENT_NAMESPACE = "infrahub"
ACCOUNT_EVENT_PREFIX = f"{EVENT_NAMESPACE}.account."
NODE_ORIGIN_LABEL = f"{EVENT_NAMESPACE}.node.origin"


class NodeMutationOrigin(StrEnum):
    """How a node mutation event was produced.

    A live edit, a replay by a merge or rebase, or a derived-value recompute write.
    """

    LIVE = "live"
    MERGE = "merge"
    REBASE = "rebase"
    RECOMPUTE = "recompute"


class EventSortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"
