from infrahub.core.constants import BranchSupportType, RelationshipCardinality, RelationshipDeleteBehavior
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot

LOOP_FIRST_KIND = "CascadeloopFirst"
LOOP_SECOND_KIND = "CascadeloopSecond"

# Each kind cascades to the other, so a chain of nodes alternating between them is deleted in one cascade.
LOOP_FIRST = NodeSchema(
    name="First",
    namespace="Cascadeloop",
    branch=BranchSupportType.AWARE,
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    relationships=[
        RelationshipSchema(
            name="next",
            peer=LOOP_SECOND_KIND,
            identifier="cascadeloop_first__cascadeloop_second",
            cardinality=RelationshipCardinality.ONE,
            optional=True,
            on_delete=RelationshipDeleteBehavior.CASCADE,
        ),
    ],
)

LOOP_SECOND = NodeSchema(
    name="Second",
    namespace="Cascadeloop",
    branch=BranchSupportType.AWARE,
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    relationships=[
        RelationshipSchema(
            name="next",
            peer=LOOP_FIRST_KIND,
            identifier="cascadeloop_second__cascadeloop_first",
            cardinality=RelationshipCardinality.ONE,
            optional=True,
            on_delete=RelationshipDeleteBehavior.CASCADE,
        ),
    ],
)

CASCADE_LOOP_SCHEMA = SchemaRoot(nodes=[LOOP_FIRST, LOOP_SECOND])
