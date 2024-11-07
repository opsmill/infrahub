from infrahub.core.constants import RelationshipCardinality, RelationshipKind
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema
from tests.constants import TestKind

CHILD = NodeSchema(
    name="Child",
    namespace="Testing",
    include_in_menu=True,
    label="Child",
    default_filter="name__value",
    attributes=[
        AttributeSchema(name="name", kind="Text"),
        AttributeSchema(name="description", kind="Text", optional=True),
        AttributeSchema(name="height", kind="Number", optional=True),
        AttributeSchema(name="age", kind="Number", optional=True),
    ],
    relationships=[
        RelationshipSchema(
            name="things",
            kind=RelationshipKind.GENERIC,
            optional=True,
            peer=TestKind.THING,
            cardinality=RelationshipCardinality.MANY,
        )
    ],
)
