from __future__ import annotations

from enum import Enum
from typing import Self

from infrahub.core.constants import InfrahubKind
from infrahub.core.schema.dropdown import DropdownChoice
from infrahub.utils import InfrahubStringEnum


class NodeAction(InfrahubStringEnum):
    CREATED = "created"
    UPDATED = "updated"


class DropdownEnum(Enum):
    @classmethod
    def available_types(cls) -> list[DropdownChoice]:
        return [cls.__members__[member].value for member in list(cls.__members__)]

    @classmethod
    def from_value(cls, value: str) -> Self:
        for member in cls.__members__:
            if value == cls.__members__[member].value.name:
                return cls.__members__[member]

        raise NotImplementedError(f"The defined value {value} doesn't match a value of {cls.__class__.__name__}")


class BranchScope(DropdownEnum):
    ALL_BRANCHES = DropdownChoice(
        name="all_branches",
        label="All Branches",
        description="All branches",
        color="#4cd964",
    )
    DEFAULT_BRANCH = DropdownChoice(
        name="default_branch",
        label="Default Branch",
        description="Only the default branch",
        color="#5ac8fa",
    )
    OTHER_BRANCHES = DropdownChoice(
        name="other_branches",
        label="Other Branches",
        description="All branches except the default branch",
        color="#ff2d55",
    )


class MemberAction(DropdownEnum):
    ADD_MEMBER = DropdownChoice(
        name="add_member",
        label="Add member",
        description="Add impacted member to the selected group",
        color="#4cd964",
    )
    REMOVE_MEMBER = DropdownChoice(
        name="remove_member",
        label="Remove member",
        description="Remove impacted member from the selected group",
        color="#ff2d55",
    )


class MemberUpdate(DropdownEnum):
    ADDED = DropdownChoice(
        name="added",
        label="Added",
        description="Trigger when members are added to this group",
        color="#4cd964",
    )
    REMOVED = DropdownChoice(
        name="removed",
        label="Removed",
        description="Trigger when members are removed from this group",
        color="#ff2d55",
    )


class RelationshipMatch(DropdownEnum):
    ADDED = DropdownChoice(
        name="added",
        label="Added",
        description="Check if the selected relationship was added",
        color="#4cd964",
    )
    REMOVED = DropdownChoice(
        name="removed",
        label="Removed",
        description="Check if the selected relationship was removed",
        color="#ff2d55",
    )
    UPDATED = DropdownChoice(
        name="updated",
        label="Updated",
        description="Check if the selected relationship was updated, added or removed.",
        color="#5ac8fa",
    )


class ValueMatch(DropdownEnum):
    VALUE = DropdownChoice(
        name="value",
        label="Value",
        description="Match against the current value",
        color="#4cd964",
    )
    VALUE_PREVIOUS = DropdownChoice(
        name="value_previous",
        label="Value Previous",
        description="Match against the previous value",
        color="#ff2d55",
    )
    VALUE_FULL = DropdownChoice(
        name="value_full",
        label="Full value match",
        description="Match against both the current and previous values",
        color="#5ac8fa",
    )


NODES_THAT_TRIGGER_ACTION_RULES_SETUP = [
    InfrahubKind.GENERATORACTION,
    InfrahubKind.GROUPACTION,
    InfrahubKind.GROUPTRIGGERRULE,
    InfrahubKind.NODETRIGGERRULE,
    InfrahubKind.NODETRIGGERATTRIBUTEMATCH,
    InfrahubKind.NODETRIGGERRELATIONSHIPMATCH,
]
