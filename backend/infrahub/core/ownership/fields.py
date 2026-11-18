"""Reserved field names and values that the changelog and the diff use for the owner lists of a node."""

from __future__ import annotations

from typing import TYPE_CHECKING

import ujson

from .models import NODE_HOLDER, NODE_SOURCES_HOLDER, NODE_TARGET_HOLDER, HolderKey, HolderKind, holder_field

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch

NODE_OWNERS_FIELD = "node_metadata__owners"
NODE_TARGET_OWNERS_FIELD = "node_metadata__target_owners"
NODE_SOURCES_FIELD = "node_metadata__sources"
NODE_FIELDS = {
    NODE_HOLDER: NODE_OWNERS_FIELD,
    NODE_TARGET_HOLDER: NODE_TARGET_OWNERS_FIELD,
    NODE_SOURCES_HOLDER: NODE_SOURCES_FIELD,
}
"""The reserved field name of each holder that has no field of the node."""

FIELD_OWNERS_SUFFIX = "__owners"
FIELD_TARGET_OWNERS_SUFFIX = "__target_owners"
ATTRIBUTE_OWNERS_PROPERTY = "owners"
"""The property that a changelog records the owner list of an attribute under."""

OWNERS_CHANGELOG_KIND = "List"
"""The attribute kind that a changelog gives to the owner list of a holder."""


def holder_field_name(holder: HolderKey, field: str | None = None) -> str:
    """Return the field name that the diff shows the owners of a holder under.

    Args:
        holder: The holder of the owners.
        field: The name of the relationship or of the attribute, for a holder of the owners of one field.

    Raises:
        ValueError: When the diff has no field name for the holder.

    """
    if holder in NODE_FIELDS:
        return NODE_FIELDS[holder]
    if holder.kind == HolderKind.ATTRIBUTE and holder.attribute:
        return holder.attribute
    if field and holder.kind == HolderKind.FIELD_SET:
        return f"{field}{FIELD_OWNERS_SUFFIX}"
    if field and holder.kind == HolderKind.TARGET_SET:
        return f"{field}{FIELD_TARGET_OWNERS_SUFFIX}"
    raise ValueError(f"The diff has no field name for the owners of a {holder.kind.value} holder")


def stored_holder_field_name(holder: HolderKey, schema: MainSchemaTypes, schema_branch: SchemaBranch) -> str | None:
    """Return the field name that the diff shows the owners of a holder of a node under.

    Args:
        holder: The holder of the owners.
        schema: The schema of the node.
        schema_branch: The schema of the branch of the node.

    Returns:
        None for the owners of an attribute, which have no reserved name, and when the kind has no field for the
        holder.

    """
    if holder in NODE_FIELDS:
        return NODE_FIELDS[holder]
    if holder.kind == HolderKind.ATTRIBUTE:
        return None
    if holder.kind == HolderKind.TARGET_SET:
        # A profile or an object template gives owners to the fields of the kind that it is for.
        schema = schema_branch.get(name=schema.name, duplicate=False)
    field = holder_field(schema=schema, holder=holder)
    return holder_field_name(holder=holder, field=field) if field else None


def owner_list_value(owner_ids: tuple[str, ...] | None) -> str | None:
    """Return the diff value of an owner state: None for inherit, else a JSON list of the sorted owner IDs."""
    if owner_ids is None:
        return None
    return ujson.dumps(sorted(owner_ids))
