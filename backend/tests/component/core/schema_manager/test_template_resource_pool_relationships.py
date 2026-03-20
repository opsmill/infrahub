from infrahub.core.constants import (
    InfrahubKind,
    RelationshipCardinality,
    RelationshipKind,
)
from infrahub.core.constants.schema import RESOURCE_POOL_REL_SUFFIX
from infrahub.core.schema import (
    AttributeSchema,
    NodeSchema,
    RelationshipSchema,
    SchemaRoot,
    core_models,
)
from infrahub.core.schema.schema_branch import SchemaBranch


async def test_manage_object_templates_with_resource_pool_relationships() -> None:
    """Test that resource pool relationships are created for IP address and prefix relationships.

    This test verifies that resource pool relationships are created for:
    1. Relationships to custom schemas that inherit from BuiltinIPAddress/BuiltinIPPrefix
    2. Relationships directly to the BuiltinIPAddress/BuiltinIPPrefix generics
    """
    schema_branch = SchemaBranch(cache={}, name="test")

    # Create a test schema with IP address and prefix nodes
    test_schema = SchemaRoot(
        nodes=[
            NodeSchema(
                name="IPAddress",
                namespace="Ipam",
                inherit_from=["BuiltinIPAddress"],
            ),
            NodeSchema(
                name="IPPrefix",
                namespace="Ipam",
                inherit_from=["BuiltinIPPrefix"],
            ),
            NodeSchema(
                name="Device",
                namespace="Infra",
                generate_template=True,
                attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
                relationships=[
                    RelationshipSchema(
                        name="address",
                        peer="IpamIPAddress",
                        label="Primary IP Address",
                        cardinality=RelationshipCardinality.ONE,
                    ),
                    RelationshipSchema(
                        name="prefix",
                        peer="IpamIPPrefix",
                        label="Management Prefix",
                        cardinality=RelationshipCardinality.ONE,
                    ),
                ],
            ),
            NodeSchema(
                name="Server",
                namespace="Infra",
                generate_template=True,
                attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
                relationships=[
                    RelationshipSchema(
                        name="ip_address",
                        peer="BuiltinIPAddress",
                        label="IP Address",
                        cardinality=RelationshipCardinality.ONE,
                    ),
                    RelationshipSchema(
                        name="ip_prefix",
                        peer="BuiltinIPPrefix",
                        label="IP Prefix",
                        cardinality=RelationshipCardinality.ONE,
                    ),
                ],
            ),
        ]
    )

    schema_branch.load_schema(schema=SchemaRoot(**core_models).merge(schema=test_schema))
    schema_branch.generate_identifiers()
    schema_branch.process_inheritance()
    schema_branch.manage_object_template_schemas()
    schema_branch.manage_object_template_relationships()

    # Get the template schemas
    device_template = schema_branch.get_template("TemplateInfraDevice", duplicate=False)
    server_template = schema_branch.get_template("TemplateInfraServer", duplicate=False)

    # Test 1: Verify relationships to custom schemas that inherit from BuiltinIP*
    # Verify the original relationships exist
    address_rel = device_template.get_relationship("address")
    assert address_rel.peer == "IpamIPAddress"
    assert address_rel.cardinality == RelationshipCardinality.ONE

    prefix_rel = device_template.get_relationship("prefix")
    assert prefix_rel.peer == "IpamIPPrefix"
    assert prefix_rel.cardinality == RelationshipCardinality.ONE

    # Verify the resource pool relationships exist
    address_pool_rel = device_template.get_relationship("address_from_resource_pool")
    assert address_pool_rel.peer == InfrahubKind.IPADDRESSPOOL
    assert address_pool_rel.cardinality == RelationshipCardinality.ONE
    assert address_pool_rel.optional is True

    prefix_pool_rel = device_template.get_relationship("prefix_from_resource_pool")
    assert prefix_pool_rel.peer == InfrahubKind.IPPREFIXPOOL
    assert prefix_pool_rel.cardinality == RelationshipCardinality.ONE
    assert prefix_pool_rel.optional is True

    # Test 2: Verify relationships directly to BuiltinIPAddress/BuiltinIPPrefix generics
    # Verify the original relationships exist
    ip_address_rel = server_template.get_relationship("ip_address")
    assert ip_address_rel.peer == "BuiltinIPAddress"
    assert ip_address_rel.cardinality == RelationshipCardinality.ONE

    ip_prefix_rel = server_template.get_relationship("ip_prefix")
    assert ip_prefix_rel.peer == "BuiltinIPPrefix"
    assert ip_prefix_rel.cardinality == RelationshipCardinality.ONE

    # Verify the resource pool relationships exist
    ip_address_pool_rel = server_template.get_relationship("ip_address_from_resource_pool")
    assert ip_address_pool_rel.peer == InfrahubKind.IPADDRESSPOOL
    assert ip_address_pool_rel.cardinality == RelationshipCardinality.ONE
    assert ip_address_pool_rel.optional is True

    ip_prefix_pool_rel = server_template.get_relationship("ip_prefix_from_resource_pool")
    assert ip_prefix_pool_rel.peer == InfrahubKind.IPPREFIXPOOL
    assert ip_prefix_pool_rel.cardinality == RelationshipCardinality.ONE
    assert ip_prefix_pool_rel.optional is True


async def test_number_attribute_generates_pool_relationship() -> None:
    """Test that Number attributes on templates get _from_resource_pool relationships to CoreNumberPool."""
    schema_branch = SchemaBranch(cache={}, name="test")

    test_schema = SchemaRoot(
        nodes=[
            NodeSchema(
                name="Device",
                namespace="Infra",
                generate_template=True,
                attributes=[
                    AttributeSchema(name="name", kind="Text", unique=True),
                    AttributeSchema(name="vlan_id", kind="Number"),
                    AttributeSchema(name="asn", kind="Number"),
                    AttributeSchema(name="unique_number", kind="Number", unique=True),
                    AttributeSchema(name="read_only_number", kind="Number", read_only=True),
                    AttributeSchema(name="description", kind="Text"),
                    AttributeSchema(name="active", kind="Boolean"),
                ],
            ),
        ]
    )

    schema_branch.load_schema(schema=SchemaRoot(**core_models).merge(schema=test_schema))
    schema_branch.generate_identifiers()
    schema_branch.process_inheritance()
    schema_branch.manage_object_template_schemas()
    schema_branch.manage_object_template_relationships()

    device_template = schema_branch.get_template("TemplateInfraDevice", duplicate=False)

    resource_pool_rel_names = {
        r_name for r_name in device_template.relationship_names if r_name.endswith(RESOURCE_POOL_REL_SUFFIX)
    }
    assert resource_pool_rel_names == {f"vlan_id{RESOURCE_POOL_REL_SUFFIX}", f"asn{RESOURCE_POOL_REL_SUFFIX}"}

    # Verify pool relationships exist for both Number attributes
    vlan_pool_rel = device_template.get_relationship("vlan_id_from_resource_pool")
    assert vlan_pool_rel.peer == InfrahubKind.NUMBERPOOL
    assert vlan_pool_rel.cardinality == RelationshipCardinality.ONE
    assert vlan_pool_rel.optional is True
    assert vlan_pool_rel.kind == RelationshipKind.GENERIC

    asn_pool_rel = device_template.get_relationship("asn_from_resource_pool")
    assert asn_pool_rel.peer == InfrahubKind.NUMBERPOOL
    assert asn_pool_rel.cardinality == RelationshipCardinality.ONE
    assert asn_pool_rel.optional is True
    assert asn_pool_rel.kind == RelationshipKind.GENERIC
