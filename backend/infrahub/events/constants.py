from enum import StrEnum

EVENT_NAMESPACE = "infrahub"
ACCOUNT_EVENT_PREFIX = f"{EVENT_NAMESPACE}.account."

# Node events carry their origin so replayed merge and rebase changes can be excluded from the
# per-node recompute automations while live mutations keep firing. The label is always present,
# defaulting to "live", because a negative match never matches an absent label.
NODE_ORIGIN_LABEL = f"{EVENT_NAMESPACE}.node.origin"
NODE_ORIGIN_LIVE = "live"
NODE_ORIGIN_MERGE = "merge"
NODE_ORIGIN_REBASE = "rebase"
REPLAYED_NODE_ORIGINS = (NODE_ORIGIN_MERGE, NODE_ORIGIN_REBASE)


def excluded_replayed_origins_match() -> list[str]:
    """Prefect match value selecting node events that are not a replayed merge or rebase."""
    return [f"!{origin}" for origin in REPLAYED_NODE_ORIGINS]


class EventSortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"
