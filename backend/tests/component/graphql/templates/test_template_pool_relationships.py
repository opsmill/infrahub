from __future__ import annotations

import copy
from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind, RelationshipCardinality
from infrahub.core.initialization import create_ipam_namespace
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.ipam import BuiltinIPPrefix
from infrahub.core.node.resource_manager.ip_address_pool import CoreIPAddressPool
from infrahub.core.schema import RelationshipSchema, SchemaRoot
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql
from tests.helpers.schema.device import DEVICE, INTERFACE, INTERFACE_HOLDER

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

CREATE_TEMPLATE_WITH_POOL = """
mutation CreateTemplate($template_name: String!, $pool_id: String!) {
    TemplateTestingDeviceCreate(data: {
        template_name: { value: $template_name }
        primary_ip: { from_pool: { id: $pool_id } }
    }) {
        ok
        object { id }
    }
}
"""

CREATE_TEMPLATE_WITH_DIRECT = """
mutation CreateTemplate($template_name: String!, $peer_id: String!) {
    TemplateTestingDeviceCreate(data: {
        template_name: { value: $template_name }
        primary_ip: { id: $peer_id }
    }) {
        ok
        object { id }
    }
}
"""

UPDATE_TEMPLATE_WITH_POOL = """
mutation UpdateTemplate($id: String!, $pool_id: String!) {
    TemplateTestingDeviceUpdate(data: {
        id: $id
        primary_ip: { from_pool: { id: $pool_id } }
    }) {
        ok
        object { id }
    }
}
"""

UPDATE_TEMPLATE_WITH_DIRECT = """
mutation UpdateTemplate($id: String!, $peer_id: String!) {
    TemplateTestingDeviceUpdate(data: {
        id: $id
        primary_ip: { id: $peer_id }
    }) {
        ok
        object { id }
    }
}
"""

UPDATE_TEMPLATE_CLEAR = """
mutation ClearTemplate($id: String!) {
    TemplateTestingDeviceUpdate(data: {
        id: $id
        primary_ip: null
    }) {
        ok
    }
}
"""


class TestTemplatePoolRelationships:
    """Component tests for template pool relationship routing via GraphQL.

    Verifies that when creating/updating templates through GraphQL mutations,
    providing from_pool on a relationship field correctly routes the data to the
    internal _from_resource_pool relationship, while direct id/hfid stays on
    the regular relationship.
    """

    @pytest.fixture(scope="class")
    async def register_ipam_schema(self, default_branch_scope_class: Branch, ipam_schema: SchemaRoot) -> None:
        registry.schema.register_schema(schema=ipam_schema, branch=default_branch_scope_class.name)
        default_branch_scope_class.update_schema_hash()

    @pytest.fixture(scope="class")
    def init_nodes_registry(self) -> None:
        registry.node["Node"] = Node
        registry.node[InfrahubKind.IPPREFIX] = BuiltinIPPrefix
        registry.node[InfrahubKind.IPADDRESSPOOL] = CoreIPAddressPool

    @pytest.fixture(scope="class")
    async def default_ipnamespace(
        self, db: InfrahubDatabase, register_core_models_schema_scope_class: SchemaBranch
    ) -> None:
        if not registry._default_ipnamespace:
            ip_namespace = await create_ipam_namespace(db=db)
            registry.default_ipnamespace = ip_namespace.id

    @pytest.fixture(scope="class")
    async def device_schema_with_pool_rel(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
        register_ipam_schema: None,
        init_nodes_registry: None,
    ) -> None:
        device = copy.deepcopy(DEVICE)
        device.relationships = [
            RelationshipSchema(
                name="primary_ip", peer="IpamIPAddress", cardinality=RelationshipCardinality.ONE, optional=True
            )
        ]
        schema = SchemaRoot(generics=[INTERFACE_HOLDER, INTERFACE], nodes=[device])
        registry.schema.register_schema(schema=schema, branch=default_branch_scope_class.name)
        default_branch_scope_class.update_schema_hash()

    @pytest.fixture(scope="class")
    async def ip_namespace(self, db: InfrahubDatabase, default_ipnamespace: None) -> Node:
        ns = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
        await ns.new(db=db, name="tpl-pool-ns")
        await ns.save(db=db)
        return ns

    @pytest.fixture(scope="class")
    async def ip_prefix(self, db: InfrahubDatabase, default_branch_scope_class: Branch, ip_namespace: Node) -> Node:
        prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch_scope_class)
        prefix = await Node.init(db=db, schema=prefix_schema)
        await prefix.new(db=db, prefix="10.99.0.0/24", ip_namespace=ip_namespace)
        await prefix.save(db=db)
        return prefix

    @pytest.fixture(scope="class")
    async def ip_address_pool(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ip_namespace: Node, ip_prefix: Node
    ) -> CoreIPAddressPool:
        pool_schema = registry.schema.get_node_schema(
            name=InfrahubKind.IPADDRESSPOOL, branch=default_branch_scope_class
        )
        pool = await CoreIPAddressPool.init(schema=pool_schema, db=db)
        await pool.new(
            db=db,
            name="tpl-test-address-pool",
            resources=[ip_prefix],
            ip_namespace=ip_namespace,
            default_address_type="IpamIPAddress",
        )
        await pool.save(db=db)
        return pool

    @pytest.fixture(scope="class")
    async def ip_address(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, ip_namespace: Node, ip_prefix: Node
    ) -> Node:
        address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch_scope_class)
        address = await Node.init(db=db, schema=address_schema, branch=default_branch_scope_class)
        await address.new(db=db, address="10.99.0.10/24", ip_prefix=ip_prefix, ip_namespace=ip_namespace)
        await address.save(db=db)
        return address

    async def test_create_template_with_pool_from_pool_routes_to_pool_relationship(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        device_schema_with_pool_rel: None,
        ip_address_pool: CoreIPAddressPool,
    ) -> None:
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=CREATE_TEMPLATE_WITH_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"template_name": "device-tpl-pool-by-id", "pool_id": ip_address_pool.id},
        )

        assert not result.errors
        assert result.data
        template_id = result.data["TemplateTestingDeviceCreate"]["object"]["id"]

        template = await NodeManager.get_one(id=template_id, db=db, branch=default_branch_scope_class)
        pool_peer = await template.get_relationship("primary_ip_from_resource_pool").get_peer(db=db)
        assert pool_peer is not None
        assert pool_peer.id == ip_address_pool.id

        direct_peer = await template.get_relationship("primary_ip").get_peer(db=db)
        assert direct_peer is None

    async def test_create_template_with_direct_id_stays_on_regular_relationship(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        device_schema_with_pool_rel: None,
        ip_address: Node,
    ) -> None:
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=CREATE_TEMPLATE_WITH_DIRECT,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"template_name": "device-tpl-direct-by-id", "peer_id": ip_address.id},
        )

        assert not result.errors
        assert result.data
        template_id = result.data["TemplateTestingDeviceCreate"]["object"]["id"]

        template = await NodeManager.get_one(id=template_id, db=db, branch=default_branch_scope_class)
        direct_peer = await template.get_relationship("primary_ip").get_peer(db=db)
        assert direct_peer is not None
        assert direct_peer.id == ip_address.id

        pool_peer = await template.get_relationship("primary_ip_from_resource_pool").get_peer(db=db)
        assert pool_peer is None

    async def test_update_template_with_pool_from_pool_routes_to_pool_relationship(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        device_schema_with_pool_rel: None,
        ip_address_pool: CoreIPAddressPool,
    ) -> None:
        template_schema = registry.schema.get_template_schema(
            name="TemplateTestingDevice", branch=default_branch_scope_class
        )
        template = await Node.init(db=db, schema=template_schema, branch=default_branch_scope_class)
        await template.new(db=db, template_name="device-tpl-update-pool")
        await template.save(db=db)

        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=UPDATE_TEMPLATE_WITH_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"id": template.id, "pool_id": ip_address_pool.id},
        )

        assert not result.errors
        assert result.data

        reloaded = await NodeManager.get_one(id=template.id, db=db, branch=default_branch_scope_class)
        pool_peer = await reloaded.get_relationship("primary_ip_from_resource_pool").get_peer(db=db)
        assert pool_peer is not None
        assert pool_peer.id == ip_address_pool.id

        direct_peer = await reloaded.get_relationship("primary_ip").get_peer(db=db)
        assert direct_peer is None

    async def test_null_clears_pool_relationship(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        device_schema_with_pool_rel: None,
        ip_address_pool: CoreIPAddressPool,
    ) -> None:
        template_schema = registry.schema.get_template_schema(
            name="TemplateTestingDevice", branch=default_branch_scope_class
        )
        template = await Node.init(db=db, schema=template_schema, branch=default_branch_scope_class)
        await template.new(db=db, template_name="device-tpl-clear-pool", primary_ip_from_resource_pool=ip_address_pool)
        await template.save(db=db)

        # Verify pool relationship is set before clearing
        pool_peer_before = await template.get_relationship("primary_ip_from_resource_pool").get_peer(db=db)
        assert pool_peer_before is not None
        assert pool_peer_before.id == ip_address_pool.id

        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=UPDATE_TEMPLATE_CLEAR,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"id": template.id},
        )

        assert not result.errors

        reloaded = await NodeManager.get_one(id=template.id, db=db, branch=default_branch_scope_class)
        pool_peer = await reloaded.get_relationship("primary_ip_from_resource_pool").get_peer(db=db)
        assert pool_peer is None
        direct_peer = await reloaded.get_relationship("primary_ip").get_peer(db=db)
        assert direct_peer is None

    async def test_null_clears_direct_relationship(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        device_schema_with_pool_rel: None,
        ip_address: Node,
    ) -> None:
        template_schema = registry.schema.get_template_schema(
            name="TemplateTestingDevice", branch=default_branch_scope_class
        )
        template = await Node.init(db=db, schema=template_schema, branch=default_branch_scope_class)
        await template.new(db=db, template_name="device-tpl-clear-direct", primary_ip=ip_address)
        await template.save(db=db)

        # Verify direct relationship is set before clearing
        direct_peer_before = await template.get_relationship("primary_ip").get_peer(db=db)
        assert direct_peer_before is not None
        assert direct_peer_before.id == ip_address.id

        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=UPDATE_TEMPLATE_CLEAR,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"id": template.id},
        )

        assert not result.errors

        reloaded = await NodeManager.get_one(id=template.id, db=db, branch=default_branch_scope_class)
        direct_peer = await reloaded.get_relationship("primary_ip").get_peer(db=db)
        assert direct_peer is None
        pool_peer = await reloaded.get_relationship("primary_ip_from_resource_pool").get_peer(db=db)
        assert pool_peer is None

    async def test_update_template_swap_direct_to_pool(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        device_schema_with_pool_rel: None,
        ip_address: Node,
        ip_address_pool: CoreIPAddressPool,
    ) -> None:
        template_schema = registry.schema.get_template_schema(
            name="TemplateTestingDevice", branch=default_branch_scope_class
        )
        template = await Node.init(db=db, schema=template_schema, branch=default_branch_scope_class)
        await template.new(db=db, template_name="device-tpl-swap-direct-to-pool", primary_ip=ip_address)
        await template.save(db=db)

        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=UPDATE_TEMPLATE_WITH_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"id": template.id, "pool_id": ip_address_pool.id},
        )

        assert not result.errors
        assert result.data

        reloaded = await NodeManager.get_one(id=template.id, db=db, branch=default_branch_scope_class)
        pool_peer = await reloaded.get_relationship("primary_ip_from_resource_pool").get_peer(db=db)
        assert pool_peer is not None
        assert pool_peer.id == ip_address_pool.id

        direct_peer = await reloaded.get_relationship("primary_ip").get_peer(db=db)
        assert direct_peer is None

    async def test_update_template_swap_pool_to_direct(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        device_schema_with_pool_rel: None,
        ip_address: Node,
        ip_address_pool: CoreIPAddressPool,
    ) -> None:
        template_schema = registry.schema.get_template_schema(
            name="TemplateTestingDevice", branch=default_branch_scope_class
        )
        template = await Node.init(db=db, schema=template_schema, branch=default_branch_scope_class)
        await template.new(
            db=db, template_name="device-tpl-swap-pool-to-direct", primary_ip_from_resource_pool=ip_address_pool
        )
        await template.save(db=db)

        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=UPDATE_TEMPLATE_WITH_DIRECT,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"id": template.id, "peer_id": ip_address.id},
        )

        assert not result.errors
        assert result.data

        reloaded = await NodeManager.get_one(id=template.id, db=db, branch=default_branch_scope_class)
        direct_peer = await reloaded.get_relationship("primary_ip").get_peer(db=db)
        assert direct_peer is not None
        assert direct_peer.id == ip_address.id

        pool_peer = await reloaded.get_relationship("primary_ip_from_resource_pool").get_peer(db=db)
        assert pool_peer is None

    async def test_create_template_with_pool_by_name(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        device_schema_with_pool_rel: None,
        ip_address_pool: CoreIPAddressPool,
    ) -> None:
        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=CREATE_TEMPLATE_WITH_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"template_name": "device-tpl-pool-by-name", "pool_id": "tpl-test-address-pool"},
        )

        assert not result.errors
        assert result.data
        template_id = result.data["TemplateTestingDeviceCreate"]["object"]["id"]

        template = await NodeManager.get_one(id=template_id, db=db, branch=default_branch_scope_class)
        pool_peer = await template.get_relationship("primary_ip_from_resource_pool").get_peer(db=db)
        assert pool_peer is not None
        assert pool_peer.id == ip_address_pool.id

        direct_peer = await template.get_relationship("primary_ip").get_peer(db=db)
        assert direct_peer is None

    async def test_update_template_with_pool_by_name(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        device_schema_with_pool_rel: None,
        ip_address_pool: CoreIPAddressPool,
    ) -> None:
        template_schema = registry.schema.get_template_schema(
            name="TemplateTestingDevice", branch=default_branch_scope_class
        )
        template = await Node.init(db=db, schema=template_schema, branch=default_branch_scope_class)
        await template.new(db=db, template_name="device-tpl-update-pool-by-name")
        await template.save(db=db)

        gql_params = await prepare_graphql_params(db=db, branch=default_branch_scope_class)
        result = await graphql(
            schema=gql_params.schema,
            source=UPDATE_TEMPLATE_WITH_POOL,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"id": template.id, "pool_id": "tpl-test-address-pool"},
        )

        assert not result.errors
        assert result.data

        reloaded = await NodeManager.get_one(id=template.id, db=db, branch=default_branch_scope_class)
        pool_peer = await reloaded.get_relationship("primary_ip_from_resource_pool").get_peer(db=db)
        assert pool_peer is not None
        assert pool_peer.id == ip_address_pool.id

        direct_peer = await reloaded.get_relationship("primary_ip").get_peer(db=db)
        assert direct_peer is None
