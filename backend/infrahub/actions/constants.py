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


class MemberAction(Enum):
    ADD_MEMBER = DropdownChoice(
        name="add_member",
        label="Add member",
        description="Add impacted member to the selected group",
        color="#86efac",
    )
    REMOVE_MEMBER = DropdownChoice(
        name="remove_member",
        label="Remove member",
        description="Remove impacted member from the selected group",
        color="#fef08a",
    )

    @classmethod
    def available_types(cls) -> list[DropdownChoice]:
        return [cls.__members__[member].value for member in list(cls.__members__)]

    @classmethod
    def from_value(cls, value: str) -> MemberAction:
        for member in cls.__members__:
            if value == cls.__members__[member].value.name:
                return cls.__members__[member]

        raise NotImplementedError(f"The defined value {value} doesn't match a member action")


class MemberUpdate(Enum):
    ADDED = DropdownChoice(
        name="added",
        label="Added",
        description="Trigger when members are added to this group",
        color="#86efac",
    )
    REMOVED = DropdownChoice(
        name="removed",
        label="Removed",
        description="Trigger when members are removed from this group",
        color="#fef08a",
    )

    @classmethod
    def available_types(cls) -> list[DropdownChoice]:
        return [cls.__members__[member].value for member in list(cls.__members__)]

    @classmethod
    def from_value(cls, value: str) -> MemberUpdate:
        for member in cls.__members__:
            if value == cls.__members__[member].value.name:
                return cls.__members__[member]

        raise NotImplementedError(f"The defined value {value} doesn't match a MemberUpdate")


class RelationshipMatch(Enum):
    ADDED = DropdownChoice(
        name="added",
        label="Added",
        description="Check if the selected relationship was added",
        color="#86efac",
    )
    REMOVED = DropdownChoice(
        name="removed",
        label="Removed",
        description="Check if the selected relationship was removed",
        color="#fef08a",
    )
    UPDATED = DropdownChoice(
        name="updated",
        label="Updated",
        description="Check if the selected relationship was updated, added or removed.",
        color="#e5e7eb",
    )

    @classmethod
    def available_types(cls) -> list[DropdownChoice]:
        return [cls.__members__[member].value for member in list(cls.__members__)]

    @classmethod
    def from_value(cls, value: str) -> RelationshipMatch:
        for member in cls.__members__:
            if value == cls.__members__[member].value.name:
                return cls.__members__[member]

        raise NotImplementedError(f"The defined value {value} doesn't match a RelationshipMatch")


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
