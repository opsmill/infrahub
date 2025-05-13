from __future__ import annotations

from enum import Enum

from infrahub.core.constants import InfrahubKind
from infrahub.core.schema.dropdown import DropdownChoice
from infrahub.utils import InfrahubStringEnum


class NodeAction(InfrahubStringEnum):
    CREATED = "created"
    DELETED = "deleted"
    UPDATED = "updated"


class BranchScope(Enum):
    ALL_BRANCHES = DropdownChoice(
        name="all_branches",
        label="All Branches",
        description="All branches",
        color="#fef08a",
    )
    DEFAULT_BRANCH = DropdownChoice(
        name="default_branch",
        label="Default Branch",
        description="Only the default branch",
        color="#86efac",
    )
    OTHER_BRANCHES = DropdownChoice(
        name="other_branches",
        label="Other Branches",
        description="All branches except the default branch",
        color="#e5e7eb",
    )

    @classmethod
    def available_types(cls) -> list[DropdownChoice]:
        return [cls.__members__[member].value for member in list(cls.__members__)]

    @classmethod
    def from_value(cls, value: str) -> BranchScope:
        for member in cls.__members__:
            if value == cls.__members__[member].value.name:
                return cls.__members__[member]

        raise NotImplementedError(f"The defined value {value} doesn't match a branch scope")


class ValueMatch(Enum):
    VALUE = DropdownChoice(
        name="value",
        label="Value",
        description="Match against the current value",
        color="#fef08a",
    )
    VALUE_PREVIOUS = DropdownChoice(
        name="value_previous",
        label="Value Previous",
        description="Match against the previous value",
        color="#86efac",
    )
    VALUE_FULL = DropdownChoice(
        name="value_full",
        label="Full value match",
        description="Match against both the current and previous values",
        color="#e5e7eb",
    )

    @classmethod
    def available_types(cls) -> list[DropdownChoice]:
        return [cls.__members__[member].value for member in list(cls.__members__)]

    @classmethod
    def from_value(cls, value: str) -> ValueMatch:
        for member in cls.__members__:
            if value == cls.__members__[member].value.name:
                return cls.__members__[member]

        raise NotImplementedError(f"The defined value {value} doesn't match a ValueMatch")


NODES_THAT_TRIGGER_ACTION_RULES_SETUP = [
    InfrahubKind.GROUPACTION,
    InfrahubKind.GROUPTRIGGERRULE,
    InfrahubKind.NODETRIGGERRULE,
]
