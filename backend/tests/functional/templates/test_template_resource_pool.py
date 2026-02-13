from __future__ import annotations

from ipaddress import IPv4Interface, IPv4Network, IPv6Interface, IPv6Network, ip_network
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.exceptions import GraphQLError

from infrahub.core.constants import InfrahubKind, MetadataOptions, RelationshipCardinality, RelationshipKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.node import InfrahubNode

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


CREATE_DEVICE_FROM_TEMPLATE = """
mutation CreateDeviceFromTemplate($name: String!, $template_id: String!) {
    InfraDeviceCreate(
        data: {
            name: { value: $name }
            object_template: { id: $template_id }
        }
    ) {
        ok
        object { id }
    }
}
"""

CREATE_RACK_FROM_TEMPLATE = """
mutation CreateRackFromTemplate($name: String!, $template_id: String!) {
    InfraRackCreate(
        data: {
            name: { value: $name }
            object_template: { id: $template_id }
        }
    ) {
        ok
        object { id }
    }
}
"""


class TestTemplateResourcePoolCreation(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def device_schema(self, db: InfrahubDatabase, initialize_registry: None) -> None:
        schema = SchemaRoot(
            version="1.0",
            nodes=[
                NodeSchema(name="IPAddress", namespace="Ipam", inherit_from=["BuiltinIPAddress"]),
                NodeSchema(name="IPPrefix", namespace="Ipam", inherit_from=["BuiltinIPPrefix"]),
                NodeSchema(
                    name="Device",
                    namespace="Infra",
                    generate_template=True,
                    attributes=[
                        AttributeSchema(name="name", kind="Text", unique=True),
                        AttributeSchema(name="description", kind="Text", optional=True),
                    ],
                    relationships=[
                        RelationshipSchema(
                            name="primary_address",
                            peer="IpamIPAddress",
                            label="Primary IP Address",
                            cardinality=RelationshipCardinality.ONE,
                            optional=True,
                        ),
                    ],
                ),
            ],
        )
        await load_schema(db, schema=schema, update_db=True)

    @pytest.fixture(scope="class")
    async def ip_namespace(self, db: InfrahubDatabase, device_schema: None) -> Node:
        ns = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
        await ns.new(db=db, name="test-namespace")
        await ns.save(db=db)
        return ns

    @pytest.fixture(scope="class")
    async def ip_prefix(self, db: InfrahubDatabase, ip_namespace: Node, device_schema: None) -> Node:
        prefix = await Node.init(db=db, schema="IpamIPPrefix")
        await prefix.new(db=db, prefix="10.20.30.0/24", ip_namespace=ip_namespace)
        await prefix.save(db=db)
        return prefix

    @pytest.fixture(scope="class")
    async def ip_address_pool(
        self, db: InfrahubDatabase, ip_namespace: Node, ip_prefix: Node, device_schema: None
    ) -> Node:
        pool = await Node.init(db=db, schema=InfrahubKind.IPADDRESSPOOL)
        await pool.new(
            db=db,
            name="test-address-pool",
            resources=[ip_prefix],
            ip_namespace=ip_namespace,
            default_address_type="IpamIPAddress",
        )
        await pool.save(db=db)
        return pool

    @pytest.fixture(scope="class")
    async def static_ip_address(
        self, db: InfrahubDatabase, ip_namespace: Node, ip_prefix: Node, device_schema: None
    ) -> Node:
        address = await Node.init(db=db, schema="IpamIPAddress")
        await address.new(db=db, address="10.20.30.100/24", ip_prefix=ip_prefix, ip_namespace=ip_namespace)
        await address.save(db=db)
        return address

    @pytest.fixture(scope="class")
    async def template_with_static_address(
        self, db: InfrahubDatabase, static_ip_address: Node, device_schema: None
    ) -> Node:
        template = await Node.init(db=db, schema="TemplateInfraDevice")
        await template.new(
            db=db,
            template_name="device-static-address",
            description="Template with static address",
            primary_address=static_ip_address,
        )
        await template.save(db=db)
        return template

    @pytest.fixture(scope="class")
    async def template_with_pool(self, db: InfrahubDatabase, ip_address_pool: Node, device_schema: None) -> Node:
        template = await Node.init(db=db, schema="TemplateInfraDevice")
        await template.new(
            db=db,
            template_name="device-pool-address",
            description="Template with pool allocation",
            primary_address_from_resource_pool=ip_address_pool,
        )
        await template.save(db=db)
        return template

    async def test_template_schema_has_pool_relationship(
        self, client: InfrahubClient, device_schema: None, default_branch: Branch
    ) -> None:
        template_schema = await client.schema.get(kind="TemplateInfraDevice")
        assert template_schema

        assert "primary_address" in template_schema.relationship_names
        assert "primary_address_from_resource_pool" in template_schema.relationship_names

        pool_rel = next(
            rel for rel in template_schema.relationships if rel.name == "primary_address_from_resource_pool"
        )
        assert pool_rel.peer == InfrahubKind.IPADDRESSPOOL
        assert pool_rel.optional

    async def test_template_with_pool_created(
        self, db: InfrahubDatabase, template_with_pool: Node, ip_address_pool: Node
    ) -> None:
        template = await NodeManager.get_one(id=template_with_pool.id, db=db)
        assert template.template_name.value == "device-pool-address"
        pool_peer = await template.primary_address_from_resource_pool.get_peer(db=db)
        assert pool_peer.id == ip_address_pool.id
        addr_peer = await template.primary_address.get_peer(db=db)
        assert addr_peer is None

    async def test_device_from_template_with_static_address(
        self, db: InfrahubDatabase, template_with_static_address: Node, static_ip_address: Node, client: InfrahubClient
    ) -> None:
        create_result = await client.execute_graphql(
            query=CREATE_DEVICE_FROM_TEMPLATE,
            variables={"name": "device-from-static-template", "template_id": template_with_static_address.id},
        )
        device_id = create_result["InfraDeviceCreate"]["object"]["id"]

        device = await NodeManager.get_one(id=device_id, db=db)
        assert device.name.value == "device-from-static-template"
        addr_peer = await device.primary_address.get_peer(db=db)
        assert addr_peer.id == static_ip_address.id

    async def test_device_from_template_with_pool_allocates_address(
        self, db: InfrahubDatabase, template_with_pool: Node, client: InfrahubClient
    ) -> None:
        create_result = await client.execute_graphql(
            query=CREATE_DEVICE_FROM_TEMPLATE,
            variables={"name": "device-from-pool-template", "template_id": template_with_pool.id},
        )
        device_id = create_result["InfraDeviceCreate"]["object"]["id"]

        device = await NodeManager.get_one(id=device_id, db=db)
        assert device.name.value == "device-from-pool-template"

        addr_peer = await device.primary_address.get_peer(db=db)
        assert addr_peer is not None
        assert addr_peer.address.value is not None
        assert IPv4Interface(addr_peer.address.value).ip in ip_network("10.20.30.0/24")

    async def test_device_from_pool_template_explicit_address_overrides(
        self,
        db: InfrahubDatabase,
        template_with_pool: Node,
        ip_namespace: Node,
        ip_prefix: Node,
        client: InfrahubClient,
    ) -> None:
        address = await Node.init(db=db, schema="IpamIPAddress")
        await address.new(db=db, address="10.20.30.200/24", ip_prefix=ip_prefix, ip_namespace=ip_namespace)
        await address.save(db=db)

        create_result = await client.execute_graphql(
            query="""
            mutation CreateDeviceWithAddress($name: String!, $template_id: String!, $address_id: String!) {
                InfraDeviceCreate(
                    data: {
                        name: { value: $name }
                        object_template: { id: $template_id }
                        primary_address: { id: $address_id }
                    }
                ) {
                    ok
                    object { id }
                }
            }
            """,
            variables={
                "name": "device-with-explicit-address",
                "template_id": template_with_pool.id,
                "address_id": address.id,
            },
        )
        device_id = create_result["InfraDeviceCreate"]["object"]["id"]

        device = await NodeManager.get_one(id=device_id, db=db)
        addr_peer = await device.primary_address.get_peer(db=db)
        assert addr_peer.id == address.id

    async def test_multiple_devices_from_pool_template_get_unique_addresses(
        self, db: InfrahubDatabase, template_with_pool: Node, client: InfrahubClient
    ) -> None:
        result1 = await client.execute_graphql(
            query=CREATE_DEVICE_FROM_TEMPLATE,
            variables={"name": "device-pool-unique-1", "template_id": template_with_pool.id},
        )
        device1_id = result1["InfraDeviceCreate"]["object"]["id"]

        result2 = await client.execute_graphql(
            query=CREATE_DEVICE_FROM_TEMPLATE,
            variables={"name": "device-pool-unique-2", "template_id": template_with_pool.id},
        )
        device2_id = result2["InfraDeviceCreate"]["object"]["id"]

        device1 = await NodeManager.get_one(id=device1_id, db=db)
        device2 = await NodeManager.get_one(id=device2_id, db=db)

        addr1_peer = await device1.primary_address.get_peer(db=db)
        addr2_peer = await device2.primary_address.get_peer(db=db)
        assert addr1_peer.id != addr2_peer.id
        assert addr1_peer.address.value != addr2_peer.address.value

    async def test_template_cannot_set_both_direct_and_pool_on_create(
        self,
        static_ip_address: Node,
        ip_address_pool: Node,
        client: InfrahubClient,
    ) -> None:
        with pytest.raises(GraphQLError) as exc:
            await client.execute_graphql(
                query="""
                mutation CreateTemplateWithBoth($address_id: String!, $pool_id: String!) {
                    TemplateInfraDeviceCreate(
                        data: {
                            template_name: { value: "device-both-relationships" }
                            primary_address: { id: $address_id }
                            primary_address_from_resource_pool: { id: $pool_id }
                        }
                    ) {
                        ok
                        object { id }
                    }
                }
                """,
                variables={"address_id": static_ip_address.id, "pool_id": ip_address_pool.id},
            )

        assert "Cannot set 'primary_address' when 'primary_address_from_resource_pool' is already set" in str(exc.value)

    async def test_template_cannot_add_pool_when_direct_exists(
        self, db: InfrahubDatabase, ip_address_pool: Node, ip_namespace: Node, ip_prefix: Node, client: InfrahubClient
    ) -> None:
        address = await Node.init(db=db, schema="IpamIPAddress")
        await address.new(db=db, address="10.20.30.150/24", ip_prefix=ip_prefix, ip_namespace=ip_namespace)
        await address.save(db=db)

        template = await Node.init(db=db, schema="TemplateInfraDevice")
        await template.new(db=db, template_name="device-direct-then-pool", primary_address=address)
        await template.save(db=db)

        with pytest.raises(GraphQLError) as exc:
            await client.execute_graphql(
                query="""
                mutation AddPoolToTemplate($id: String!, $pool_id: String!) {
                    TemplateInfraDeviceUpdate(
                        data: {
                            id: $id
                            primary_address_from_resource_pool: { id: $pool_id }
                        }
                    ) {
                        ok
                        object { id }
                    }
                }
                """,
                variables={"id": template.id, "pool_id": ip_address_pool.id},
            )

        assert "Templates can only use one of: direct relationship or resource pool allocation" in str(exc.value)

    async def test_template_cannot_add_direct_when_pool_exists(
        self, db: InfrahubDatabase, static_ip_address: Node, ip_address_pool: Node, client: InfrahubClient
    ) -> None:
        template = await Node.init(db=db, schema="TemplateInfraDevice")
        await template.new(
            db=db, template_name="device-pool-then-direct", primary_address_from_resource_pool=ip_address_pool
        )
        await template.save(db=db)

        with pytest.raises(GraphQLError) as exc:
            await client.execute_graphql(
                query="""
                mutation AddDirectToTemplate($id: String!, $address_id: String!) {
                    TemplateInfraDeviceUpdate(
                        data: {
                            id: $id
                            primary_address: { id: $address_id }
                        }
                    ) {
                        ok
                        object { id }
                    }
                }
                """,
                variables={"id": template.id, "address_id": static_ip_address.id},
            )

        assert "Templates can only use one of: direct relationship or resource pool allocation" in str(exc.value)

    async def test_template_can_add_direct_when_pool_is_unset(
        self, db: InfrahubDatabase, static_ip_address: Node, ip_address_pool: Node, client: InfrahubClient
    ) -> None:
        template = await Node.init(db=db, schema="TemplateInfraDevice")
        await template.new(
            db=db, template_name="device-pool-replaced-by-direct", primary_address_from_resource_pool=ip_address_pool
        )
        await template.save(db=db)

        update_result = await client.execute_graphql(
            query="""
            mutation SwapPoolToDirect($id: String!, $address_id: String!) {
                TemplateInfraDeviceUpdate(
                    data: {
                        id: $id
                        primary_address_from_resource_pool: null
                        primary_address: { id: $address_id }
                    }
                ) {
                    ok
                    object {
                        id
                        primary_address { node { id } }
                        primary_address_from_resource_pool { node { id } }
                    }
                }
            }
            """,
            variables={"id": template.id, "address_id": static_ip_address.id},
        )
        updated = update_result["TemplateInfraDeviceUpdate"]["object"]
        assert updated["primary_address"]["node"]["id"] == static_ip_address.id
        assert updated["primary_address_from_resource_pool"]["node"] is None

    async def test_template_can_add_pool_when_direct_is_unset(
        self, db: InfrahubDatabase, static_ip_address: Node, ip_address_pool: Node, client: InfrahubClient
    ) -> None:
        template = await Node.init(db=db, schema="TemplateInfraDevice")
        await template.new(db=db, template_name="device-direct-replaced-by-pool", primary_address=static_ip_address)
        await template.save(db=db)

        update_result = await client.execute_graphql(
            query="""
            mutation SwapDirectToPool($id: String!, $pool_id: String!) {
                TemplateInfraDeviceUpdate(
                    data: {
                        id: $id
                        primary_address: null
                        primary_address_from_resource_pool: { id: $pool_id }
                    }
                ) {
                    ok
                    object {
                        id
                        primary_address { node { id } }
                        primary_address_from_resource_pool { node { id } }
                    }
                }
            }
            """,
            variables={"id": template.id, "pool_id": ip_address_pool.id},
        )
        updated = update_result["TemplateInfraDeviceUpdate"]["object"]
        assert updated["primary_address"]["node"] is None
        assert updated["primary_address_from_resource_pool"]["node"]["id"] == ip_address_pool.id


class TestTemplateNumberPoolAttributes(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def device_schema(self, db: InfrahubDatabase, initialize_registry: None) -> None:
        schema = SchemaRoot(
            version="1.0",
            nodes=[
                NodeSchema(
                    name="Rack",
                    namespace="Infra",
                    generate_template=True,
                    attributes=[
                        AttributeSchema(name="name", kind="Text", unique=True),
                        AttributeSchema(name="location", kind="Text", optional=True),
                        AttributeSchema(name="slot_id", kind="Number", optional=True),
                    ],
                ),
            ],
        )
        await load_schema(db, schema=schema, update_db=True)

    @pytest.fixture(scope="class")
    async def slot_pool(self, db: InfrahubDatabase, device_schema: None) -> Node:
        pool = await Node.init(db=db, schema=InfrahubKind.NUMBERPOOL)
        await pool.new(
            db=db,
            name="slot-pool",
            node="InfraRack",
            node_attribute="slot_id",
            start_range=1,
            end_range=100,
        )
        await pool.save(db=db)
        return pool

    @pytest.fixture(scope="class")
    async def template_with_static_slot(self, db: InfrahubDatabase, device_schema: None) -> Node:
        template = await Node.init(db=db, schema="TemplateInfraRack")
        await template.new(db=db, template_name="rack-static-slot", location="datacenter-1", slot_id=50)
        await template.save(db=db)
        return template

    @pytest.fixture(scope="class")
    async def template_with_pool_slot(
        self, client: InfrahubClient, slot_pool: Node, device_schema: None
    ) -> InfrahubNode:
        sdk_pool = await client.get(kind=InfrahubKind.NUMBERPOOL, id=slot_pool.id)
        template = await client.create(
            kind="TemplateInfraRack",
            template_name="rack-pool-slot",
            location="datacenter-1",
            slot_id=sdk_pool,
        )
        await template.save()
        return template

    async def test_template_with_pool_stores_reference_not_value(
        self, db: InfrahubDatabase, template_with_pool_slot: InfrahubNode
    ) -> None:
        """Template with from_pool should store reference without allocating a value."""
        template = await NodeManager.get_one(id=template_with_pool_slot.id, db=db)
        assert template.template_name.value == "rack-pool-slot"
        assert template.slot_id.value is None

    async def test_rack_from_template_with_static_slot(
        self, db: InfrahubDatabase, template_with_static_slot: Node, client: InfrahubClient
    ) -> None:
        """Static value from template should have the template as source."""
        create_result = await client.execute_graphql(
            query=CREATE_RACK_FROM_TEMPLATE,
            variables={"name": "rack-from-static-template", "template_id": template_with_static_slot.id},
        )
        rack_id = create_result["InfraRackCreate"]["object"]["id"]

        rack = await NodeManager.get_one(id=rack_id, db=db, include_metadata=MetadataOptions.SOURCE)
        assert rack.name.value == "rack-from-static-template"
        assert rack.slot_id.value == 50
        assert rack.slot_id.source_id == template_with_static_slot.id

    async def test_rack_from_template_with_pool_allocates_slot(
        self, db: InfrahubDatabase, template_with_pool_slot: InfrahubNode, slot_pool: Node, client: InfrahubClient
    ) -> None:
        """Object created from template should allocate from pool."""
        create_result = await client.execute_graphql(
            query=CREATE_RACK_FROM_TEMPLATE,
            variables={"name": "rack-from-pool-template", "template_id": template_with_pool_slot.id},
        )
        rack_id = create_result["InfraRackCreate"]["object"]["id"]

        rack = await NodeManager.get_one(id=rack_id, db=db, include_metadata=MetadataOptions.SOURCE)
        assert rack.name.value == "rack-from-pool-template"
        assert rack.slot_id.value is not None
        assert 1 <= rack.slot_id.value <= 100
        assert rack.slot_id.source_id == slot_pool.id

    async def test_rack_explicit_slot_overrides_pool_template(
        self, db: InfrahubDatabase, template_with_pool_slot: InfrahubNode, client: InfrahubClient
    ) -> None:
        """User-provided slot value should override pool allocation."""
        create_result = await client.execute_graphql(
            query="""
            mutation CreateRackWithSlot($name: String!, $template_id: String!, $slot_id: BigInt!) {
                InfraRackCreate(
                    data: {
                        name: { value: $name }
                        object_template: { id: $template_id }
                        slot_id: { value: $slot_id }
                    }
                ) {
                    ok
                    object { id }
                }
            }
            """,
            variables={
                "name": "rack-with-explicit-slot",
                "template_id": template_with_pool_slot.id,
                "slot_id": 999,
            },
        )
        rack_id = create_result["InfraRackCreate"]["object"]["id"]

        rack = await NodeManager.get_one(id=rack_id, db=db)
        assert rack.slot_id.value == 999

    async def test_multiple_racks_from_pool_template_get_unique_slots(
        self, db: InfrahubDatabase, template_with_pool_slot: InfrahubNode, client: InfrahubClient
    ) -> None:
        """Multiple objects from same pool template should get unique slot allocations."""
        result1 = await client.execute_graphql(
            query=CREATE_RACK_FROM_TEMPLATE,
            variables={"name": "rack-pool-unique-1", "template_id": template_with_pool_slot.id},
        )
        rack1_id = result1["InfraRackCreate"]["object"]["id"]

        result2 = await client.execute_graphql(
            query=CREATE_RACK_FROM_TEMPLATE,
            variables={"name": "rack-pool-unique-2", "template_id": template_with_pool_slot.id},
        )
        rack2_id = result2["InfraRackCreate"]["object"]["id"]

        rack1 = await NodeManager.get_one(id=rack1_id, db=db)
        rack2 = await NodeManager.get_one(id=rack2_id, db=db)
        assert rack1.slot_id.value is not None
        assert rack2.slot_id.value is not None
        assert rack1.slot_id.value != rack2.slot_id.value


class TestTemplateNestedComponentPoolAllocations(TestInfrahubApp):
    """End-to-end test for pool allocations in templates with nested component relationships.

    Schema:
    - Device: has management IP (from IP address pool) and rack_unit (from number pool)
    - Interface: component of Device, has VLAN (from number pool) and prefix (from prefix pool)

    Template:
    - Device template with 8 interface templates
    - Creates multiple devices and verifies all allocations are unique with correct sources
    """

    @pytest.fixture(scope="class")
    async def device_schema(self, db: InfrahubDatabase, initialize_registry: None) -> None:
        schema = SchemaRoot(
            version="1.0",
            nodes=[
                NodeSchema(name="IPAddress", namespace="Ipam", inherit_from=["BuiltinIPAddress"]),
                NodeSchema(name="IPPrefix", namespace="Ipam", inherit_from=["BuiltinIPPrefix"]),
                NodeSchema(
                    name="Device",
                    namespace="Infra",
                    generate_template=True,
                    attributes=[
                        AttributeSchema(name="name", kind="Text", unique=True),
                        AttributeSchema(name="rack_unit", kind="Number", optional=True),
                    ],
                    relationships=[
                        RelationshipSchema(
                            name="mgmt_address",
                            peer="IpamIPAddress",
                            cardinality=RelationshipCardinality.ONE,
                            optional=True,
                        ),
                        RelationshipSchema(
                            name="interfaces",
                            peer="InfraInterface",
                            cardinality=RelationshipCardinality.MANY,
                            kind=RelationshipKind.COMPONENT,
                            optional=True,
                        ),
                    ],
                ),
                NodeSchema(
                    name="Interface",
                    namespace="Infra",
                    attributes=[
                        AttributeSchema(name="name", kind="Text"),
                        AttributeSchema(name="vlan_id", kind="Number", optional=True),
                    ],
                    relationships=[
                        RelationshipSchema(
                            name="device",
                            peer="InfraDevice",
                            cardinality=RelationshipCardinality.ONE,
                            kind=RelationshipKind.PARENT,
                            optional=False,
                        ),
                        RelationshipSchema(
                            name="prefix", peer="IpamIPPrefix", cardinality=RelationshipCardinality.ONE, optional=True
                        ),
                    ],
                ),
            ],
        )
        await load_schema(db, schema=schema, update_db=True)

    @pytest.fixture(scope="class")
    async def ip_namespace(self, db: InfrahubDatabase, device_schema: None) -> Node:
        ns = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
        await ns.new(db=db, name="all-pools-namespace")
        await ns.save(db=db)
        return ns

    @pytest.fixture(scope="class")
    async def mgmt_prefix(self, db: InfrahubDatabase, ip_namespace: Node) -> Node:
        """Management IP prefix: 10.0.0.0/24 for device management addresses."""
        prefix = await Node.init(db=db, schema="IpamIPPrefix")
        await prefix.new(db=db, prefix="10.0.0.0/24", ip_namespace=ip_namespace)
        await prefix.save(db=db)
        return prefix

    @pytest.fixture(scope="class")
    async def mgmt_address_pool(self, db: InfrahubDatabase, ip_namespace: Node, mgmt_prefix: Node) -> Node:
        """IP Address Pool for device management IPs."""
        pool = await Node.init(db=db, schema=InfrahubKind.IPADDRESSPOOL)
        await pool.new(
            db=db,
            name="mgmt-address-pool",
            resources=[mgmt_prefix],
            ip_namespace=ip_namespace,
            default_address_type="IpamIPAddress",
        )
        await pool.save(db=db)
        return pool

    @pytest.fixture(scope="class")
    async def interface_supernet(self, db: InfrahubDatabase, ip_namespace: Node) -> Node:
        """Supernet for interface prefixes: 172.16.0.0/16."""
        prefix = await Node.init(db=db, schema="IpamIPPrefix")
        await prefix.new(db=db, prefix="172.16.0.0/16", ip_namespace=ip_namespace, is_pool=True)
        await prefix.save(db=db)
        return prefix

    @pytest.fixture(scope="class")
    async def interface_prefix_pool(self, db: InfrahubDatabase, ip_namespace: Node, interface_supernet: Node) -> Node:
        """IP Prefix Pool for interface /30 prefixes."""
        pool = await Node.init(db=db, schema=InfrahubKind.IPPREFIXPOOL)
        await pool.new(
            db=db,
            name="interface-prefix-pool",
            resources=[interface_supernet],
            ip_namespace=ip_namespace,
            default_prefix_length=30,
            default_prefix_type="IpamIPPrefix",
        )
        await pool.save(db=db)
        return pool

    @pytest.fixture(scope="class")
    async def vlan_pool(self, db: InfrahubDatabase, device_schema: None) -> Node:
        """Number Pool for VLAN IDs (100-999)."""
        pool = await Node.init(db=db, schema=InfrahubKind.NUMBERPOOL)
        await pool.new(
            db=db,
            name="vlan-pool",
            node="InfraInterface",
            node_attribute="vlan_id",
            start_range=100,
            end_range=999,
        )
        await pool.save(db=db)
        return pool

    @pytest.fixture(scope="class")
    async def rack_unit_pool(self, db: InfrahubDatabase, device_schema: None) -> Node:
        """Number Pool for device rack units (1-48)."""
        pool = await Node.init(db=db, schema=InfrahubKind.NUMBERPOOL)
        await pool.new(
            db=db,
            name="rack-unit-pool",
            node="InfraDevice",
            node_attribute="rack_unit",
            start_range=1,
            end_range=48,
        )
        await pool.save(db=db)
        return pool

    @pytest.fixture(scope="class")
    async def device_template_with_interfaces(
        self,
        client: InfrahubClient,
        mgmt_address_pool: Node,
        interface_prefix_pool: Node,
        vlan_pool: Node,
        rack_unit_pool: Node,
    ) -> InfrahubNode:
        """Device template with 8 interface templates, all using pool allocations."""
        sdk_rack_pool = await client.get(kind=InfrahubKind.NUMBERPOOL, id=rack_unit_pool.id)
        sdk_vlan_pool = await client.get(kind=InfrahubKind.NUMBERPOOL, id=vlan_pool.id)

        device_template = await client.create(
            kind="TemplateInfraDevice",
            template_name="device-with-8-interfaces",
            mgmt_address_from_resource_pool=mgmt_address_pool.id,
            rack_unit=sdk_rack_pool,
        )
        await device_template.save()

        for i in range(8):
            interface_template = await client.create(
                kind="TemplateInfraInterface",
                template_name=f"interface-eth{i}",
                name=f"eth{i}",
                vlan_id=sdk_vlan_pool,
                device=device_template,
                prefix_from_resource_pool=interface_prefix_pool.id,
            )
            await interface_template.save()

        return device_template

    async def test_templates_store_pool_references_not_values(
        self, device_template_with_interfaces: InfrahubNode, client: InfrahubClient
    ) -> None:
        """Templates should store pool references without allocating values."""
        device_template = await client.get(kind="TemplateInfraDevice", id=device_template_with_interfaces.id)
        assert device_template.rack_unit.value is None, "Device template should not have allocated rack_unit"

        interface_templates = await client.all(kind="TemplateInfraInterface")
        assert len(interface_templates) == 8
        for iface_template in interface_templates:
            assert iface_template.vlan_id.value is None, "Interface template should not have allocated vlan_id"

    async def test_devices_from_template_get_unique_allocations(
        self,
        device_template_with_interfaces: InfrahubNode,
        mgmt_address_pool: Node,
        rack_unit_pool: Node,
        vlan_pool: Node,
        interface_prefix_pool: Node,
        client: InfrahubClient,
    ) -> None:
        """Each device from template should get unique allocations from all pool types."""
        device_ids = []
        for i in range(3):
            device = await client.create(
                kind="InfraDevice",
                name=f"device-all-pools-{i}",
                object_template=device_template_with_interfaces.id,
            )
            await device.save()
            device_ids.append(device.id)

        # Collect all allocated values across devices and interfaces
        mgmt_addresses: set[IPv4Interface | IPv6Interface] = set()
        rack_units: set[int] = set()
        vlans: set[int] = set()
        prefixes: set[IPv4Network | IPv6Network] = set()

        for device_id in device_ids:
            device = await client.get(kind="InfraDevice", id=device_id, include=["rack_unit"], property=True)

            # Device management address from IP pool
            await device.mgmt_address.fetch()
            assert device.mgmt_address.peer is not None, "Device should have management address from IP pool"
            assert device.mgmt_address.source == mgmt_address_pool.id, (
                f"Management address source should be the IP address pool, got {device.mgmt_address.source}"
            )
            mgmt_addr = await client.get(kind="IpamIPAddress", id=device.mgmt_address.peer.id)
            mgmt_addresses.add(mgmt_addr.address.value)

            # Device rack_unit from number pool
            assert device.rack_unit.value is not None, "Device should have rack_unit from number pool"
            assert device.rack_unit.source.id == rack_unit_pool.id, (
                f"rack_unit source should be the number pool, got {device.rack_unit.source}"
            )
            rack_units.add(device.rack_unit.value)

            # Interface attributes from pools
            interfaces = await client.filters(kind="InfraInterface", device__ids=[device_id], property=True)
            assert len(interfaces) == 8, "Device should have 8 interfaces from template"

            for iface in interfaces:
                # Interface VLAN from number pool
                assert iface.vlan_id.value is not None, "Interface should have vlan_id from number pool"
                assert iface.vlan_id.source.id == vlan_pool.id, (
                    f"vlan_id source should be the VLAN number pool, got {iface.vlan_id.source}"
                )
                vlans.add(iface.vlan_id.value)

                # Interface prefix from IP prefix pool
                await iface.prefix.fetch()
                assert iface.prefix.peer is not None, "Interface should have prefix from IP prefix pool"
                assert iface.prefix.source == interface_prefix_pool.id, (
                    f"Interface prefix source should be the IP prefix pool, got {iface.prefix.source}"
                )
                prefix = await client.get(kind="IpamIPPrefix", id=iface.prefix.peer.id)
                prefixes.add(prefix.prefix.value)

        # Each device gets unique allocations
        assert len(mgmt_addresses) == 3, "Each device should have unique management address"
        assert len(rack_units) == 3, "Each device should have unique rack_unit"

        # Each interface across all devices gets unique allocations
        assert len(vlans) == 24, "Each interface should have unique VLAN (3 devices x 8 interfaces)"
        assert len(prefixes) == 24, "Each interface should have unique prefix (3 devices x 8 interfaces)"
