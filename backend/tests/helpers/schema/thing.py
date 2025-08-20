from infrahub.core.constants import ComputedAttributeKind, RelationshipCardinality, RelationshipKind
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema
from infrahub.core.schema.computed_attribute import ComputedAttribute
from tests.constants import TestKind

THING = NodeSchema(
    name="Thing",
    namespace="Testing",
    include_in_menu=True,
    label="Thing",
    default_filter="name__value",
    attributes=[
        AttributeSchema(name="name", kind="Text"),
        AttributeSchema(name="color", kind="Text"),
        AttributeSchema(
            name="description",
            kind="Text",
            read_only=True,
            computed_attribute=ComputedAttribute(
                kind=ComputedAttributeKind.JINJA2,
                jinja2_template="{{ owner__name__value }}'s {{ color__value }} {{ name__value }}",
            ),
        ),
    ],
    relationships=[
        RelationshipSchema(
            name="owner",
            kind=RelationshipKind.GENERIC,
            optional=False,
            peer=TestKind.CHILD,
            cardinality=RelationshipCardinality.ONE,
        )
    ],
)
