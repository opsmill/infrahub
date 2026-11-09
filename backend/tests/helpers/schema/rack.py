from infrahub.core.constants import RelationshipCardinality, RelationshipDirection
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema

# A rack reaches a card through a slot: ``slots`` peers the generic ``Slot`` and ``card`` is a
# relationship defined on that generic, so a card is reached through a relationship whose owner is a
# generic.
SLOT = GenericSchema(
    name="Slot",
    namespace="Testing",
    attributes=[AttributeSchema(name="name", kind="Text")],
    relationships=[
        RelationshipSchema(
            name="card",
            peer="TestingCard",
            identifier="slot__card",
            cardinality=RelationshipCardinality.ONE,
            optional=True,
            direction=RelationshipDirection.OUTBOUND,
        )
    ],
)

POWER_SLOT = NodeSchema(name="PowerSlot", namespace="Testing", inherit_from=["TestingSlot"])

CARD = NodeSchema(
    name="Card",
    namespace="Testing",
    attributes=[AttributeSchema(name="name", kind="Text")],
)

RACK = NodeSchema(
    name="Rack",
    namespace="Testing",
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    relationships=[
        RelationshipSchema(
            name="slots",
            peer="TestingSlot",
            identifier="rack__slot",
            cardinality=RelationshipCardinality.MANY,
            optional=True,
            direction=RelationshipDirection.OUTBOUND,
        )
    ],
)
