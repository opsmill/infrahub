from infrahub.core.constants import RelationshipCardinality, RelationshipKind
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema
from tests.constants import TestKind

INTERFACE_HOLDER = GenericSchema(
    name="InterfaceHolder",
    namespace="Testing",
    include_in_menu=False,
    label="Interface Holder",
    relationships=[
        RelationshipSchema(
            name="interfaces",
            kind=RelationshipKind.COMPONENT,
            optional=True,
            peer=TestKind.INTERFACE,
            cardinality=RelationshipCardinality.MANY,
            identifier="interfaceholder__interfaces",
        )
    ],
)


INTERFACE = GenericSchema(
    name="Interface",
    namespace="Testing",
    include_in_menu=False,
    label="Interface",
    default_filter="name__value",
    uniqueness_constraints=[["device", "name__value"]],
    attributes=[
        AttributeSchema(name="name", kind="Text"),
        AttributeSchema(name="enabled", kind="Boolean", default_value=True),
    ],
    relationships=[
        RelationshipSchema(
            name="device",
            kind=RelationshipKind.PARENT,
            optional=False,
            peer=TestKind.INTERFACE_HOLDER,
            cardinality=RelationshipCardinality.ONE,
            identifier="interfaceholder__interfaces",
        )
    ],
)

DEVICE = NodeSchema(
    name="Device",
    namespace="Testing",
    inherit_from=[TestKind.INTERFACE_HOLDER],
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
            name="primary_ip", peer="IpamIPAddress", cardinality=RelationshipCardinality.ONE, optional=True
        )
    ],
)

PHYSICAL_INTERFACE = NodeSchema(
    name="PhysicalInterface",
    namespace="Testing",
    inherit_from=[TestKind.INTERFACE],
    include_in_menu=True,
    label="Physical Interface",
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
                "Virtual",
            ],
        )
    ],
    relationships=[
        RelationshipSchema(
            name="sfp",
            kind=RelationshipKind.COMPONENT,
            optional=True,
            peer=TestKind.SFP,
            cardinality=RelationshipCardinality.ONE,
        )
    ],
)

VIRTUAL_INTERFACE = NodeSchema(
    name="VirtualInterface",
    namespace="Testing",
    inherit_from=[TestKind.INTERFACE],
    include_in_menu=True,
    label="Virtual Interface",
)

LAG_INTERFACE = NodeSchema(
    name="LinkAggegrationInterface",
    namespace="Testing",
    inherit_from=[TestKind.INTERFACE],
    include_in_menu=True,
    label="LAG Interface",
    relationships=[
        RelationshipSchema(
            name="members",
            kind=RelationshipKind.COMPONENT,
            optional=True,
            peer=TestKind.PHYSICAL_INTERFACE,
            cardinality=RelationshipCardinality.MANY,
            common_parent="device",
        )
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
            peer=TestKind.PHYSICAL_INTERFACE,
            cardinality=RelationshipCardinality.ONE,
        )
    ],
)
