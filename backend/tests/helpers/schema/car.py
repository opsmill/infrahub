from infrahub.core.constants import RelationshipCardinality, RelationshipKind
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema
from tests.constants import TestKind

CAR = NodeSchema(
    name="Car",
    namespace="Testing",
    include_in_menu=True,
    label="Car",
    default_filter="name__value",
    display_labels=["name__value", "color__value"],
    attributes=[
        AttributeSchema(name="name", kind="Text"),
        AttributeSchema(name="description", kind="Text", optional=True),
        AttributeSchema(name="color", kind="Text"),
    ],
    relationships=[
        RelationshipSchema(
            name="owner",
            kind=RelationshipKind.ATTRIBUTE,
            optional=False,
            peer=TestKind.PERSON,
            cardinality=RelationshipCardinality.ONE,
        ),
        RelationshipSchema(
            name="previous_owner",
            kind=RelationshipKind.ATTRIBUTE,
            optional=True,
            peer=TestKind.PERSON,
            cardinality=RelationshipCardinality.ONE,
            identifier="testingcar__previousowners",
        ),
        RelationshipSchema(
            name="manufacturer",
            kind=RelationshipKind.ATTRIBUTE,
            optional=False,
            peer=TestKind.MANUFACTURER,
            cardinality=RelationshipCardinality.ONE,
            identifier="car__manufacturer",
        ),
    ],
)
