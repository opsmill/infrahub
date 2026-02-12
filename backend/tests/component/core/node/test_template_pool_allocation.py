from __future__ import annotations

import copy
from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind, RelationshipCardinality
from infrahub.core.node import Node
from infrahub.core.node.create import create_node
from infrahub.core.node.resource_manager.ip_address_pool import CoreIPAddressPool
from infrahub.core.schema import RelationshipSchema, SchemaRoot
from tests.constants import TestKind
from tests.helpers.schema.device import DEVICE, INTERFACE, INTERFACE_HOLDER

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


@pytest.fixture
async def device_schema(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
    init_nodes_registry,
) -> None:
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


async def test_template_with_pool_relationship_does_not_allocate(
    db: InfrahubDatabase, default_branch: Branch, device_schema: None, ip_address_pool: CoreIPAddressPool
) -> None:
    template_schema = registry.schema.get_template_schema(name="TemplateTestingDevice", branch=default_branch)

    template = await Node.init(schema=template_schema, db=db, branch=default_branch)
    await template.new(
        db=db, template_name="device-template-with-pool", primary_ip_from_resource_pool={"id": ip_address_pool.id}
    )
    await template.save(db=db)

    assert template.id is not None

    pool_rel = await template.primary_ip_from_resource_pool.get_peer(db=db)
    assert pool_rel is not None
    assert pool_rel.id == ip_address_pool.id

    primary_ip = await template.primary_ip.get_peer(db=db)
    assert primary_ip is None


async def test_object_from_template_with_pool_allocates_address(
    db: InfrahubDatabase, default_branch: Branch, device_schema: None, ip_address_pool: CoreIPAddressPool
) -> None:
    template_schema = registry.schema.get_template_schema(name="TemplateTestingDevice", branch=default_branch)
    node_schema = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)

    template = await Node.init(schema=template_schema, db=db, branch=default_branch)
    await template.new(
        db=db, template_name="device-template-for-allocation", primary_ip_from_resource_pool={"id": ip_address_pool.id}
    )
    await template.save(db=db)

    device = await create_node(
        data={
            "name": "device-from-template",
            "manufacturer": "Acme",
            "weight": 10,
            "airflow": "Front to rear",
            "object_template": {"id": template.id},
        },
        db=db,
        branch=default_branch,
        schema=node_schema,
    )

    assert device.id is not None
    assert device.name.value == "device-from-template"

    primary_ip = await device.primary_ip.get_peer(db=db)
    assert primary_ip is not None
    assert primary_ip.address.value is not None
    assert primary_ip.address.value.startswith("10.10.3.")

    primary_ip_rel = await device.primary_ip.get_relationships(db=db)
    assert len(primary_ip_rel) == 1
    assert primary_ip_rel[0].source_id == ip_address_pool.id


async def test_object_from_template_with_explicit_address_uses_explicit(
    db: InfrahubDatabase,
    default_branch: Branch,
    device_schema: None,
    ip_address_pool: CoreIPAddressPool,
    ip_namespace: Node,
    ip_prefix: Node,
) -> None:
    template_schema = registry.schema.get_template_schema(name="TemplateTestingDevice", branch=default_branch)
    node_schema = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)
    address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)

    template = await Node.init(schema=template_schema, db=db, branch=default_branch)
    await template.new(
        db=db,
        template_name="device-template-override-test",
        primary_ip_from_resource_pool={"id": ip_address_pool.id},
    )
    await template.save(db=db)

    explicit_address = await Node.init(db=db, schema=address_schema, branch=default_branch)
    await explicit_address.new(db=db, address="10.10.3.25/27", ip_prefix=ip_prefix, ip_namespace=ip_namespace)
    await explicit_address.save(db=db)

    device = await create_node(
        data={
            "name": "device-with-explicit-address",
            "manufacturer": "Acme",
            "weight": 10,
            "airflow": "Front to rear",
            "object_template": {"id": template.id},
            "primary_ip": {"id": explicit_address.id},
        },
        db=db,
        branch=default_branch,
        schema=node_schema,
    )

    assert device.id is not None

    primary_ip = await device.primary_ip.get_peer(db=db)
    assert primary_ip is not None
    assert primary_ip.id == explicit_address.id
    assert primary_ip.address.value == "10.10.3.25/27"


async def test_object_from_template_with_direct_address_inherits_address(
    db: InfrahubDatabase, default_branch: Branch, device_schema: None, ip_namespace: Node, ip_prefix: Node
) -> None:
    template_schema = registry.schema.get_template_schema(name="TemplateTestingDevice", branch=default_branch)
    node_schema = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)
    address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)

    template_address = await Node.init(db=db, schema=address_schema, branch=default_branch)
    await template_address.new(db=db, address="10.10.3.50/27", ip_prefix=ip_prefix, ip_namespace=ip_namespace)
    await template_address.save(db=db)

    template = await Node.init(schema=template_schema, db=db, branch=default_branch)
    await template.new(db=db, template_name="device-template-with-direct-ip", primary_ip={"id": template_address.id})
    await template.save(db=db)

    device = await create_node(
        data={
            "name": "device-inherits-direct-ip",
            "manufacturer": "Acme",
            "weight": 10,
            "airflow": "Front to rear",
            "object_template": {"id": template.id},
        },
        db=db,
        branch=default_branch,
        schema=node_schema,
    )

    assert device.id is not None

    primary_ip = await device.primary_ip.get_peer(db=db)
    assert primary_ip is not None
    assert primary_ip.id == template_address.id
    assert primary_ip.address.value == "10.10.3.50/27"
