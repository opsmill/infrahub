from enum import StrEnum


class OrderDirection(StrEnum):
    ASC = "ASC"
    DESC = "DESC"


class OrderByField(StrEnum):
    ID = "id"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
