from infrahub.core.constants import RelationshipCardinality, RelationshipKind
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema
from tests.constants import TestKind

DEVICE = NodeSchema(
    name="Device",
    namespace="Testing",
    include_in_menu=True,
    label="Device",
    default_filter="name__value",
    generate_template=True,
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(name="manufacturer", kind="Text"),
        AttributeSchema(name="height", kind="Number", default_value=1),
        AttributeSchema(name="weight", kind="Number"),
        AttributeSchema(
            name="airflow",
            kind="Text",
            enum=[
                "Front to rear",
                "Rear to front",
                "Left to right",
                "Right to left",
                "Side to rear",
                "Rear to side",
                "Bottom to top",
                "Top to bottom",
                "Passive",
                "Mixed",
            ],
        ),
        AttributeSchema(name="part_number", kind="Text", optional=True),
    ],
    relationships=[
        RelationshipSchema(
            name="interfaces",
            kind=RelationshipKind.COMPONENT,
            optional=True,
            peer=TestKind.INTERFACE,
            cardinality=RelationshipCardinality.MANY,
        )
    ],
)

INTERFACE = NodeSchema(
    name="Interface",
    namespace="Testing",
    include_in_menu=True,
    label="Interface",
    default_filter="name__value",
    human_friendly_id=["device__name__value", "name__value"],
    uniqueness_constraints=[["device", "name__value"]],
    attributes=[
        AttributeSchema(name="name", kind="Text"),
        AttributeSchema(
            name="phys_type",
            kind="Text",
            enum=[
                "1000BASE-T (1GE)",
                "10GBASE-T (20GE)",
                "SFP (1GE)",
                "SFP+ (10GE)",
                "XFP (10GE)",
                "SFP28 (25GE)",
                "SFP56 (50GE)",
                "QSFP+ (40 GE)",
                "QSFP28 (100GE)",
                "Virtual",
            ],
        ),
        AttributeSchema(name="enabled", kind="Boolean", default_value=True),
    ],
    relationships=[
        RelationshipSchema(
            name="device",
            kind=RelationshipKind.PARENT,
            optional=False,
            peer=TestKind.DEVICE,
            cardinality=RelationshipCardinality.ONE,
        ),
        RelationshipSchema(
            name="sfp",
            kind=RelationshipKind.COMPONENT,
            optional=True,
            peer=TestKind.SFP,
            cardinality=RelationshipCardinality.ONE,
        ),
    ],
)

SFP = NodeSchema(
    name="Sfp",
    namespace="Testing",
    include_in_menu=True,
    label="SFP",
    human_friendly_id=["phys_type__value", "serial_number__value"],
    uniqueness_constraints=[["phys_type__value", "serial_number__value"]],
    attributes=[
        AttributeSchema(
            name="phys_type",
            kind="Text",
            enum=[
                "1000BASE-T (1GE)",
                "10GBASE-T (20GE)",
                "SFP (1GE)",
                "SFP+ (10GE)",
                "XFP (10GE)",
                "SFP28 (25GE)",
                "SFP56 (50GE)",
                "QSFP+ (40 GE)",
                "QSFP28 (100GE)",
            ],
        ),
        AttributeSchema(name="serial_number", kind="Text"),
        AttributeSchema(name="part_number", kind="Text", optional=True),
    ],
    relationships=[
        RelationshipSchema(
            name="interface",
            kind=RelationshipKind.PARENT,
            optional=False,
            peer=TestKind.INTERFACE,
            cardinality=RelationshipCardinality.ONE,
        )
    ],
)
