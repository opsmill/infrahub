from __future__ import annotations

import copy
from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind, RelationshipCardinality
from infrahub.core.node import Node
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


@pytest.fixture
async def device_schema_with_pool_rel(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
    init_nodes_registry,
) -> None:
    """Register a device schema with a primary_ip relationship that supports pool allocation."""
    device = copy.deepcopy(DEVICE)
    device.relationships = [
        RelationshipSchema(
            name="primary_ip", peer="IpamIPAddress", cardinality=RelationshipCardinality.ONE, optional=True
        )
    ]
    schema = SchemaRoot(generics=[INTERFACE_HOLDER, INTERFACE], nodes=[device])
    registry.schema.register_schema(schema=schema, branch=default_branch.name)


@pytest.fixture
async def ip_namespace(db: InfrahubDatabase, register_ipam_schema: SchemaBranch) -> Node:
    ns = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
    await ns.new(db=db, name="test-ns")
    await ns.save(db=db)
    return ns


@pytest.fixture
async def ip_prefix(db: InfrahubDatabase, default_branch: Branch, ip_namespace: Node) -> Node:
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)
    prefix = await Node.init(db=db, schema=prefix_schema)
    await prefix.new(db=db, prefix="10.10.3.0/27", ip_namespace=ip_namespace)
    await prefix.save(db=db)
    return prefix


@pytest.fixture
async def ip_address_pool(
    db: InfrahubDatabase, default_branch: Branch, ip_namespace: Node, ip_prefix: Node
) -> CoreIPAddressPool:
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


@pytest.fixture
async def ip_address(db: InfrahubDatabase, default_branch: Branch, ip_namespace: Node, ip_prefix: Node) -> Node:
    address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)
    address = await Node.init(db=db, schema=address_schema, branch=default_branch)
    await address.new(db=db, address="10.10.3.10/27", ip_prefix=ip_prefix, ip_namespace=ip_namespace)
    await address.save(db=db)
    return address


async def test_constraint_allows_pool_relationship_only(
    db: InfrahubDatabase, default_branch: Branch, device_schema_with_pool_rel: None, ip_address_pool: CoreIPAddressPool
) -> None:
    """Test that the constraint allows setting only the pool relationship."""
    template_schema = registry.schema.get_template_schema(name="TemplateTestingDevice", branch=default_branch)
    constraint = TemplateResourcePoolExclusiveConstraint(db=db, branch=default_branch)

    template = await Node.init(db=db, schema=template_schema, branch=default_branch)
    await template.new(db=db, template_name="device-template-pool-only", primary_ip_from_resource_pool=ip_address_pool)

    await constraint.check(
        relm=template.primary_ip_from_resource_pool, node_schema=template.get_schema(), node=template
    )


async def test_constraint_allows_direct_relationship_only(
    db: InfrahubDatabase, default_branch: Branch, device_schema_with_pool_rel: None, ip_address: Node
) -> None:
    """Test that the constraint allows setting only the direct relationship."""
    template_schema = registry.schema.get_template_schema(name="TemplateTestingDevice", branch=default_branch)
    constraint = TemplateResourcePoolExclusiveConstraint(db=db, branch=default_branch)

    template = await Node.init(db=db, schema=template_schema, branch=default_branch)
    await template.new(db=db, template_name="device-template-direct-only", primary_ip=ip_address)

    await constraint.check(relm=template.primary_ip, node_schema=template.get_schema(), node=template)


async def test_constraint_rejects_pool_when_direct_exists(
    db: InfrahubDatabase,
    default_branch: Branch,
    device_schema_with_pool_rel: None,
    ip_address_pool: CoreIPAddressPool,
    ip_address: Node,
) -> None:
    """Test that the constraint rejects adding pool relationship when direct relationship exists."""
    template_schema = registry.schema.get_template_schema(name="TemplateTestingDevice", branch=default_branch)
    constraint = TemplateResourcePoolExclusiveConstraint(db=db, branch=default_branch)

    template = await Node.init(db=db, schema=template_schema, branch=default_branch)
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
    db: InfrahubDatabase,
    default_branch: Branch,
    device_schema_with_pool_rel: None,
    ip_address_pool: CoreIPAddressPool,
    ip_address: Node,
) -> None:
    """Test that the constraint rejects adding direct relationship when pool relationship exists."""
    template_schema = registry.schema.get_template_schema(name="TemplateTestingDevice", branch=default_branch)
    constraint = TemplateResourcePoolExclusiveConstraint(db=db, branch=default_branch)

    template = await Node.init(db=db, schema=template_schema, branch=default_branch)
    await template.new(
        db=db,
        template_name="device-template-both",
        primary_ip=ip_address,
        primary_ip_from_resource_pool=ip_address_pool,
    )

    with pytest.raises(ValidationError) as exc:
        await constraint.check(relm=template.primary_ip, node_schema=template.get_schema(), node=template)

    assert "Cannot set 'primary_ip' when 'primary_ip_from_resource_pool' is already set." in exc.value.message


async def test_constraint_rejects_direct_when_pool_is_set(
    db: InfrahubDatabase,
    default_branch: Branch,
    device_schema_with_pool_rel: None,
    ip_address_pool: CoreIPAddressPool,
    ip_address: Node,
) -> None:
    """Test that the constraint rejects adding direct relationship when pool is already set."""
    template_schema = registry.schema.get_template_schema(name="TemplateTestingDevice", branch=default_branch)
    constraint = TemplateResourcePoolExclusiveConstraint(db=db, branch=default_branch)

    template = await Node.init(db=db, schema=template_schema, branch=default_branch)
    await template.new(db=db, template_name="device-template-pool-in-db", primary_ip_from_resource_pool=ip_address_pool)
    await template.save(db=db)

    loaded_template = await registry.manager.get_one(db=db, id=template.id, branch=default_branch)
    await loaded_template.primary_ip.update(db=db, data={"id": ip_address.id})

    with pytest.raises(ValidationError) as exc:
        await constraint.check(
            relm=loaded_template.primary_ip, node_schema=loaded_template.get_schema(), node=loaded_template
        )

    assert "Cannot set 'primary_ip' when 'primary_ip_from_resource_pool' is already set." in exc.value.message


async def test_constraint_skipped_for_non_template_nodes(
    db: InfrahubDatabase, default_branch: Branch, device_schema_with_pool_rel: None, ip_address: Node
) -> None:
    """Test that the constraint is skipped for regular nodes (not templates)."""
    node_schema = registry.schema.get_node_schema(name="TestingDevice", branch=default_branch)
    constraint = TemplateResourcePoolExclusiveConstraint(db=db, branch=default_branch)

    device = await Node.init(db=db, schema=node_schema, branch=default_branch)
    await device.new(
        db=db, name="test-device", manufacturer="Test Inc.", weight=10, airflow="Front to rear", primary_ip=ip_address
    )

    await constraint.check(relm=device.primary_ip, node_schema=device.get_schema(), node=device)


async def test_constraint_allows_update_after_clearing_counterpart(
    db: InfrahubDatabase,
    default_branch: Branch,
    device_schema_with_pool_rel: None,
    ip_address_pool: CoreIPAddressPool,
    ip_address: Node,
) -> None:
    """Test that the constraint allows setting a relationship after clearing its counterpart."""
    template_schema = registry.schema.get_template_schema(name="TemplateTestingDevice", branch=default_branch)
    constraint = TemplateResourcePoolExclusiveConstraint(db=db, branch=default_branch)

    template = await Node.init(db=db, schema=template_schema, branch=default_branch)
    await template.new(db=db, template_name="device-template-replace", primary_ip_from_resource_pool=ip_address_pool)
    await template.save(db=db)

    loaded_template = await registry.manager.get_one(db=db, id=template.id, branch=default_branch)
    await loaded_template.primary_ip_from_resource_pool.update(db=db, data=None)
    await loaded_template.primary_ip.update(db=db, data={"id": ip_address.id})

    await constraint.check(
        relm=loaded_template.primary_ip, node_schema=loaded_template.get_schema(), node=loaded_template
    )
