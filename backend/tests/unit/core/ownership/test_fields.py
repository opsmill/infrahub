from dataclasses import dataclass

import pytest

from infrahub.core.constants import RelationshipCardinality
from infrahub.core.ownership.fields import (
    field_owners_holder,
    holder_from_field_name,
    stored_holder_field_name,
)
from infrahub.core.ownership.models import (
    NODE_HOLDER,
    NODE_SOURCES_HOLDER,
    NODE_TARGET_HOLDER,
    HolderKey,
    HolderKind,
    field_holder,
)
from infrahub.core.schema import (
    AttributeSchema,
    MainSchemaTypes,
    NodeSchema,
    RelationshipSchema,
    SchemaRoot,
    TemplateSchema,
)
from infrahub.core.schema.schema_branch import SchemaBranch

SCHEMA = SchemaRoot(
    nodes=[
        NodeSchema(
            name="Device",
            namespace="Test",
            attributes=[AttributeSchema(name="name", kind="Text")],
            relationships=[
                RelationshipSchema(name="tags", peer="BuiltinTag", cardinality=RelationshipCardinality.MANY),
            ],
        ),
        NodeSchema(name="Tag", namespace="Builtin", attributes=[AttributeSchema(name="name", kind="Text")]),
    ],
)
TEMPLATE = TemplateSchema(name="TestDevice", namespace="Template")
"""An object template of the device kind, which gives owners to the fields of the devices."""


@pytest.fixture(scope="module")
def schema_branch() -> SchemaBranch:
    schema_branch = SchemaBranch(cache={}, name="main")
    schema_branch.load_schema(schema=SCHEMA)
    schema_branch.process()
    return schema_branch


@dataclass
class RoundTripTestCase:
    name: str
    field_name: str
    target: bool = False
    """True for a holder of the owners that an object template gives."""
    field: str | None = None
    """The attribute or the relationship of the holder, and None for a holder of the node."""


ROUND_TRIP_TEST_CASES = [
    RoundTripTestCase(name="node", field_name="node_metadata__owners"),
    RoundTripTestCase(name="node_target", field_name="node_metadata__target_owners", target=True),
    RoundTripTestCase(name="node_sources", field_name="node_metadata__sources"),
    RoundTripTestCase(name="relationship", field_name="tags__owners", field="tags"),
    RoundTripTestCase(name="relationship_target", field_name="tags__target_owners", target=True, field="tags"),
    RoundTripTestCase(name="attribute_target", field_name="name__target_owners", target=True, field="name"),
]


def _holder(test_case: RoundTripTestCase, schema_branch: SchemaBranch) -> HolderKey:
    if test_case.field is None:
        return {"node": NODE_HOLDER, "node_target": NODE_TARGET_HOLDER, "node_sources": NODE_SOURCES_HOLDER}[
            test_case.name
        ]
    holder = field_holder(
        schema=schema_branch.get(name="TestDevice", duplicate=False),
        field_name=test_case.field,
        target=test_case.target,
    )
    assert holder is not None
    return holder


def _schema(test_case: RoundTripTestCase, schema_branch: SchemaBranch) -> MainSchemaTypes:
    return TEMPLATE if test_case.target else schema_branch.get(name="TestDevice", duplicate=False)


def _holder_of_name(field_name: str, schema: MainSchemaTypes, schema_branch: SchemaBranch) -> HolderKey | None:
    return holder_from_field_name(field_name=field_name) or field_owners_holder(
        field_name=field_name, schema=schema, schema_branch=schema_branch
    )


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in ROUND_TRIP_TEST_CASES])
def test_holder_and_field_name_map_to_each_other(test_case: RoundTripTestCase, schema_branch: SchemaBranch) -> None:
    holder = _holder(test_case=test_case, schema_branch=schema_branch)
    schema = _schema(test_case=test_case, schema_branch=schema_branch)

    field_name = stored_holder_field_name(holder=holder, schema=schema, schema_branch=schema_branch)
    assert field_name == test_case.field_name
    assert _holder_of_name(field_name=field_name, schema=schema, schema_branch=schema_branch) == holder


def test_owners_of_an_attribute_have_no_reserved_field_name(schema_branch: SchemaBranch) -> None:
    schema = schema_branch.get(name="TestDevice", duplicate=False)
    holder = HolderKey(kind=HolderKind.ATTRIBUTE, attribute="name")

    assert stored_holder_field_name(holder=holder, schema=schema, schema_branch=schema_branch) is None
    assert _holder_of_name(field_name="name", schema=schema, schema_branch=schema_branch) is None
    assert _holder_of_name(field_name="name__owners", schema=schema, schema_branch=schema_branch) is None
