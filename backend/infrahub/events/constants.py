from enum import Enum

EVENT_NAMESPACE = "infrahub"


class EventSortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"
