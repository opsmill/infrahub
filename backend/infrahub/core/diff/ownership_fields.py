"""Field names, values and labels that the diff uses for the owner state of a holder and the sources of a node."""

from __future__ import annotations

from typing import TYPE_CHECKING

import ujson

from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.ownership.fields import (
    FIELD_OWNERS_SUFFIX,
    FIELD_TARGET_OWNERS_SUFFIX,
    NODE_FIELDS,
    NODE_SOURCES_FIELD,
)
from infrahub.core.ownership.models import NODE_SOURCES_HOLDER, HolderKey, HolderKind, field_holder

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch

DELETED_OWNER_LABEL = "deleted owner"
DELETED_SOURCE_LABEL = "deleted source"
OWNER_LABEL_SEPARATOR = ", "


def holder_from_field_name(field_name: str) -> HolderKey | None:
    """Return the holder that the diff shows under a reserved field name, and None for any other field name."""
    return next((holder for holder, name in NODE_FIELDS.items() if name == field_name), None)


def field_owners_holder(field_name: str, schema: MainSchemaTypes, schema_branch: SchemaBranch) -> HolderKey | None:
    """Return the holder that the diff shows under the reserved name of the owners of one field of a node.

    Args:
        field_name: A field name of the diff.
        schema: The schema of the node.
        schema_branch: The schema of the branch of the node.

    Returns:
        None when the name is not the reserved name of a field of the kind.

    """
    if field_name.endswith(FIELD_TARGET_OWNERS_SUFFIX):
        # A profile or an object template gives owners to the fields of the kind that it is for.
        schema = schema_branch.get(name=schema.name, duplicate=False)
        return field_holder(schema=schema, field_name=field_name.removesuffix(FIELD_TARGET_OWNERS_SUFFIX), target=True)
    if not field_name.endswith(FIELD_OWNERS_SUFFIX):
        return None
    holder = field_holder(schema=schema, field_name=field_name.removesuffix(FIELD_OWNERS_SUFFIX))
    # The diff shows the owners of an attribute under the name of the attribute.
    return holder if holder and holder.kind == HolderKind.FIELD_SET else None


def is_owners_field_name(field_name: str) -> bool:
    """Tell if a field name is a reserved name for the owner list of a holder, or for the sources of a node."""
    return field_name == NODE_SOURCES_FIELD or field_name.endswith((FIELD_OWNERS_SUFFIX, FIELD_TARGET_OWNERS_SUFFIX))


def list_property_type(holder: HolderKey) -> DatabaseEdgeType:
    """Return the property type that the diff shows the owner list or the source list of a holder under."""
    return DatabaseEdgeType.HAS_SOURCE if holder == NODE_SOURCES_HOLDER else DatabaseEdgeType.HAS_OWNER


def is_list_property(field_name: str, property_type: DatabaseEdgeType) -> bool:
    """Tell if a property of a node field in the diff is the owner list of a holder or the sources of a node."""
    if property_type is DatabaseEdgeType.HAS_SOURCE:
        return field_name == NODE_SOURCES_FIELD
    return property_type is DatabaseEdgeType.HAS_OWNER


def deleted_label(is_source: bool) -> str:
    """Return the label that a list shows in place of a deleted node."""
    return DELETED_SOURCE_LABEL if is_source else DELETED_OWNER_LABEL


def is_owner_list_path(path: str) -> bool:
    """Tell if the path identifier of a property of a node field in the diff is an owner list or a source list."""
    return path.endswith(
        (
            f"/property/{DatabaseEdgeType.HAS_OWNER.value}",
            f"/{NODE_SOURCES_FIELD}/property/{DatabaseEdgeType.HAS_SOURCE.value}",
        )
    )


def owner_ids_from_value(value: str | None) -> list[str] | None:
    """Return the owner IDs of a diff value, and None when the value is not a list of owners."""
    if value is None or not value.startswith("["):
        return None
    return list(ujson.loads(value))


def stored_owner_ids(value: str | None) -> tuple[str, ...] | None:
    """Return the owner IDs of the diff value of an owner list, and None when the value is None."""
    if value is None:
        return None
    owner_ids = owner_ids_from_value(value=value)
    # A diff that a release with one owner for each attribute stored holds the owner ID alone.
    return (value,) if owner_ids is None else tuple(owner_ids)
