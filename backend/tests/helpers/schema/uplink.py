from infrahub.core.constants import (
    BranchSupportType,
    RelationshipCardinality,
    RelationshipDeleteBehavior,
    RelationshipDirection,
)
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema, SchemaRoot

UPLINK_TARGET_KIND = "UplinkTarget"
UPLINK_CORE_KIND = "UplinkCore"
UPLINK_SWITCH_KIND = "UplinkSwitch"
UPLINK_ROUTER_KIND = "UplinkRouter"

UPLINK_TARGET = GenericSchema(
    name="Target",
    namespace="Uplink",
    branch=BranchSupportType.AGNOSTIC,
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
)

UPLINK_CORE = NodeSchema(
    name="Core",
    namespace="Uplink",
    branch=BranchSupportType.AGNOSTIC,
    inherit_from=[UPLINK_TARGET_KIND],
)

# Both relationships share one identifier and only the outbound one is required; the optional one is declared first.
UPLINK_SWITCH = NodeSchema(
    name="Switch",
    namespace="Uplink",
    branch=BranchSupportType.AGNOSTIC,
    inherit_from=[UPLINK_TARGET_KIND],
    relationships=[
        RelationshipSchema(
            name="downstream",
            peer=UPLINK_SWITCH_KIND,
            identifier="uplink_switch__uplink",
            direction=RelationshipDirection.INBOUND,
            cardinality=RelationshipCardinality.MANY,
            optional=True,
        ),
        RelationshipSchema(
            name="upstream",
            peer=UPLINK_TARGET_KIND,
            identifier="uplink_switch__uplink",
            direction=RelationshipDirection.OUTBOUND,
            cardinality=RelationshipCardinality.ONE,
            optional=False,
        ),
    ],
)

# Both relationships share one identifier and only the inbound one cascades.
UPLINK_ROUTER = NodeSchema(
    name="Router",
    namespace="Uplink",
    branch=BranchSupportType.AWARE,
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    relationships=[
        RelationshipSchema(
            name="downstream",
            peer=UPLINK_ROUTER_KIND,
            identifier="uplink_router__uplink",
            direction=RelationshipDirection.INBOUND,
            cardinality=RelationshipCardinality.MANY,
            optional=True,
            on_delete=RelationshipDeleteBehavior.CASCADE,
        ),
        RelationshipSchema(
            name="upstream",
            peer=UPLINK_ROUTER_KIND,
            identifier="uplink_router__uplink",
            direction=RelationshipDirection.OUTBOUND,
            cardinality=RelationshipCardinality.ONE,
            optional=True,
        ),
    ],
)

UPLINK_SCHEMA = SchemaRoot(generics=[UPLINK_TARGET], nodes=[UPLINK_CORE, UPLINK_SWITCH, UPLINK_ROUTER])
