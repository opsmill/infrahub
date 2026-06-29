from enum import StrEnum

EVENT_NAMESPACE = "infrahub"
ACCOUNT_EVENT_PREFIX = f"{EVENT_NAMESPACE}.account."

# Node events carry their origin so the per-node recompute automations fire only for live mutations,
# excluding the merge and rebase replays the coalesced recompute owns. The label is always present
# (it defaults to "live"), so the automations use a single positive match on "live" rather than a
# list of negations: Prefect evaluates a multi-value match as OR, so "!merge OR !rebase" would always
# be true and would not exclude anything.
NODE_ORIGIN_LABEL = f"{EVENT_NAMESPACE}.node.origin"
NODE_ORIGIN_LIVE = "live"
NODE_ORIGIN_MERGE = "merge"
NODE_ORIGIN_REBASE = "rebase"


class EventSortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"
