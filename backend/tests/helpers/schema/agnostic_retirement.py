from infrahub.core.constants import BranchSupportType, RelationshipCardinality, RelationshipKind
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot

RELATIONSHIP_IDENTIFIER = "agnosticretire_widget__agnosticretire_gadget"

WIDGET_KIND = "AgnosticretireWidget"
GADGET_KIND = "AgnosticretireGadget"
BEACON_KIND = "AgnosticretireBeacon"

AGNOSTIC_WIDGET = NodeSchema(
    name="Widget",
    namespace="Agnosticretire",
    branch=BranchSupportType.AWARE,
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(name="serial", kind="Number", branch=BranchSupportType.AGNOSTIC),
    ],
    relationships=[
        RelationshipSchema(
            name="gadget",
            kind=RelationshipKind.GENERIC,
            peer=GADGET_KIND,
            identifier=RELATIONSHIP_IDENTIFIER,
            cardinality=RelationshipCardinality.ONE,
            optional=True,
            branch=BranchSupportType.AGNOSTIC,
        ),
    ],
)

AGNOSTIC_GADGET = NodeSchema(
    name="Gadget",
    namespace="Agnosticretire",
    branch=BranchSupportType.AWARE,
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
)

# A kind that is itself branch-agnostic, so its own existence edge lives on the global branch.
AGNOSTIC_BEACON = NodeSchema(
    name="Beacon",
    namespace="Agnosticretire",
    branch=BranchSupportType.AGNOSTIC,
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(name="serial", kind="Number", optional=True),
    ],
)

AGNOSTIC_RETIREMENT_SCHEMA = SchemaRoot(nodes=[AGNOSTIC_WIDGET, AGNOSTIC_GADGET, AGNOSTIC_BEACON])
