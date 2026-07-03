from __future__ import annotations

import types
import typing

import pytest
from infrahub_sdk.schema.generated import write as sdk_write

from infrahub.core.constants import Visibility
from infrahub.core.schema.definitions.internal import (
    attribute_schema,
    base_node_schema,
    generic_schema,
    node_schema,
    relationship_schema,
)

# Map each schema-definition family to the generated SDK *write* model it produces.
DEFINITION_TO_WRITE_MODEL = {
    "attribute": (attribute_schema, sdk_write.GeneratedAttributeSchema),
    "relationship": (relationship_schema, sdk_write.GeneratedRelationshipSchema),
    "base_node": (base_node_schema, sdk_write.GeneratedBaseNodeSchema),
    "node": (node_schema, sdk_write.GeneratedNodeSchema),
    "generic": (generic_schema, sdk_write.GeneratedGenericSchema),
}


def _literal_values(annotation: typing.Any) -> tuple[typing.Any, ...] | None:
    """Return the values of a ``Literal[...]`` annotation, unwrapping an optional union.

    Returns None when the annotation is not (optionally) a ``Literal``.
    """
    origin = typing.get_origin(annotation)
    if origin is typing.Literal:
        return typing.get_args(annotation)

    # Unwrap ``X | None`` / ``Optional[X]`` and look for a Literal member.
    if origin in {typing.Union, types.UnionType}:
        for arg in typing.get_args(annotation):
            values = _literal_values(arg)
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

        values = _literal_values(model_field.annotation)
        assert values is not None, (
            f"{write_model.__name__}.{field.name} is not a Literal; a bounded set is defined internally"
        )
        assert set(values) == set(field.enum), (
            f"{write_model.__name__}.{field.name} allowed values {sorted(values)} "
            f"do not match the internal set {sorted(field.enum)}"
        )
