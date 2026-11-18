from infrahub.core.constants import RelationshipCardinality, RelationshipKind
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema, SchemaRoot

NAME_ATTRIBUTE = AttributeSchema(name="name", kind="Text", unique=True)

# A site has a hierarchy parent only, a device has a Parent relationship only, and a rack has both.
# Only a site has an object template, because the template of a kind with a Parent relationship needs one for the parent.
OWNERSHIP_SCHEMA = SchemaRoot(
    generics=[GenericSchema(name="Location", namespace="Test", hierarchical=True, attributes=[NAME_ATTRIBUTE])],
    nodes=[
        NodeSchema(name="Site", namespace="Test", inherit_from=["TestLocation"], generate_template=True),
        NodeSchema(name="Tenant", namespace="Test", attributes=[NAME_ATTRIBUTE]),
        NodeSchema(
            name="Rack",
            namespace="Test",
            inherit_from=["TestLocation"],
            relationships=[
                RelationshipSchema(
                    name="tenant",
                    peer="TestTenant",
                    kind=RelationshipKind.PARENT,
                    optional=False,
                    cardinality=RelationshipCardinality.ONE,
                )
            ],
        ),
        NodeSchema(
            name="Device",
            namespace="Test",
            attributes=[NAME_ATTRIBUTE],
            relationships=[
                RelationshipSchema(
                    name="rack",
                    peer="TestRack",
                    kind=RelationshipKind.PARENT,
                    optional=False,
                    cardinality=RelationshipCardinality.ONE,
                )
            ],
        ),
    ],
)
