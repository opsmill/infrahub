from enum import StrEnum

EVENT_NAMESPACE = "infrahub"
ACCOUNT_EVENT_PREFIX = f"{EVENT_NAMESPACE}.account."

# Resource label on a node mutation event carrying its origin ("live", "merge", or "rebase"). The
# per-node recompute automations subscribe to it by matching "live" directly, so a merge or rebase
# replay (a non-live origin) is skipped and handled by the coalesced pass instead. Matching by
# exclusion would not work: Prefect ORs a multi-value match, so "not merge, not rebase" is always
# true and would exclude nothing.
NODE_ORIGIN_LABEL = f"{EVENT_NAMESPACE}.node.origin"


class NodeMutationOrigin(StrEnum):
    """How a node mutation event was produced: a live edit, or a replay by a merge or rebase."""

    LIVE = "live"
    MERGE = "merge"
    REBASE = "rebase"


class EventSortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"
