import pytest

from infrahub.core.constants import (
    BranchSupportType,
    RelationshipCardinality,
    RelationshipDirection,
    RelationshipKind,
)
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot


@pytest.fixture
def car_person_schema_root() -> SchemaRoot:
    car = NodeSchema(
        name="Car",
        namespace="Test",
        default_filter="name__value",
        display_label="{{ name__value }} {{ color__value }}",
        uniqueness_constraints=[["name__value"]],
        branch=BranchSupportType.AWARE,
        attributes=[
            AttributeSchema(name="name", kind="Text", unique=True),
            AttributeSchema(name="nbr_seats", kind="Number", optional=True),
            AttributeSchema(name="color", kind="Text", default_value="#444444", max_length=7, optional=True),
            AttributeSchema(name="is_electric", kind="Boolean", optional=True),
            AttributeSchema(
                name="transmission",
                kind="Text",
                optional=True,
                enum=["manual", "automatic", "flintstone-feet"],
            ),
        ],
        relationships=[
            RelationshipSchema(
                name="owner",
                label="Commander of Car",
                peer="TestPerson",
                optional=False,
                kind=RelationshipKind.PARENT,
                cardinality=RelationshipCardinality.ONE,
                direction=RelationshipDirection.OUTBOUND,
            ),
            RelationshipSchema(
                name="driver",
                label="Commander of Car",
                peer="TestPerson",
                optional=True,
                cardinality=RelationshipCardinality.ONE,
                identifier="cars_driven__driver",
            ),
        ],
    )
    person = NodeSchema(
        name="Person",
        namespace="Test",
        default_filter="name__value",
        display_label="name__value",
        branch=BranchSupportType.AWARE,
        uniqueness_constraints=[["name__value"]],
        attributes=[
            AttributeSchema(name="name", kind="Text", unique=True),
            AttributeSchema(name="height", kind="Number", optional=True),
        ],
        relationships=[
            RelationshipSchema(
                name="cars",
                peer="TestCar",
                cardinality=RelationshipCardinality.MANY,
                direction=RelationshipDirection.INBOUND,
            ),
            RelationshipSchema(
                name="cars_driven",
                peer="TestCar",
                cardinality=RelationshipCardinality.MANY,
                identifier="cars_driven__driver",
            ),
        ],
    )
    return SchemaRoot(nodes=[car, person])
