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
    # A recompute write carries this so the per-node recompute automations (which match LIVE) skip
    # it; the next recompute level is dispatched as one coalesced pass instead of per changed node.
    RECOMPUTE = "recompute"


class EventSortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"
