from enum import StrEnum

EVENT_NAMESPACE = "infrahub"
ACCOUNT_EVENT_PREFIX = f"{EVENT_NAMESPACE}.account."


class EventSortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"
