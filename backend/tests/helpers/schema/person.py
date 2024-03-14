from infrahub.core.constants import RelationshipCardinality, RelationshipKind
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema
from tests.constants import TestKind

PERSON = NodeSchema(
    name="Person",
    namespace="Testing",
    include_in_menu=True,
    label="Person",
    default_filter="name__value",
    attributes=[
        AttributeSchema(name="name", kind="Text"),
        AttributeSchema(name="description", kind="Text", optional=True),
        AttributeSchema(name="height", kind="Number", optional=True),
    ],
    relationships=[
        RelationshipSchema(
            name="cars",
            kind=RelationshipKind.GENERIC,
            optional=True,
            peer=TestKind.CAR,
            cardinality=RelationshipCardinality.MANY,
        )
    ],
)
