from infrahub.core.constants import RelationshipCardinality, RelationshipKind
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema

from tests.constants import TestKind

MANUFACTURER = NodeSchema(
    name="Manufacturer",
    namespace="Testing",
    include_in_menu=True,
    label="Manufacturer",
    attributes=[
        AttributeSchema(name="name", kind="Text"),
        AttributeSchema(name="description", kind="Text", optional=True),
    ],
    relationships=[
        RelationshipSchema(
            name="cars",
            kind=RelationshipKind.GENERIC,
            optional=True,
            peer=TestKind.CAR,
            cardinality=RelationshipCardinality.MANY,
            identifier="car__manufacturer",
        ),
        RelationshipSchema(
            name="customers",
            kind=RelationshipKind.GENERIC,
            optional=True,
            peer=TestKind.PERSON,
            cardinality=RelationshipCardinality.MANY,
            identifier="person__manufacturer",
        ),
    ],
)
