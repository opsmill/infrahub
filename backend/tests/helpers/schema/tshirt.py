from infrahub.core.constants import ComputedAttributeKind, RelationshipCardinality
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema
from infrahub.core.schema.computed_attribute import ComputedAttribute
from tests.constants import TestKind

TSHIRT = NodeSchema(
    name="TShirt",
    namespace="Testing",
    include_in_menu=True,
    label="T-shirt",
    default_filter="name__value",
    display_labels=["name__value"],
    attributes=[
        AttributeSchema(name="name", kind="Text"),
        AttributeSchema(
            name="description",
            kind="Text",
            optional=False,
            read_only=True,
            computed_attribute=ComputedAttribute(
                kind=ComputedAttributeKind.JINJA2,
                jinja2_template="A {{color__name__value }} {{ name__value}} t-shirt. {{ color__description__value }}",
            ),
        ),
    ],
    relationships=[
        RelationshipSchema(
            name="color",
            optional=False,
            peer=TestKind.COLOR,
            cardinality=RelationshipCardinality.ONE,
        )
    ],
)
