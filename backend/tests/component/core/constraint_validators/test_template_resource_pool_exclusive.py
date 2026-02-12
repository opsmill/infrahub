from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import BranchSupportType, InfrahubKind, RelationshipCardinality
from infrahub.core.node import Node
from infrahub.core.node.ipam import BuiltinIPPrefix
from infrahub.core.node.resource_manager.ip_address_pool import CoreIPAddressPool
from infrahub.core.relationship.constraints.template_resource_pool_exclusive import (
    TemplateResourcePoolExclusiveConstraint,
)
from infrahub.core.schema import RelationshipSchema, SchemaRoot
from infrahub.exceptions import ValidationError
from tests.helpers.schema.device import DEVICE, INTERFACE, INTERFACE_HOLDER

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


class TestTemplateResourcePoolExclusiveConstraint:
    @pytest.fixture(scope="class")
    def ipam_schema(self) -> SchemaRoot:
        SCHEMA: dict[str, Any] = {
            "nodes": [
                {
                    "name": "IPPrefix",
                    "namespace": "Ipam",
                    "default_filter": "prefix__value",
                    "order_by": ["prefix__value"],
                    "display_labels": ["prefix__value"],
                    "branch": BranchSupportType.AWARE.value,
                    "inherit_from": [InfrahubKind.IPPREFIX],
                },
                {
                    "name": "IPAddress",
                    "namespace": "Ipam",
                    "default_filter": "address__value",
                    "order_by": ["address__value"],
                    "display_labels": ["address__value"],
                    "branch": BranchSupportType.AWARE.value,
                    "inherit_from": [InfrahubKind.IPADDRESS],
                },
            ],
        }
        return SchemaRoot(**SCHEMA)

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

    @pytest.fixture(scope="class")
    async def ip_namespace(self, db: InfrahubDatabase, register_ipam_schema: SchemaBranch) -> Node:
        ns = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
        await ns.new(db=db, name="test-ns")
        await ns.save(db=db)
        return ns

    @pytest.fixture(scope="class")
    async def ip_prefix(self, db: InfrahubDatabase, default_branch_scope_class: Branch, ip_namespace: Node) -> Node:
        prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch_scope_class)
        prefix = await Node.init(db=db, schema=prefix_schema)
        await prefix.new(db=db, prefix="10.10.3.0/27", ip_namespace=ip_namespace)
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
            name="test-address-pool",
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
        await address.new(db=db, address="10.10.3.10/27", ip_prefix=ip_prefix, ip_namespace=ip_namespace)
        await address.save(db=db)
        return address

    async def test_constraint_allows_pool_relationship_only(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        device_schema_with_pool_rel: None,
        ip_address_pool: CoreIPAddressPool,
    ) -> None:
        """Test that the constraint allows setting only the pool relationship."""
        template_schema = registry.schema.get_template_schema(
            name="TemplateTestingDevice", branch=default_branch_scope_class
        )
        constraint = TemplateResourcePoolExclusiveConstraint(db=db, branch=default_branch_scope_class)

        template = await Node.init(db=db, schema=template_schema, branch=default_branch_scope_class)
        await template.new(
            db=db, template_name="device-template-pool-only", primary_ip_from_resource_pool=ip_address_pool
        )

        await constraint.check(
            relm=template.primary_ip_from_resource_pool, node_schema=template.get_schema(), node=template
        )

    async def test_constraint_allows_direct_relationship_only(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        device_schema_with_pool_rel: None,
        ip_address: Node,
    ) -> None:
        """Test that the constraint allows setting only the direct relationship."""
        template_schema = registry.schema.get_template_schema(
            name="TemplateTestingDevice", branch=default_branch_scope_class
        )
        constraint = TemplateResourcePoolExclusiveConstraint(db=db, branch=default_branch_scope_class)

        template = await Node.init(db=db, schema=template_schema, branch=default_branch_scope_class)
        await template.new(db=db, template_name="device-template-direct-only", primary_ip=ip_address)

        await constraint.check(relm=template.primary_ip, node_schema=template.get_schema(), node=template)

    async def test_constraint_rejects_pool_when_direct_exists(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        device_schema_with_pool_rel: None,
        ip_address_pool: CoreIPAddressPool,
        ip_address: Node,
    ) -> None:
        """Test that the constraint rejects adding pool relationship when direct relationship exists."""
        template_schema = registry.schema.get_template_schema(
            name="TemplateTestingDevice", branch=default_branch_scope_class
        )
        constraint = TemplateResourcePoolExclusiveConstraint(db=db, branch=default_branch_scope_class)

        template = await Node.init(db=db, schema=template_schema, branch=default_branch_scope_class)
        await template.new(
            db=db,
            template_name="device-template-both",
            primary_ip=ip_address,
            primary_ip_from_resource_pool=ip_address_pool,
        )

        with pytest.raises(ValidationError) as exc:
            await constraint.check(
                relm=template.primary_ip_from_resource_pool, node_schema=template.get_schema(), node=template
            )

        assert "Cannot set 'primary_ip_from_resource_pool' when 'primary_ip' is already set." in exc.value.message

    async def test_constraint_rejects_direct_when_pool_exists(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        device_schema_with_pool_rel: None,
        ip_address_pool: CoreIPAddressPool,
        ip_address: Node,
    ) -> None:
        """Test that the constraint rejects adding direct relationship when pool relationship exists."""
        template_schema = registry.schema.get_template_schema(
            name="TemplateTestingDevice", branch=default_branch_scope_class
        )
        constraint = TemplateResourcePoolExclusiveConstraint(db=db, branch=default_branch_scope_class)

        template = await Node.init(db=db, schema=template_schema, branch=default_branch_scope_class)
        await template.new(
            db=db,
            template_name="device-template-both-2",
            primary_ip=ip_address,
            primary_ip_from_resource_pool=ip_address_pool,
        )

        with pytest.raises(ValidationError) as exc:
            await constraint.check(relm=template.primary_ip, node_schema=template.get_schema(), node=template)

        assert "Cannot set 'primary_ip' when 'primary_ip_from_resource_pool' is already set." in exc.value.message

    async def test_constraint_rejects_direct_when_pool_is_set(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        device_schema_with_pool_rel: None,
        ip_address_pool: CoreIPAddressPool,
        ip_address: Node,
    ) -> None:
        """Test that the constraint rejects adding direct relationship when pool is already set."""
        template_schema = registry.schema.get_template_schema(
            name="TemplateTestingDevice", branch=default_branch_scope_class
        )
        constraint = TemplateResourcePoolExclusiveConstraint(db=db, branch=default_branch_scope_class)

        template = await Node.init(db=db, schema=template_schema, branch=default_branch_scope_class)
        await template.new(
            db=db, template_name="device-template-pool-in-db", primary_ip_from_resource_pool=ip_address_pool
        )
        await template.save(db=db)

        loaded_template = await registry.manager.get_one(db=db, id=template.id, branch=default_branch_scope_class)
        await loaded_template.primary_ip.update(db=db, data={"id": ip_address.id})

        with pytest.raises(ValidationError) as exc:
            await constraint.check(
                relm=loaded_template.primary_ip, node_schema=loaded_template.get_schema(), node=loaded_template
            )

        assert "Cannot set 'primary_ip' when 'primary_ip_from_resource_pool' is already set." in exc.value.message

    async def test_constraint_skipped_for_non_template_nodes(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        device_schema_with_pool_rel: None,
        ip_address: Node,
    ) -> None:
        """Test that the constraint is skipped for regular nodes (not templates)."""
        node_schema = registry.schema.get_node_schema(name="TestingDevice", branch=default_branch_scope_class)
        constraint = TemplateResourcePoolExclusiveConstraint(db=db, branch=default_branch_scope_class)

        device = await Node.init(db=db, schema=node_schema, branch=default_branch_scope_class)
        await device.new(
            db=db,
            name="test-device",
            manufacturer="Test Inc.",
            weight=10,
            airflow="Front to rear",
            primary_ip=ip_address,
        )

        await constraint.check(relm=device.primary_ip, node_schema=device.get_schema(), node=device)

    async def test_constraint_allows_update_after_clearing_counterpart(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        device_schema_with_pool_rel: None,
        ip_address_pool: CoreIPAddressPool,
        ip_address: Node,
    ) -> None:
        """Test that the constraint allows setting a relationship after clearing its counterpart."""
        template_schema = registry.schema.get_template_schema(
            name="TemplateTestingDevice", branch=default_branch_scope_class
        )
        constraint = TemplateResourcePoolExclusiveConstraint(db=db, branch=default_branch_scope_class)

        template = await Node.init(db=db, schema=template_schema, branch=default_branch_scope_class)
        await template.new(
            db=db, template_name="device-template-replace", primary_ip_from_resource_pool=ip_address_pool
        )
        await template.save(db=db)

        loaded_template = await registry.manager.get_one(db=db, id=template.id, branch=default_branch_scope_class)
        await loaded_template.primary_ip_from_resource_pool.update(db=db, data=None)
        await loaded_template.primary_ip.update(db=db, data={"id": ip_address.id})

        await constraint.check(
            relm=loaded_template.primary_ip, node_schema=loaded_template.get_schema(), node=loaded_template
        )
