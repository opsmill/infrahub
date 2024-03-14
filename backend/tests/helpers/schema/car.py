from infrahub.core.constants import RelationshipCardinality, RelationshipKind
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema
from tests.constants import TestKind

CAR = NodeSchema(
    name="Car",
    namespace="Testing",
    include_in_menu=True,
    label="Car",
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
            name="manufacturer",
            kind=RelationshipKind.ATTRIBUTE,
            optional=False,
            peer=TestKind.MANUFACTURER,
            cardinality=RelationshipCardinality.ONE,
            identifier="car__manufacturer",
        ),
    ],
)
