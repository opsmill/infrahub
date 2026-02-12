from __future__ import annotations

from ipaddress import ip_network
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.exceptions import GraphQLError

from infrahub.core.constants import InfrahubKind
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.node.node import InfrahubNode

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


class TestTemplateResourcePoolCreation(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def load_schema(self, db: InfrahubDatabase, initialize_registry: None, client: InfrahubClient) -> None:
        schema = {
            "version": "1.0",
            "nodes": [
                {"name": "IPAddress", "namespace": "Ipam", "inherit_from": ["BuiltinIPAddress"]},
                {"name": "IPPrefix", "namespace": "Ipam", "inherit_from": ["BuiltinIPPrefix"]},
                {
                    "name": "Device",
                    "namespace": "Infra",
                    "generate_template": True,
                    "attributes": [
                        {"name": "name", "kind": "Text", "unique": True},
                        {"name": "description", "kind": "Text", "optional": True},
                    ],
                    "relationships": [
                        {
                            "name": "primary_address",
                            "peer": "IpamIPAddress",
                            "label": "Primary IP Address",
                            "cardinality": "one",
                            "optional": True,
                        },
                    ],
                },
            ],
        }
        response = await client.schema.load(schemas=[schema])
        assert response.schema_updated
        assert not response.errors

    @pytest.fixture(scope="class")
    async def ip_namespace(self, client: InfrahubClient, load_schema: None) -> InfrahubNode:
        ns = await client.create(kind=InfrahubKind.NAMESPACE, name="test-namespace")
        await ns.save()
        return ns

    @pytest.fixture(scope="class")
    async def ip_prefix(self, client: InfrahubClient, ip_namespace: InfrahubNode, load_schema: None) -> InfrahubNode:
        prefix = await client.create(kind="IpamIPPrefix", prefix="10.20.30.0/24", ip_namespace=ip_namespace.id)
        await prefix.save()
        return prefix

    @pytest.fixture(scope="class")
    async def ip_address_pool(
        self, client: InfrahubClient, ip_namespace: InfrahubNode, ip_prefix: InfrahubNode, load_schema: None
    ) -> InfrahubNode:
        pool = await client.create(
            kind=InfrahubKind.IPADDRESSPOOL,
            name="test-address-pool",
            resources=[ip_prefix.id],
            ip_namespace=ip_namespace.id,
            default_address_type="IpamIPAddress",
        )
        await pool.save()
        return pool

    @pytest.fixture(scope="class")
    async def static_ip_address(
        self, client: InfrahubClient, ip_namespace: InfrahubNode, ip_prefix: InfrahubNode, load_schema: None
    ) -> InfrahubNode:
        address = await client.create(
            kind="IpamIPAddress", address="10.20.30.100/24", ip_prefix=ip_prefix.id, ip_namespace=ip_namespace.id
        )
        await address.save()
        return address

    @pytest.fixture(scope="class")
    async def template_with_static_address(
        self, client: InfrahubClient, static_ip_address: InfrahubNode, load_schema: None
    ) -> InfrahubNode:
        template = await client.create(
            kind="TemplateInfraDevice",
            template_name="device-static-address",
            description="Template with static address",
            primary_address=static_ip_address.id,
        )
        await template.save()
        return template

    @pytest.fixture(scope="class")
    async def template_with_pool(
        self, client: InfrahubClient, ip_address_pool: InfrahubNode, load_schema: None
    ) -> InfrahubNode:
        template = await client.create(
            kind="TemplateInfraDevice",
            template_name="device-pool-address",
            description="Template with pool allocation",
            primary_address_from_resource_pool=ip_address_pool.id,
        )
        await template.save()
        return template

    async def test_template_schema_has_pool_relationship(
        self, client: InfrahubClient, load_schema: None, default_branch: Branch
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
        self, template_with_pool: InfrahubNode, ip_address_pool: InfrahubNode, client: InfrahubClient
    ) -> None:
        retrieved = await client.get(kind="TemplateInfraDevice", id=template_with_pool.id)
        assert retrieved.template_name.value == "device-pool-address"

        await retrieved.primary_address_from_resource_pool.fetch()
        assert retrieved.primary_address_from_resource_pool.peer is not None
        assert retrieved.primary_address_from_resource_pool.peer.id == ip_address_pool.id
        assert retrieved.primary_address.id is None

    async def test_device_from_template_with_static_address(
        self, template_with_static_address: InfrahubNode, static_ip_address: InfrahubNode, client: InfrahubClient
    ) -> None:
        device = await client.create(
            kind="InfraDevice",
            name="device-from-static-template",
            object_template=template_with_static_address.id,
        )
        await device.save()

        retrieved = await client.get(kind="InfraDevice", id=device.id)
        assert retrieved.name.value == "device-from-static-template"

        await retrieved.primary_address.fetch()
        assert retrieved.primary_address.peer is not None
        assert retrieved.primary_address.peer.id == static_ip_address.id

    async def test_device_from_template_with_pool_allocates_address(
        self, template_with_pool: InfrahubNode, ip_address_pool: InfrahubNode, client: InfrahubClient
    ) -> None:
        device = await client.create(
            kind="InfraDevice", name="device-from-pool-template", object_template=template_with_pool.id
        )
        await device.save()

        retrieved = await client.get(kind="InfraDevice", id=device.id, property=True)
        assert retrieved.name.value == "device-from-pool-template"

        await retrieved.primary_address.fetch()
        assert retrieved.primary_address.peer is not None

        address_peer = await client.get(kind="IpamIPAddress", id=retrieved.primary_address.peer.id)
        assert address_peer.address.value is not None
        assert address_peer.address.value.ip in ip_network("10.20.30.0/24")

    async def test_device_from_pool_template_explicit_address_overrides(
        self,
        template_with_pool: InfrahubNode,
        ip_namespace: InfrahubNode,
        ip_prefix: InfrahubNode,
        client: InfrahubClient,
    ) -> None:
        explicit_address = await client.create(
            kind="IpamIPAddress",
            address="10.20.30.200/24",
            ip_prefix=ip_prefix.id,
            ip_namespace=ip_namespace.id,
        )
        await explicit_address.save()

        device = await client.create(
            kind="InfraDevice",
            name="device-with-explicit-address",
            object_template=template_with_pool.id,
            primary_address=explicit_address.id,
        )
        await device.save()

        retrieved = await client.get(kind="InfraDevice", id=device.id)

        await retrieved.primary_address.fetch()
        assert retrieved.primary_address.peer is not None
        assert retrieved.primary_address.peer.id == explicit_address.id

    async def test_multiple_devices_from_pool_template_get_unique_addresses(
        self, template_with_pool: InfrahubNode, client: InfrahubClient
    ) -> None:
        device1 = await client.create(
            kind="InfraDevice", name="device-pool-unique-1", object_template=template_with_pool.id
        )
        await device1.save()

        device2 = await client.create(
            kind="InfraDevice", name="device-pool-unique-2", object_template=template_with_pool.id
        )
        await device2.save()

        retrieved1 = await client.get(kind="InfraDevice", id=device1.id)
        retrieved2 = await client.get(kind="InfraDevice", id=device2.id)

        await retrieved1.primary_address.fetch()
        await retrieved2.primary_address.fetch()

        assert retrieved1.primary_address.peer is not None
        assert retrieved2.primary_address.peer is not None
        assert retrieved1.primary_address.peer.id != retrieved2.primary_address.peer.id

        addr1 = await client.get(kind="IpamIPAddress", id=retrieved1.primary_address.peer.id)
        addr2 = await client.get(kind="IpamIPAddress", id=retrieved2.primary_address.peer.id)
        assert addr1.address.value != addr2.address.value

    async def test_template_cannot_set_both_direct_and_pool_on_create(
        self,
        static_ip_address: InfrahubNode,
        ip_address_pool: InfrahubNode,
        client: InfrahubClient,
    ) -> None:
        template = await client.create(
            kind="TemplateInfraDevice",
            template_name="device-both-relationships",
            primary_address=static_ip_address.id,
            primary_address_from_resource_pool=ip_address_pool.id,
        )

        with pytest.raises(GraphQLError) as exc:
            await template.save()

        assert "Cannot set 'primary_address' when 'primary_address_from_resource_pool' is already set" in str(exc.value)

    async def test_template_cannot_add_pool_when_direct_exists(
        self,
        static_ip_address: InfrahubNode,
        ip_address_pool: InfrahubNode,
        ip_namespace: InfrahubNode,
        ip_prefix: InfrahubNode,
        client: InfrahubClient,
    ) -> None:
        another_address = await client.create(
            kind="IpamIPAddress", address="10.20.30.150/24", ip_prefix=ip_prefix.id, ip_namespace=ip_namespace.id
        )
        await another_address.save()

        template = await client.create(
            kind="TemplateInfraDevice",
            template_name="device-direct-then-pool",
            primary_address=another_address.id,
        )
        await template.save()

        retrieved = await client.get(kind="TemplateInfraDevice", id=template.id)
        retrieved.primary_address_from_resource_pool = ip_address_pool.id

        with pytest.raises(GraphQLError) as exc:
            await retrieved.update()

        assert "Templates can only use one of: direct relationship or resource pool allocation" in str(exc.value)

    async def test_template_cannot_add_direct_when_pool_exists(
        self,
        static_ip_address: InfrahubNode,
        ip_address_pool: InfrahubNode,
        client: InfrahubClient,
    ) -> None:
        template = await client.create(
            kind="TemplateInfraDevice",
            template_name="device-pool-then-direct",
            primary_address_from_resource_pool=ip_address_pool.id,
        )
        await template.save()

        retrieved = await client.get(kind="TemplateInfraDevice", id=template.id)
        retrieved.primary_address = static_ip_address.id

        with pytest.raises(GraphQLError) as exc:
            await retrieved.update()

        assert "Templates can only use one of: direct relationship or resource pool allocation" in str(exc.value)


class TestTemplateNumberPoolAttributes(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def load_schema(self, db: InfrahubDatabase, initialize_registry: None, client: InfrahubClient) -> None:
        schema = {
            "version": "1.0",
            "nodes": [
                {
                    "name": "Rack",
                    "namespace": "Infra",
                    "generate_template": True,
                    "attributes": [
                        {"name": "name", "kind": "Text", "unique": True},
                        {"name": "location", "kind": "Text", "optional": True},
                        {"name": "slot_id", "kind": "Number", "optional": True},
                    ],
                },
            ],
        }
        response = await client.schema.load(schemas=[schema])
        assert response.schema_updated
        assert not response.errors

    @pytest.fixture(scope="class")
    async def slot_pool(self, client: InfrahubClient, load_schema: None) -> InfrahubNode:
        pool = await client.create(
            kind=InfrahubKind.NUMBERPOOL,
            name="slot-pool",
            node="InfraRack",
            node_attribute="slot_id",
            start_range=1,
            end_range=100,
        )
        await pool.save()
        return pool

    @pytest.fixture(scope="class")
    async def template_with_static_slot(self, client: InfrahubClient, load_schema: None) -> InfrahubNode:
        template = await client.create(
            kind="TemplateInfraRack", template_name="rack-static-slot", location="datacenter-1", slot_id=50
        )
        await template.save()
        return template

    @pytest.fixture(scope="class")
    async def template_with_pool_slot(
        self, client: InfrahubClient, slot_pool: InfrahubNode, load_schema: None
    ) -> InfrahubNode:
        template = await client.create(
            kind="TemplateInfraRack", template_name="rack-pool-slot", location="datacenter-1", slot_id=slot_pool
        )
        await template.save()
        return template

    async def test_template_with_pool_stores_reference_not_value(
        self, template_with_pool_slot: InfrahubNode, slot_pool: InfrahubNode, client: InfrahubClient
    ) -> None:
        """Template with from_pool should store reference without allocating a value."""
        retrieved = await client.get(kind="TemplateInfraRack", id=template_with_pool_slot.id)
        assert retrieved.template_name.value == "rack-pool-slot"
        assert retrieved.slot_id.value is None

    async def test_rack_from_template_with_static_slot(
        self, template_with_static_slot: InfrahubNode, client: InfrahubClient
    ) -> None:
        rack = await client.create(
            kind="InfraRack", name="rack-from-static-template", object_template=template_with_static_slot.id
        )
        await rack.save()

        retrieved = await client.get(kind="InfraRack", id=rack.id)
        assert retrieved.name.value == "rack-from-static-template"
        assert retrieved.slot_id.value == 50

    async def test_rack_from_template_with_pool_allocates_slot(
        self, template_with_pool_slot: InfrahubNode, slot_pool: InfrahubNode, client: InfrahubClient
    ) -> None:
        """Object created from template should allocate from pool."""
        rack = await client.create(
            kind="InfraRack", name="rack-from-pool-template", object_template=template_with_pool_slot.id
        )
        await rack.save()

        retrieved = await client.get(kind="InfraRack", id=rack.id, include=["slot_id"])
        assert retrieved.name.value == "rack-from-pool-template"
        assert retrieved.slot_id.value is not None
        assert 1 <= retrieved.slot_id.value <= 100

    async def test_rack_explicit_slot_overrides_pool_template(
        self, template_with_pool_slot: InfrahubNode, client: InfrahubClient
    ) -> None:
        """User-provided slot value should override pool allocation."""
        rack = await client.create(
            kind="InfraRack",
            name="rack-with-explicit-slot",
            object_template=template_with_pool_slot.id,
            slot_id=999,
        )
        await rack.save()

        retrieved = await client.get(kind="InfraRack", id=rack.id)
        assert retrieved.slot_id.value == 999

    async def test_multiple_racks_from_pool_template_get_unique_slots(
        self, template_with_pool_slot: InfrahubNode, client: InfrahubClient
    ) -> None:
        """Multiple objects from same pool template should get unique slot allocations."""
        rack1 = await client.create(
            kind="InfraRack", name="rack-pool-unique-1", object_template=template_with_pool_slot.id
        )
        await rack1.save()

        rack2 = await client.create(
            kind="InfraRack", name="rack-pool-unique-2", object_template=template_with_pool_slot.id
        )
        await rack2.save()

        retrieved1 = await client.get(kind="InfraRack", id=rack1.id)
        retrieved2 = await client.get(kind="InfraRack", id=rack2.id)

        assert retrieved1.slot_id.value is not None
        assert retrieved2.slot_id.value is not None
        assert retrieved1.slot_id.value != retrieved2.slot_id.value
