from uuid import UUID
from typing import Union, Any
from itertools import groupby

from enum import Enum, EnumMeta


def is_valid_uuid(value: Any) -> bool:
    """Check if the input is a valid UUID."""
    try:
        UUID(str(value))
        return True
    except:
        return False


def duplicates(input_list: list) -> list:
    """Identify and return all the duplicates in a list."""

    dups = []
    for x, y in groupby(sorted(input_list)):
        #  list(y) returns all the occurences of item x
        if len(list(y)) > 1:
            dups.append(x)

    return dups


def intersection(list1, list2) -> list:
    """Calculate the intersection between 2 lists."""
    return list(set(list1) & set(list2))


class MetaEnum(EnumMeta):
    def __contains__(cls, item):
        try:
            cls(item)
        except ValueError:
            return False
        return True


class BaseEnum(Enum, metaclass=MetaEnum):
    pass
