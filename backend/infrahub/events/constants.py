from enum import StrEnum

EVENT_NAMESPACE = "infrahub"
ACCOUNT_EVENT_PREFIX = f"{EVENT_NAMESPACE}.account."

# Node events carry their origin so the per-node recompute automations fire only for live mutations,
# excluding the merge and rebase replays the coalesced recompute owns. The label is always present
# (it defaults to LIVE), so the automations use a single positive match on LIVE rather than a list of
# negations: Prefect evaluates a multi-value match as OR, so "!merge OR !rebase" would always be true
# and would not exclude anything.
NODE_ORIGIN_LABEL = f"{EVENT_NAMESPACE}.node.origin"


class NodeMutationOrigin(StrEnum):
    """How a node mutation event was produced: a live edit, or a replay by a merge or rebase."""

    LIVE = "live"
    MERGE = "merge"
    REBASE = "rebase"


class EventSortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"
