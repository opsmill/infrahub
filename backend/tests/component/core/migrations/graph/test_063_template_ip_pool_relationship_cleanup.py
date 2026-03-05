from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import BranchSupportType, InfrahubKind, MetadataOptions, RelationshipCardinality
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m063_template_ip_pool_relationship_cleanup import Migration063
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.ip_address_pool import CoreIPAddressPool
from infrahub.core.node.resource_manager.ip_prefix_pool import CoreIPPrefixPool
from infrahub.core.schema import NodeSchema, SchemaRoot
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


class TestMigration063(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def device_schema(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_schema: SchemaBranch
    ) -> NodeSchema:
        SCHEMA: dict[str, Any] = {
            "nodes": [
                {
                    "name": "IPPrefix",
                    "namespace": "Ipam",
                    "inherit_from": [InfrahubKind.IPPREFIX, InfrahubKind.WEIGHTED_POOL_RESOURCE],
                    "display_labels": ["prefix__value"],
                    "branch": BranchSupportType.AWARE.value,
                },
                {
                    "name": "IPAddress",
                    "namespace": "Ipam",
                    "inherit_from": [InfrahubKind.IPADDRESS],
                    "display_labels": ["address__value"],
                    "branch": BranchSupportType.AWARE.value,
                },
                {
                    "name": "Device",
                    "namespace": "Test",
                    "generate_template": True,
                    "display_labels": ["name__value"],
                    "attributes": [{"name": "name", "kind": "Text", "unique": True}],
                    "relationships": [
                        {
                            "name": "primary_address",
                            "peer": "IpamIPAddress",
                            "cardinality": RelationshipCardinality.ONE.value,
                            "optional": True,
                        },
                        {
                            "name": "management_prefix",
                            "peer": "IpamIPPrefix",
                            "cardinality": RelationshipCardinality.ONE.value,
                            "optional": True,
                        },
                    ],
                },
            ],
        }
        schema = SchemaRoot(**SCHEMA)
        registry.schema.register_schema(schema=schema, branch=default_branch.name)
        return registry.schema.get_node_schema(name="TestDevice", branch=default_branch.name, duplicate=False)

    @pytest.fixture(scope="class")
    async def ip_namespace(self, db: InfrahubDatabase, device_schema: NodeSchema) -> Node:
        ns = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
        await ns.new(db=db, name="default")
        await ns.save(db=db)
        registry.default_ipnamespace = ns.id
        return ns

    @pytest.fixture(scope="class")
    async def ip_prefix(self, db: InfrahubDatabase, ip_namespace: Node) -> Node:
        prefix = await Node.init(db=db, schema="IpamIPPrefix")
        await prefix.new(db=db, prefix="10.0.0.0/24", ip_namespace=ip_namespace)
        await prefix.save(db=db)
        return prefix

    @pytest.fixture(scope="class")
    async def ip_address_pool(
        self, db: InfrahubDatabase, default_branch: Branch, ip_prefix: Node, ip_namespace: Node
    ) -> Node:
        pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPADDRESSPOOL, branch=default_branch)
        pool = await CoreIPAddressPool.init(schema=pool_schema, db=db)
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
    async def ip_prefix_pool(
        self, db: InfrahubDatabase, default_branch: Branch, ip_prefix: Node, ip_namespace: Node
    ) -> Node:
        pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPPREFIXPOOL, branch=default_branch)
        pool = await CoreIPPrefixPool.init(schema=pool_schema, db=db)
        await pool.new(
            db=db,
            name="test-prefix-pool",
            default_prefix_length=28,
            default_prefix_type="IpamIPPrefix",
            resources=[ip_prefix],
            ip_namespace=ip_namespace,
        )
        await pool.save(db=db)
        return pool

    @pytest.fixture(scope="class")
    async def ip_address(self, db: InfrahubDatabase, ip_namespace: Node) -> Node:
        addr = await Node.init(db=db, schema="IpamIPAddress")
        await addr.new(db=db, address="10.0.0.1/32", ip_namespace=ip_namespace)
        await addr.save(db=db)
        return addr

    @pytest.fixture(scope="class")
    async def child_prefix(self, db: InfrahubDatabase, ip_namespace: Node, ip_prefix: Node) -> Node:
        prefix = await Node.init(db=db, schema="IpamIPPrefix")
        await prefix.new(db=db, prefix="10.0.0.0/28", ip_namespace=ip_namespace, parent=ip_prefix)
        await prefix.save(db=db)
        return prefix

    @pytest.fixture(scope="class")
    async def template_with_pool_source(
        self,
        db: InfrahubDatabase,
        ip_address: Node,
        ip_address_pool: Node,
        child_prefix: Node,
        ip_prefix_pool: Node,
    ) -> Node:
        template = await Node.init(db=db, schema="TemplateTestDevice")
        await template.new(
            db=db,
            template_name="pooled-device-template",
            primary_address=ip_address,
            management_prefix=child_prefix,
        )
        await template.save(db=db)

        # Set pool sources on both relationships
        loaded = await NodeManager.get_one(db=db, id=template.id, include_metadata=MetadataOptions.LINKED_NODES)

        address_rel_mgr = loaded.get_relationship("primary_address")
        address_rels = await address_rel_mgr.get_relationships(db=db)
        address_rels[0].source = ip_address_pool.id
        await address_rel_mgr.save(db=db)

        prefix_rel_mgr = loaded.get_relationship("management_prefix")
        prefix_rels = await prefix_rel_mgr.get_relationships(db=db)
        prefix_rels[0].source = ip_prefix_pool.id
        await prefix_rel_mgr.save(db=db)

        return loaded

    @pytest.fixture(scope="class")
    async def plain_ip_address(self, db: InfrahubDatabase) -> Node:
        addr = await Node.init(db=db, schema="IpamIPAddress")
        await addr.new(db=db, address="10.0.0.2/32")
        await addr.save(db=db)
        return addr

    @pytest.fixture(scope="class")
    async def plain_child_prefix(self, db: InfrahubDatabase, ip_namespace: Node, ip_prefix: Node) -> Node:
        prefix = await Node.init(db=db, schema="IpamIPPrefix")
        await prefix.new(db=db, prefix="10.0.0.16/28", ip_namespace=ip_namespace, parent=ip_prefix)
        await prefix.save(db=db)
        return prefix

    @pytest.fixture(scope="class")
    async def template_without_pool_source(
        self, db: InfrahubDatabase, plain_ip_address: Node, plain_child_prefix: Node
    ) -> Node:
        template = await Node.init(db=db, schema="TemplateTestDevice")
        await template.new(
            db=db,
            template_name="plain-device-template",
            primary_address=plain_ip_address,
            management_prefix=plain_child_prefix,
        )
        await template.save(db=db)
        return template

    @pytest.fixture(scope="class")
    async def test_branch(self, db: InfrahubDatabase, template_with_pool_source: Node) -> Branch:
        return await create_branch(db=db, branch_name="test-branch-m063")

    @pytest.fixture(scope="class")
    async def branch_template_with_pool_source(
        self,
        db: InfrahubDatabase,
        test_branch: Branch,
        ip_address: Node,
        ip_address_pool: Node,
        child_prefix: Node,
        ip_prefix_pool: Node,
    ) -> Node:
        template = await Node.init(db=db, schema="TemplateTestDevice", branch=test_branch)
        await template.new(
            db=db,
            template_name="branch-device-template",
            primary_address=ip_address,
            management_prefix=child_prefix,
        )
        await template.save(db=db)

        loaded = await NodeManager.get_one(
            db=db, id=template.id, branch=test_branch, include_metadata=MetadataOptions.LINKED_NODES
        )

        address_mgr = loaded.get_relationship("primary_address")
        address_rels = await address_mgr.get_relationships(db=db)
        address_rels[0].source = ip_address_pool.id
        await address_mgr.save(db=db)

        prefix_mgr = loaded.get_relationship("management_prefix")
        prefix_rels = await prefix_mgr.get_relationships(db=db)
        prefix_rels[0].source = ip_prefix_pool.id
        await prefix_mgr.save(db=db)

        return loaded

    async def _assert_rel_migrated(
        self,
        db: InfrahubDatabase,
        template_id: str,
        rel_name: str,
        pool_id: str,
        branch: Branch | None = None,
    ) -> None:
        loaded = await NodeManager.get_one(
            db=db, id=template_id, branch=branch, include_metadata=MetadataOptions.LINKED_NODES
        )

        pool_rels = await loaded.get_relationship(f"{rel_name}_from_resource_pool").get_relationships(db=db)
        assert len(pool_rels) == 1
        assert pool_rels[0].peer_id == pool_id

        original_rels = await loaded.get_relationship(rel_name).get_relationships(db=db)
        assert len(original_rels) == 0

    async def _assert_rel_unchanged(
        self,
        db: InfrahubDatabase,
        template_id: str,
        rel_name: str,
        peer_id: str,
        branch: Branch | None = None,
    ) -> None:
        loaded = await NodeManager.get_one(
            db=db, id=template_id, branch=branch, include_metadata=MetadataOptions.LINKED_NODES
        )

        original_rels = await loaded.get_relationship(rel_name).get_relationships(db=db)
        assert len(original_rels) == 1
        assert original_rels[0].peer_id == peer_id

        pool_rels = await loaded.get_relationship(f"{rel_name}_from_resource_pool").get_relationships(db=db)
        assert len(pool_rels) == 0

    async def test_creates_from_resource_pool_and_deletes_original(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        ip_address_pool: Node,
        ip_prefix_pool: Node,
        ip_address: Node,
        child_prefix: Node,
        plain_ip_address: Node,
        plain_child_prefix: Node,
        template_with_pool_source: Node,
        template_without_pool_source: Node,
        branch_template_with_pool_source: Node,
    ) -> None:
        # Verify initial state: original relationships exist, pool relationships do not
        loaded = await NodeManager.get_one(
            db=db, id=template_with_pool_source.id, include_metadata=MetadataOptions.LINKED_NODES
        )
        address_rels = await loaded.get_relationship("primary_address").get_relationships(db=db)
        assert len(address_rels) == 1
        assert address_rels[0].peer_id == ip_address.id

        prefix_rels = await loaded.get_relationship("management_prefix").get_relationships(db=db)
        assert len(prefix_rels) == 1
        assert prefix_rels[0].peer_id == child_prefix.id

        address_pool_rels = await loaded.get_relationship("primary_address_from_resource_pool").get_relationships(db=db)
        assert len(address_pool_rels) == 0

        prefix_pool_rels = await loaded.get_relationship("management_prefix_from_resource_pool").get_relationships(
            db=db
        )
        assert len(prefix_pool_rels) == 0

        # Run migration
        async with db.start_session() as dbs:
            migration = Migration063()
            result = await migration.execute(migration_input=MigrationInput(db=dbs))
            assert not result.errors

        await self._assert_rel_migrated(
            db=db, template_id=template_with_pool_source.id, rel_name="primary_address", pool_id=ip_address_pool.id
        )
        await self._assert_rel_migrated(
            db=db, template_id=template_with_pool_source.id, rel_name="management_prefix", pool_id=ip_prefix_pool.id
        )
        await self._assert_rel_unchanged(
            db=db, template_id=template_without_pool_source.id, rel_name="primary_address", peer_id=plain_ip_address.id
        )
        await self._assert_rel_unchanged(
            db=db,
            template_id=template_without_pool_source.id,
            rel_name="management_prefix",
            peer_id=plain_child_prefix.id,
        )

        # Verify idempotency: running again produces no errors and same results
        async with db.start_session() as dbs:
            migration = Migration063()
            result = await migration.execute(migration_input=MigrationInput(db=dbs))
            assert not result.errors

        await self._assert_rel_migrated(
            db=db, template_id=template_with_pool_source.id, rel_name="primary_address", pool_id=ip_address_pool.id
        )
        await self._assert_rel_migrated(
            db=db, template_id=template_with_pool_source.id, rel_name="management_prefix", pool_id=ip_prefix_pool.id
        )
        await self._assert_rel_unchanged(
            db=db, template_id=template_without_pool_source.id, rel_name="primary_address", peer_id=plain_ip_address.id
        )
        await self._assert_rel_unchanged(
            db=db,
            template_id=template_without_pool_source.id,
            rel_name="management_prefix",
            peer_id=plain_child_prefix.id,
        )

    async def test_execute_against_branch(
        self,
        db: InfrahubDatabase,
        test_branch: Branch,
        ip_address_pool: Node,
        ip_prefix_pool: Node,
        plain_ip_address: Node,
        plain_child_prefix: Node,
        template_without_pool_source: Node,
        branch_template_with_pool_source: Node,
    ) -> None:
        # Default branch migration was already applied by the previous test;
        # branch and its template data were created via fixtures before that migration ran
        await test_branch.rebase(db=db)

        async with db.start_session() as dbs:
            migration = Migration063()
            result = await migration.execute_against_branch(migration_input=MigrationInput(db=dbs), branch=test_branch)
            assert not result.errors

        await self._assert_rel_migrated(
            db=db,
            template_id=branch_template_with_pool_source.id,
            rel_name="primary_address",
            pool_id=ip_address_pool.id,
            branch=test_branch,
        )
        await self._assert_rel_migrated(
            db=db,
            template_id=branch_template_with_pool_source.id,
            rel_name="management_prefix",
            pool_id=ip_prefix_pool.id,
            branch=test_branch,
        )
        await self._assert_rel_unchanged(
            db=db, template_id=template_without_pool_source.id, rel_name="primary_address", peer_id=plain_ip_address.id
        )
        await self._assert_rel_unchanged(
            db=db,
            template_id=template_without_pool_source.id,
            rel_name="management_prefix",
            peer_id=plain_child_prefix.id,
        )
