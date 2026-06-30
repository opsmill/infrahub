from enum import StrEnum

EVENT_NAMESPACE = "infrahub"
ACCOUNT_EVENT_PREFIX = f"{EVENT_NAMESPACE}.account."

# Recompute automations match LIVE positively, not a list of negations: Prefect ORs a multi-value
# match, so "not merge, not rebase" would always be true and exclude nothing.
NODE_ORIGIN_LABEL = f"{EVENT_NAMESPACE}.node.origin"


class NodeMutationOrigin(StrEnum):
    """How a node mutation event was produced: a live edit, or a replay by a merge or rebase."""

    LIVE = "live"
    MERGE = "merge"
    REBASE = "rebase"


class EventSortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"
