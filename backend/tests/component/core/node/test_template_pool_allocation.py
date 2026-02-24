from __future__ import annotations

import copy
from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind, RelationshipCardinality
from infrahub.core.initialization import initialize_registry
from infrahub.core.node import Node
from infrahub.core.node.create import create_node
from infrahub.core.node.resource_manager.ip_address_pool import CoreIPAddressPool
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import AttributeSchema, RelationshipSchema
from infrahub.exceptions import PoolExhaustedError, ValidationError
from tests.constants import TestKind
from tests.helpers.schema import DEVICE_SCHEMA

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
    init_nodes_registry: None,
) -> None:
    schema = copy.deepcopy(DEVICE_SCHEMA)
    device = next(n for n in schema.nodes if n.kind == TestKind.DEVICE)
    device.relationships.append(
        RelationshipSchema(
            name="primary_ip", peer="IpamIPAddress", cardinality=RelationshipCardinality.ONE, optional=True
        )
    )
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
    template_schema = registry.schema.get_template_schema(name=f"Template{TestKind.DEVICE}", branch=default_branch)

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
    template_schema = registry.schema.get_template_schema(name=f"Template{TestKind.DEVICE}", branch=default_branch)
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

    assert device._creation_context is not None
    assert len(device._creation_context.side_effect_nodes) == 1
    assert device._creation_context.side_effect_nodes[0].get_kind() == "IpamIPAddress"
    assert device._creation_context.side_effect_nodes[0].id == primary_ip.id


async def test_object_from_template_with_explicit_address_uses_explicit(
    db: InfrahubDatabase,
    default_branch: Branch,
    device_schema: None,
    ip_address_pool: CoreIPAddressPool,
    ip_namespace: Node,
    ip_prefix: Node,
) -> None:
    template_schema = registry.schema.get_template_schema(name=f"Template{TestKind.DEVICE}", branch=default_branch)
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
    template_schema = registry.schema.get_template_schema(name=f"Template{TestKind.DEVICE}", branch=default_branch)
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


async def test_object_from_template_raises_validation_error_when_pool_exhausted(
    db: InfrahubDatabase, default_branch: Branch, device_schema: None, ip_namespace: Node, ip_prefix: Node
) -> None:
    """Creating object from template should raise ValidationError when pool is exhausted."""
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)
    small_prefix = await Node.init(db=db, schema=prefix_schema)
    await small_prefix.new(db=db, prefix="10.10.3.8/30", ip_namespace=ip_namespace, parent=ip_prefix, is_pool=True)
    await small_prefix.save(db=db)

    pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPADDRESSPOOL, branch=default_branch)
    small_pool = await CoreIPAddressPool.init(schema=pool_schema, db=db)
    await small_pool.new(
        db=db,
        name="small-address-pool",
        resources=[small_prefix],
        ip_namespace=ip_namespace,
        default_address_type="IpamIPAddress",
    )
    await small_pool.save(db=db)

    template_schema = registry.schema.get_template_schema(name=f"Template{TestKind.DEVICE}", branch=default_branch)
    node_schema = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)

    template = await Node.init(schema=template_schema, db=db, branch=default_branch)
    await template.new(
        db=db, template_name="device-template-small-pool", primary_ip_from_resource_pool={"id": small_pool.id}
    )
    await template.save(db=db)

    # Allocate everything from the pool
    for i in range(2):
        device = await create_node(
            data={
                "name": f"device-exhaust-{i}",
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

    with pytest.raises(PoolExhaustedError, match=r"There are no more addresses available in this pool"):
        await create_node(
            data={
                "name": "device-should-fail",
                "manufacturer": "Acme",
                "weight": 10,
                "airflow": "Front to rear",
                "object_template": {"id": template.id},
            },
            db=db,
            branch=default_branch,
            schema=node_schema,
        )


@pytest.fixture
async def device_with_rack_unit_schema(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, init_nodes_registry: None
) -> None:
    schema = copy.deepcopy(DEVICE_SCHEMA)
    device = next(n for n in schema.nodes if n.kind == TestKind.DEVICE)
    device.attributes.append(AttributeSchema(name="rack_unit", kind="Number", optional=True))
    registry.schema.register_schema(schema=schema, branch=default_branch.name)
    await initialize_registry(db=db)


@pytest.fixture
async def number_pool(
    db: InfrahubDatabase, default_branch: Branch, device_with_rack_unit_schema: None
) -> CoreNumberPool:
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(
        db=db, name="rack-unit-pool", node=TestKind.DEVICE, node_attribute="rack_unit", start_range=1, end_range=48
    )
    await pool.save(db=db)
    return pool


async def test_template_with_number_pool_attribute_does_not_allocate(
    db: InfrahubDatabase, default_branch: Branch, device_with_rack_unit_schema: None, number_pool: CoreNumberPool
) -> None:
    """Template with from_pool attribute should store reference but not allocate."""
    template_schema = registry.schema.get_template_schema(name="TemplateTestingDevice", branch=default_branch)

    template = await Node.init(schema=template_schema, db=db, branch=default_branch)
    await template.new(
        db=db, template_name="device-template-with-pool-attr", rack_unit={"from_pool": {"id": number_pool.id}}
    )
    await template.save(db=db)

    assert template.id is not None
    assert template.rack_unit.value is None

    source = await template.rack_unit.get_source(db=db)
    assert source is not None
    assert source.id == number_pool.id


async def test_object_from_template_with_number_pool_allocates_value(
    db: InfrahubDatabase, default_branch: Branch, device_with_rack_unit_schema: None, number_pool: CoreNumberPool
) -> None:
    """Object created from template should allocate from the NumberPool."""
    template_schema = registry.schema.get_template_schema(name=f"Template{TestKind.DEVICE}", branch=default_branch)
    node_schema = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)

    template = await Node.init(schema=template_schema, db=db, branch=default_branch)
    await template.new(
        db=db, template_name="device-template-for-number-allocation", rack_unit={"from_pool": {"id": number_pool.id}}
    )
    await template.save(db=db)

    device = await create_node(
        data={
            "name": "device-from-template-with-pool",
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
    assert device.name.value == "device-from-template-with-pool"
    assert device.rack_unit.value is not None
    assert 1 <= device.rack_unit.value <= 48

    source = await device.rack_unit.get_source(db=db)
    assert source is not None
    assert source.id == number_pool.id


async def test_object_from_template_with_explicit_value_uses_explicit(
    db: InfrahubDatabase, default_branch: Branch, device_with_rack_unit_schema: None, number_pool: CoreNumberPool
) -> None:
    """Object created with explicit value should use it instead of pool allocation."""
    template_schema = registry.schema.get_template_schema(name=f"Template{TestKind.DEVICE}", branch=default_branch)
    node_schema = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)

    template = await Node.init(schema=template_schema, db=db, branch=default_branch)
    await template.new(
        db=db, template_name="device-template-explicit-override", rack_unit={"from_pool": {"id": number_pool.id}}
    )
    await template.save(db=db)

    device = await create_node(
        data={
            "name": "device-with-explicit-rack-unit",
            "manufacturer": "Acme",
            "weight": 10,
            "airflow": "Front to rear",
            "object_template": {"id": template.id},
            "rack_unit": 99,
        },
        db=db,
        branch=default_branch,
        schema=node_schema,
    )

    assert device.id is not None
    assert device.rack_unit.value == 99
    source = await device.rack_unit.get_source(db=db)
    assert source is None


async def test_object_from_template_raises_error_when_number_pool_exhausted(
    db: InfrahubDatabase, default_branch: Branch, device_with_rack_unit_schema: None
) -> None:
    """Creating object from template raises ValidationError when NumberPool is exhausted."""
    small_pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await small_pool.new(
        db=db, name="small-rack-unit-pool", node=TestKind.DEVICE, node_attribute="rack_unit", start_range=1, end_range=2
    )
    await small_pool.save(db=db)

    template_schema = registry.schema.get_template_schema(name=f"Template{TestKind.DEVICE}", branch=default_branch)
    node_schema = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)

    template = await Node.init(schema=template_schema, db=db, branch=default_branch)
    await template.new(
        db=db, template_name="device-template-small-number-pool", rack_unit={"from_pool": {"id": small_pool.id}}
    )
    await template.save(db=db)

    # Allocate everything from the pool
    for i in range(2):
        device = await create_node(
            data={
                "name": f"device-exhaust-number-{i}",
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

    with pytest.raises(ValidationError, match=r"The pool (.*) is exhausted"):
        await create_node(
            data={
                "name": "device-should-fail-number",
                "manufacturer": "Acme",
                "weight": 10,
                "airflow": "Front to rear",
                "object_template": {"id": template.id},
            },
            db=db,
            branch=default_branch,
            schema=node_schema,
        )


async def test_template_children_and_pool_recorded_as_side_effects(
    db: InfrahubDatabase,
    default_branch: Branch,
    device_schema: None,
    ip_namespace: Node,
    ip_prefix: Node,
    ip_address_pool: CoreIPAddressPool,
) -> None:
    """Template children and pool allocations are recorded in creation_context for event emission."""
    device_template_schema = registry.schema.get_template_schema(
        name=f"Template{TestKind.DEVICE}", branch=default_branch
    )
    device_template = await Node.init(schema=device_template_schema, db=db, branch=default_branch)
    await device_template.new(
        db=db,
        template_name="device-template-side-effects",
        manufacturer="Acme",
        weight=10,
        airflow="Front to rear",
        primary_ip_from_resource_pool={"id": ip_address_pool.id},
    )
    await device_template.save(db=db)

    intf_template_schema = registry.schema.get_template_schema(
        name=f"Template{TestKind.PHYSICAL_INTERFACE}", branch=default_branch
    )
    intf_template = await Node.init(schema=intf_template_schema, db=db, branch=default_branch)
    await intf_template.new(
        db=db, template_name="intf-tpl", name="eth0", phys_type="SFP+ (10GE)", device=device_template
    )
    await intf_template.save(db=db)

    node_schema = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)
    device = await create_node(
        data={
            "name": "device-side-effect-test",
            "manufacturer": "Acme",
            "weight": 10,
            "airflow": "Front to rear",
            "object_template": {"id": device_template.id},
        },
        db=db,
        branch=default_branch,
        schema=node_schema,
    )

    assert device._creation_context is not None
    side_effects = device._creation_context.side_effect_nodes

    intf_side_effects = [n for n in side_effects if n.get_kind() == TestKind.PHYSICAL_INTERFACE]
    assert len(intf_side_effects) == 1

    ip_side_effects = [n for n in side_effects if n.get_kind() == "IpamIPAddress"]
    assert len(ip_side_effects) == 1
