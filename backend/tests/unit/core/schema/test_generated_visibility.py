from __future__ import annotations

import enum
import types
import typing

import pytest
from infrahub_sdk.schema.generated import read as sdk_read
from infrahub_sdk.schema.generated import write as sdk_write
from infrahub_sdk.schema.generated.contract import READ_ONLY_FIELDS

from infrahub.core.constants import Visibility
from infrahub.core.schema.definitions.internal import (
    attribute_schema,
    base_node_schema,
    generic_schema,
    node_schema,
    relationship_schema,
)
from infrahub.types import ATTRIBUTE_KIND_LABELS

if typing.TYPE_CHECKING:
    from pydantic import BaseModel

# Map each schema-definition family to the generated SDK *write* model it produces. The attribute
# family is a discriminated union on kind; its shared fields live on AttributeSchemaBaseWrite, so
# shared-field checks introspect the base while kind coverage is asserted per variant separately.
DEFINITION_TO_WRITE_MODEL = {
    "attribute": (attribute_schema, sdk_write.AttributeSchemaBaseWrite),
    "relationship": (relationship_schema, sdk_write.RelationshipSchemaWrite),
    "base_node": (base_node_schema, sdk_write.BaseNodeSchemaWrite),
    "node": (node_schema, sdk_write.NodeSchemaWrite),
    "generic": (generic_schema, sdk_write.GenericSchemaWrite),
}


def _allowed_values(annotation: typing.Any) -> tuple[typing.Any, ...] | None:
    """Return the bounded set of values a field publishes, unwrapping an optional union.

    A generated field publishes its allowed set either as a ``Literal[...]`` or as a
    dedicated ``Enum`` subclass; both are recognised here. Returns None when the
    annotation is neither (optionally), i.e. the field is unbounded (bare ``str``/``int``).
    """
    origin = typing.get_origin(annotation)
    if origin is typing.Literal:
        return typing.get_args(annotation)

    # A dedicated Enum subclass publishes its allowed set as its members.
    if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        return tuple(annotation)

    # Unwrap ``X | None`` / ``Optional[X]`` and look for a bounded member.
    if origin in {typing.Union, types.UnionType}:
        for arg in typing.get_args(annotation):
            values = _allowed_values(arg)
            if values is not None:
                return values
    return None


# Core user-settable fields that must remain writable; a settable field silently defaulting to a
# non-write visibility would drop out of the write model and break loading a hand-authored schema.
REQUIRED_WRITE_FIELDS = {
    "node": {"name", "namespace", "description"},
    "attribute": {"name", "kind", "optional", "read_only"},
    "relationship": {"name", "peer", "kind", "cardinality", "optional"},
}


@pytest.mark.parametrize("family", list(DEFINITION_TO_WRITE_MODEL))
def test_write_model_exposes_no_read_or_internal_field(family: str) -> None:
    """The generated write model of each family exposes only write-level fields."""
    definition, write_model = DEFINITION_TO_WRITE_MODEL[family]

    non_write_names = {field.name for field in definition.attributes if field.visibility is not Visibility.WRITE} | {
        rel.name for rel in definition.relationships if rel.visibility is not Visibility.WRITE
    }

    leaked = non_write_names & set(write_model.model_fields)
    assert not leaked, f"{write_model.__name__} exposes non-write fields: {sorted(leaked)}"


@pytest.mark.parametrize("family", list(REQUIRED_WRITE_FIELDS))
def test_write_model_keeps_core_settable_fields(family: str) -> None:
    """Each family's core user-settable fields stay present in its write model.

    Guards against a settable field silently defaulting to a non-write visibility and being
    dropped from the write model, which would reject a valid hand-authored schema.
    """
    _, write_model = DEFINITION_TO_WRITE_MODEL[family]

    missing = REQUIRED_WRITE_FIELDS[family] - set(write_model.model_fields)
    assert not missing, f"{write_model.__name__} dropped settable fields: {sorted(missing)}"


@pytest.mark.parametrize("family", list(DEFINITION_TO_WRITE_MODEL))
def test_write_model_publishes_allowed_values(family: str) -> None:
    """No write-level constrained field is bare str/int; each publishes its allowed set."""
    definition, write_model = DEFINITION_TO_WRITE_MODEL[family]

    for field in definition.attributes:
        if field.visibility is not Visibility.WRITE or not field.enum:
            continue

        model_field = write_model.model_fields.get(field.name)
        assert model_field is not None, f"{write_model.__name__} is missing constrained field {field.name!r}"

        values = _allowed_values(model_field.annotation)
        assert values is not None, (
            f"{write_model.__name__}.{field.name} does not publish its allowed set; a bounded set is defined internally"
        )
        assert set(values) == set(field.enum), (
            f"{write_model.__name__}.{field.name} allowed values {sorted(values)} "
            f"do not match the internal set {sorted(field.enum)}"
        )


# Each generated write model paired with the read model of the same family. The read-only table
# consumed by the offline validator must be exactly the delta between the two.
WRITE_TO_READ_MODEL = {
    "attribute": (sdk_write.AttributeSchemaBaseWrite, sdk_read.AttributeSchemaBaseRead),
    "relationship": (sdk_write.RelationshipSchemaWrite, sdk_read.RelationshipSchemaRead),
    "base_node": (sdk_write.BaseNodeSchemaWrite, sdk_read.BaseNodeSchemaRead),
    "node": (sdk_write.NodeSchemaWrite, sdk_read.NodeSchemaRead),
    "generic": (sdk_write.GenericSchemaWrite, sdk_read.GenericSchemaRead),
}


def _declared_read_only_fields(model: type[BaseModel]) -> set[str]:
    """Read-only names the table declares for a model, including those it inherits."""
    names: set[str] = set()
    for klass in model.__mro__:
        names |= READ_ONLY_FIELDS.get(klass.__name__, frozenset())
    return names


@pytest.mark.parametrize("family", list(WRITE_TO_READ_MODEL))
def test_read_only_table_matches_the_read_write_delta(family: str) -> None:
    """The generated read-only table is exactly what the read model adds over the write model.

    The table decides whether an extra field in a submitted payload is a warning or an error, so a
    field appearing on read but missing from the table would be rejected instead of tolerated, and
    breaking the read-back, edit, re-load round trip.
    """
    write_model, read_model = WRITE_TO_READ_MODEL[family]

    # A computed field is part of the read payload even though it is not a model field.
    read_names = set(read_model.model_fields) | set(read_model.model_computed_fields)

    assert _declared_read_only_fields(write_model) == read_names - set(write_model.model_fields)


def test_attribute_kind_variants_partition_all_kinds() -> None:
    """The attribute union's variants together cover every attribute kind, without overlap.

    ``kind`` is the union discriminator, so each kind must resolve to exactly one variant; the
    variants' narrowed ``kind`` literals must partition the full internal set of attribute kinds.
    """
    union_members = typing.get_args(typing.get_args(sdk_write.AttributeSchemaWrite)[0])
    assert union_members, "AttributeSchemaWrite must be a non-empty discriminated union"

    seen: list[str] = []
    for variant in union_members:
        values = _allowed_values(variant.model_fields["kind"].annotation)
        assert values is not None, f"{variant.__name__}.kind must be a Literal of its supported kinds"
        seen.extend(values)

    assert sorted(seen) == sorted(ATTRIBUTE_KIND_LABELS), (
        f"variant kinds {sorted(seen)} do not cover the internal set {sorted(ATTRIBUTE_KIND_LABELS)}"
    )
    assert len(seen) == len(set(seen)), f"attribute kinds overlap across variants: {sorted(seen)}"
