from __future__ import annotations

import enum
import types
import typing
from dataclasses import dataclass

import pytest
from infrahub_sdk.schema.generated import read as sdk_read
from infrahub_sdk.schema.generated import write as sdk_write
from infrahub_sdk.schema.generated.contract import READ_ONLY_FIELDS
from pydantic import BaseModel

from infrahub.core.constants import Visibility
from infrahub.core.schema.definitions.internal import (
    attribute_schema,
    base_node_schema,
    generic_schema,
    node_schema,
    relationship_schema,
)
from infrahub.types import ATTRIBUTE_KIND_LABELS

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


@dataclass(frozen=True)
class ReadOnlyDeltaCase:
    name: str
    write_model: type[BaseModel]
    read_model: type[BaseModel]


READ_ONLY_DELTA_CASES = [
    ReadOnlyDeltaCase(
        name="attribute",
        write_model=sdk_write.AttributeSchemaBaseWrite,
        read_model=sdk_read.AttributeSchemaBaseRead,
    ),
    ReadOnlyDeltaCase(
        name="relationship",
        write_model=sdk_write.RelationshipSchemaWrite,
        read_model=sdk_read.RelationshipSchemaRead,
    ),
    ReadOnlyDeltaCase(
        name="base_node",
        write_model=sdk_write.BaseNodeSchemaWrite,
        read_model=sdk_read.BaseNodeSchemaRead,
    ),
    ReadOnlyDeltaCase(
        name="node",
        write_model=sdk_write.NodeSchemaWrite,
        read_model=sdk_read.NodeSchemaRead,
    ),
    ReadOnlyDeltaCase(
        name="generic",
        write_model=sdk_write.GenericSchemaWrite,
        read_model=sdk_read.GenericSchemaRead,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(tc, id=tc.name) for tc in READ_ONLY_DELTA_CASES])
def test_read_only_table_matches_the_read_write_delta(case: ReadOnlyDeltaCase) -> None:
    """The generated read-only table is exactly what the read model adds over the write model.

    The table decides whether an extra field in a submitted payload is a warning or an error, so a
    field appearing on read but missing from the table would be rejected instead of tolerated, and
    breaking the read-back, edit, re-load round trip. Each entry resolves what the class inherits,
    so a consumer looks it up by name without walking the model hierarchy.
    """
    # A computed field is part of the read payload even though it is not a model field.
    read_names = set(case.read_model.model_fields) | set(case.read_model.model_computed_fields)

    assert READ_ONLY_FIELDS[case.write_model.__name__] == read_names - set(case.write_model.model_fields)


def test_read_only_table_entries_are_fully_resolved() -> None:
    """No generated write class inherits a read-only field its own table entry omits.

    The offline validator looks a class up by name alone. Were the generator to emit only a class's
    own read-only fields, an inherited one would fall through as an unknown field, turning a value
    that must be tolerated on a round trip into a hard error.
    """
    incomplete: dict[str, list[str]] = {}
    for obj in vars(sdk_write).values():
        if not (isinstance(obj, type) and issubclass(obj, BaseModel)):
            continue
        inherited: set[str] = set()
        for base in obj.__mro__[1:]:
            inherited |= READ_ONLY_FIELDS.get(base.__name__, frozenset())
        missing = inherited - READ_ONLY_FIELDS.get(obj.__name__, frozenset())
        if missing:
            incomplete[obj.__name__] = sorted(missing)

    assert incomplete == {}


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
