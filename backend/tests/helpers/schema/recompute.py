from infrahub.core.constants import ComputedAttributeKind, RelationshipCardinality
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema
from infrahub.core.schema.computed_attribute import ComputedAttribute

# Display label and hfid both read a computed attribute, so writing it cascades into both in one save.
CASCADE_NODE = NodeSchema(
    name="CascadeNode",
    namespace="Testing",
    label="Cascade Node",
    default_filter="name__value",
    display_label="{{ code__value }}",
    human_friendly_id=["code__value"],
    uniqueness_constraints=[["name__value"]],
    attributes=[
        AttributeSchema(name="name", kind="Text", optional=False, unique=True),
        AttributeSchema(
            name="code",
            kind="Text",
            optional=True,
            read_only=True,
            computed_attribute=ComputedAttribute(
                kind=ComputedAttributeKind.JINJA2, jinja2_template="{{ name__value }}"
            ),
        ),
    ],
)

# Two kinds whose computed summaries read each other across a relationship: a genuine cycle, stopped
# only by the recompute chain-depth bound.
CYCLE_A = NodeSchema(
    name="CycleA",
    namespace="Testing",
    label="Cycle A",
    default_filter="name__value",
    display_label="{{ name__value }}",
    uniqueness_constraints=[["name__value"]],
    attributes=[
        AttributeSchema(name="name", kind="Text", optional=False, unique=True),
        AttributeSchema(
            name="summary",
            kind="Text",
            optional=True,
            read_only=True,
            computed_attribute=ComputedAttribute(
                kind=ComputedAttributeKind.JINJA2, jinja2_template="{{ peer__summary__value }}"
            ),
        ),
    ],
    relationships=[
        RelationshipSchema(name="peer", optional=True, peer="TestingCycleB", cardinality=RelationshipCardinality.ONE),
    ],
)

CYCLE_B = NodeSchema(
    name="CycleB",
    namespace="Testing",
    label="Cycle B",
    default_filter="name__value",
    display_label="{{ name__value }}",
    uniqueness_constraints=[["name__value"]],
    attributes=[
        AttributeSchema(name="name", kind="Text", optional=False, unique=True),
        AttributeSchema(
            name="summary",
            kind="Text",
            optional=True,
            read_only=True,
            computed_attribute=ComputedAttribute(
                kind=ComputedAttributeKind.JINJA2, jinja2_template="{{ peer__summary__value }}"
            ),
        ),
    ],
    relationships=[
        RelationshipSchema(name="peer", optional=True, peer="TestingCycleA", cardinality=RelationshipCardinality.ONE),
    ],
)
