from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from infrahub.core.schema import MainSchemaTypes


class OwnerState(StrEnum):
    INHERIT = "inherit"
    OWNERS = "owners"
    NO_OWNER = "no_owner"


class OwnerOrigin(StrEnum):
    SELF = "self"
    PROFILE = "profile"
    TEMPLATE = "template"
    PARENT = "parent"
    NODE = "node"


class HolderKind(StrEnum):
    """The vertex that holds a set of owners."""

    NODE = "node"
    ATTRIBUTE = "attribute"
    FIELD_SET = "field_set"
    """An `OwnerSet` vertex for the owners of one relationship of the node."""

    TARGET_SET = "target_set"
    """An `OwnerSet` vertex for the owners that a profile or an object template gives to its nodes."""

    SOURCES = "sources"
    """The node vertex, for the list of sources of the node."""


@dataclass(frozen=True)
class HolderKey:
    kind: HolderKind
    attribute: str | None = None
    identifier: str | None = None
    direction: str | None = None


NODE_HOLDER = HolderKey(kind=HolderKind.NODE)
NODE_TARGET_HOLDER = HolderKey(kind=HolderKind.TARGET_SET)
"""The owners that a profile or an object template gives to its nodes."""

NODE_SOURCES_HOLDER = HolderKey(kind=HolderKind.SOURCES)
"""The sources of a node. Its state holds the source IDs in `owner_ids`, and None when the node has no source."""


def field_holder(schema: MainSchemaTypes, field_name: str, target: bool = False) -> HolderKey | None:
    """Return the holder of the owners of one field of the nodes of a kind, and None when the kind has no such field.

    Args:
        schema: The schema of the kind that has the field.
        field_name: The name of an attribute or of a relationship.
        target: True for the owners that a profile or an object template gives to the field.

    """
    if field_name in schema.attribute_names:
        return HolderKey(kind=HolderKind.TARGET_SET if target else HolderKind.ATTRIBUTE, attribute=field_name)
    relationship = schema.get_relationship_or_none(name=field_name)
    if relationship is None:
        return None
    return HolderKey(
        kind=HolderKind.TARGET_SET if target else HolderKind.FIELD_SET,
        identifier=relationship.get_identifier(),
        direction=relationship.direction.value,
    )


def holder_field(schema: MainSchemaTypes, holder: HolderKey) -> str | None:
    """Return the name of the field of a kind that a holder keeps the owners of, and None when the kind has none."""
    if holder.attribute is not None:
        return holder.attribute if holder.attribute in schema.attribute_names else None
    return next(
        (
            relationship.name
            for relationship in schema.relationships
            if relationship.identifier == holder.identifier and relationship.direction.value == holder.direction
        ),
        None,
    )


def given_holder(holder: HolderKey) -> HolderKey:
    """Return the holder of the owners that a profile or an object template gives to the holder of one of its nodes."""
    return HolderKey(
        kind=HolderKind.TARGET_SET,
        attribute=holder.attribute,
        identifier=holder.identifier,
        direction=holder.direction,
    )


def receiving_holder(given: HolderKey) -> HolderKey:
    """Return the holder of a node that gets the owners that a profile or an object template gives."""
    if given.attribute is not None:
        return HolderKey(kind=HolderKind.ATTRIBUTE, attribute=given.attribute)
    if given.identifier is not None:
        return HolderKey(kind=HolderKind.FIELD_SET, identifier=given.identifier, direction=given.direction)
    return NODE_HOLDER


@dataclass(frozen=True)
class StoredOwnerState:
    owner_ids: tuple[str, ...] | None
    """None is inherit, an empty tuple is "no owner"."""

    template_id: str | None = None
    """The object template that the owners are a copy from."""

    @property
    def state(self) -> OwnerState:
        if self.owner_ids is None or self.template_id is not None:
            return OwnerState.INHERIT
        if not self.owner_ids:
            return OwnerState.NO_OWNER
        return OwnerState.OWNERS


INHERIT = StoredOwnerState(owner_ids=None)


@dataclass(frozen=True)
class StoredNodeOwnership:
    """The owner states that the graph stores for one node, with the links that the owner inheritance follows."""

    node_id: str
    kind: str
    holders: Mapping[HolderKey, StoredOwnerState] = field(default_factory=dict)
    """Only the holders that do not inherit, and the holder of the sources when the node has sources."""

    parent_id: str | None = None
    profiles: tuple[tuple[str, int | None], ...] = ()
    """The ID and the priority of each profile of the node."""

    def get(self, key: HolderKey) -> StoredOwnerState:
        return self.holders.get(key, INHERIT)


@dataclass(frozen=True)
class ResolvedOwnership:
    state: OwnerState
    """What a user set on the item itself, whatever the origin of the owners that apply."""

    owner_ids: tuple[str, ...]
    """The owners that apply, live or deleted."""

    origin: OwnerOrigin | None
    """None when no stored state applies."""

    origin_node_id: str | None
    """The profile, the template, the parent or the node that holds the owners."""


@dataclass(frozen=True)
class OwnerReference:
    id: str
    kind: str | None
    display_label: str | None
    hfid: tuple[str, ...] | None
    is_deleted: bool
