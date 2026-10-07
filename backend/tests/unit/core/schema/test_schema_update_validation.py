from typing import Any

from infrahub.core.constants import UpdateValidationErrorType
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_parameters import (
    NumberPoolParameters,
    NumberPoolRangeParameters,
    TextAttributeParameters,
)
from infrahub.core.schema.schema_branch import SchemaBranch

WIDGET_GADGET_SCHEMA: dict[str, Any] = {
    "version": "1.0",
    "nodes": [
        {
            "name": "Widget",
            "namespace": "Test",
            "attributes": [{"name": "name", "kind": "Text", "unique": True}],
            "relationships": [
                {
                    "name": "gadgets",
                    "peer": "TestGadget",
                    "cardinality": "many",
                    "identifier": "widget__gadget",
                    "optional": True,
                }
            ],
        },
        {
            "name": "Gadget",
            "namespace": "Test",
            "attributes": [{"name": "name", "kind": "Text", "unique": True}],
        },
    ],
}


def _build_schema() -> SchemaBranch:
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**WIDGET_GADGET_SCHEMA))
    schema.process()
    return schema


async def test_relationship_identifier_update_is_not_supported() -> None:
    """Changing a relationship's identifier must be rejected rather than silently orphaning data."""
    schema = _build_schema()

    candidate = schema.duplicate()
    widget = candidate.get_node(name="TestWidget", duplicate=True)
    relationship = widget.get_relationship(name="gadgets")
    relationship.identifier = "widget__gadget_renamed"
    candidate.set(name="TestWidget", schema=widget)

    diff = schema.diff(other=candidate)
    result = schema.validate_update(other=candidate, diff=diff)

    assert len(result.errors) == 1
    error = result.errors[0]
    assert error.error == UpdateValidationErrorType.NOT_SUPPORTED
    assert error.path.schema_kind == "TestWidget"
    assert error.path.field_name == "gadgets"
    assert error.path.property_name == "identifier"
    assert result.migrations == []


async def test_schema_diff_constraint_scoped_to_changed_attribute() -> None:
    """A change to one attribute property emits only that attribute's constraint, not the kind's uniqueness constraint."""
    schema = _build_schema()

    candidate = schema.duplicate()
    widget = candidate.get_node(name="TestWidget", duplicate=True)
    parameters = widget.get_attribute(name="name").parameters
    assert isinstance(parameters, TextAttributeParameters)
    parameters.max_length = 20
    candidate.set(name="TestWidget", schema=widget)

    diff = schema.diff(other=candidate)
    result = schema.validate_update(other=candidate, diff=diff)

    constraint_names = {c.constraint_name for c in result.constraints}
    assert constraint_names
    assert "node.uniqueness_constraints.update" not in constraint_names
    # every emitted constraint is scoped to the single changed element
    assert all(c.path.schema_kind == "TestWidget" and c.path.field_name == "name" for c in result.constraints)


async def test_number_pool_ranges_change_emits_a_supported_constraint() -> None:
    """A change limited to the declared ranges of a NumberPool attribute is validated rather than refused."""
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(
        schema=SchemaRoot(
            version="1.0",
            nodes=[
                {
                    "name": "Widget",
                    "namespace": "Test",
                    "attributes": [
                        {"name": "name", "kind": "Text", "unique": True},
                        {
                            "name": "number",
                            "kind": "NumberPool",
                            "read_only": True,
                            "parameters": {"ranges": [{"start": 1, "end": 100}]},
                        },
                    ],
                }
            ],
        )
    )
    schema.process()

    candidate = schema.duplicate()
    widget = candidate.get_node(name="TestWidget", duplicate=True)
    parameters = widget.get_attribute(name="number").parameters
    assert isinstance(parameters, NumberPoolParameters)
    parameters.ranges = [NumberPoolRangeParameters(start=1, end=50), NumberPoolRangeParameters(start=80, end=100)]
    candidate.set(name="TestWidget", schema=widget)

    diff = schema.diff(other=candidate)
    result = schema.validate_update(other=candidate, diff=diff)

    assert result.errors == []
    assert [c.constraint_name for c in result.constraints] == ["attribute.parameters.ranges.update"]
    assert result.constraints[0].path.property_name == "parameters.ranges"
