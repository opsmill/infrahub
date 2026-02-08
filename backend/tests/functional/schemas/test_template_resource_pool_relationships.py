from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import InfrahubKind
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


class TestTemplateResourcePoolRelationships(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def load_schema(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
    ) -> None:
        """Load a schema with IP address/prefix relationships."""
        schema = {
            "version": "1.0",
            "nodes": [
                {
                    "name": "IPAddress",
                    "namespace": "Ipam",
                    "inherit_from": ["BuiltinIPAddress"],
                },
                {
                    "name": "IPPrefix",
                    "namespace": "Ipam",
                    "inherit_from": ["BuiltinIPPrefix"],
                },
                {
                    "name": "Device",
                    "namespace": "Infra",
                    "generate_template": True,
                    "attributes": [
                        {"name": "name", "kind": "Text", "unique": True},
                    ],
                    "relationships": [
                        {
                            "name": "address",
                            "peer": "IpamIPAddress",
                            "label": "IP Address",
                            "cardinality": "one",
                        },
                        {
                            "name": "prefix",
                            "peer": "IpamIPPrefix",
                            "label": "IP Prefix",
                            "cardinality": "one",
                        },
                    ],
                },
                {
                    "name": "Server",
                    "namespace": "Infra",
                    "generate_template": True,
                    "attributes": [
                        {"name": "name", "kind": "Text", "unique": True},
                    ],
                    "relationships": [
                        {
                            "name": "ip_address",
                            "peer": "BuiltinIPAddress",
                            "label": "IP Address",
                            "cardinality": "one",
                        },
                        {
                            "name": "ip_prefix",
                            "peer": "BuiltinIPPrefix",
                            "label": "IP Prefix",
                            "cardinality": "one",
                        },
                    ],
                },
            ],
        }
        response = await client.schema.load(schemas=[schema])
        assert response.schema_updated
        assert not response.errors

    async def test_resource_pool_relationships_created(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        load_schema: None,
        default_branch: Branch,
    ) -> None:
        """Test that resource pool relationships are automatically created for IP address/prefix relationships."""
        # Get the Device template schema
        device_template = await client.schema.get(kind="TemplateInfraDevice")
        assert device_template

        # Verify original relationships exist
        device_rels = {rel.name: rel for rel in device_template.relationships}
        assert "address" in device_rels
        assert device_rels["address"].peer == "IpamIPAddress"

        assert "prefix" in device_rels
        assert device_rels["prefix"].peer == "IpamIPPrefix"

        # Verify resource pool relationships exist
        assert "address_from_resource_pool" in device_rels
        assert device_rels["address_from_resource_pool"].peer == InfrahubKind.IPADDRESSPOOL
        assert device_rels["address_from_resource_pool"].cardinality == "one"
        assert device_rels["address_from_resource_pool"].optional is True

        assert "prefix_from_resource_pool" in device_rels
        assert device_rels["prefix_from_resource_pool"].peer == InfrahubKind.IPPREFIXPOOL
        assert device_rels["prefix_from_resource_pool"].cardinality == "one"
        assert device_rels["prefix_from_resource_pool"].optional is True

        # Get the Server template schema
        server_template = await client.schema.get(kind="TemplateInfraServer")
        assert server_template

        # Verify original relationships exist
        server_rels = {rel.name: rel for rel in server_template.relationships}
        assert "ip_address" in server_rels
        assert server_rels["ip_address"].peer == "BuiltinIPAddress"

        assert "ip_prefix" in server_rels
        assert server_rels["ip_prefix"].peer == "BuiltinIPPrefix"

        # Verify resource pool relationships exist
        assert "ip_address_from_resource_pool" in server_rels
        assert server_rels["ip_address_from_resource_pool"].peer == InfrahubKind.IPADDRESSPOOL
        assert server_rels["ip_address_from_resource_pool"].cardinality == "one"
        assert server_rels["ip_address_from_resource_pool"].optional is True

        assert "ip_prefix_from_resource_pool" in server_rels
        assert server_rels["ip_prefix_from_resource_pool"].peer == InfrahubKind.IPPREFIXPOOL
        assert server_rels["ip_prefix_from_resource_pool"].cardinality == "one"
        assert server_rels["ip_prefix_from_resource_pool"].optional is True
