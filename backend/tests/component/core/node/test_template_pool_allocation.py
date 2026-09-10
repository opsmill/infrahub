from __future__ import annotations

import copy
from ipaddress import ip_interface
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind, RelationshipCardinality
from infrahub.core.initialization import initialize_registry
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.create import create_node
from infrahub.core.node.resource_manager.ip_address_pool import CoreIPAddressPool
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import AttributeSchema, RelationshipSchema
from infrahub.exceptions import NodeNotFoundError, PoolExhaustedError, ValidationError
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
    await small_prefix.new(db=db, prefix="10.10.3.8/30", ip_namespace=ip_namespace, parent=ip_prefix, is_pool=False)
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


async def test_template_with_number_pool_relationship_does_not_allocate(
    db: InfrahubDatabase, default_branch: Branch, device_with_rack_unit_schema: None, number_pool: CoreNumberPool
) -> None:
    """Template with _from_resource_pool relationship should store pool reference but not allocate."""
    template_schema = registry.schema.get_template_schema(name="TemplateTestingDevice", branch=default_branch)

    template = await Node.init(schema=template_schema, db=db, branch=default_branch)
    await template.new(
        db=db,
        template_name="device-template-with-pool-attr",
        rack_unit_from_resource_pool={"id": number_pool.id},
    )
    await template.save(db=db)

    assert template.id is not None
    assert template.rack_unit.value is None

    pool_rel = await template.rack_unit_from_resource_pool.get_peer(db=db)
    assert pool_rel is not None
    assert pool_rel.id == number_pool.id


async def test_template_from_pool_on_attribute_raises_validation_error(
    db: InfrahubDatabase, default_branch: Branch, device_with_rack_unit_schema: None, number_pool: CoreNumberPool
) -> None:
    """Using from_pool on a template attribute should raise ValidationError."""
    template_schema = registry.schema.get_template_schema(name=f"Template{TestKind.DEVICE}", branch=default_branch)
    template = await Node.init(schema=template_schema, db=db, branch=default_branch)

    with pytest.raises(
        ValidationError,
        match=r"'from_pool' is not supported on template attributes\. Set the 'rack_unit_from_resource_pool' relationship on this template instead\.",
    ):
        await template.new(
            db=db, template_name="device-template-from-pool-attr", rack_unit={"from_pool": {"id": number_pool.id}}
        )


async def test_template_from_pool_on_relationship_raises_validation_error(
    db: InfrahubDatabase,
    default_branch: Branch,
    device_schema: None,
    ip_address_pool: CoreIPAddressPool,
) -> None:
    """Using from_pool on a template relationship should raise ValidationError."""
    template_schema = registry.schema.get_template_schema(name=f"Template{TestKind.DEVICE}", branch=default_branch)
    template = await Node.init(schema=template_schema, db=db, branch=default_branch)

    with pytest.raises(
        ValidationError,
        match=r"'from_pool' is not supported on template relationships\. "
        r"Set the 'primary_ip_from_resource_pool' relationship on this template instead\.",
    ):
        await template.new(
            db=db, template_name="device-template-from-pool-rel", primary_ip={"from_pool": {"id": ip_address_pool.id}}
        )


async def test_object_from_template_with_number_pool_allocates_value(
    db: InfrahubDatabase, default_branch: Branch, device_with_rack_unit_schema: None, number_pool: CoreNumberPool
) -> None:
    """Object created from template should allocate from the NumberPool via _from_resource_pool relationship."""
    template_schema = registry.schema.get_template_schema(name=f"Template{TestKind.DEVICE}", branch=default_branch)
    node_schema = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)

    template = await Node.init(schema=template_schema, db=db, branch=default_branch)
    await template.new(
        db=db,
        template_name="device-template-for-number-allocation",
        rack_unit_from_resource_pool={"id": number_pool.id},
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
        db=db,
        template_name="device-template-explicit-override",
        rack_unit_from_resource_pool={"id": number_pool.id},
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
    """Creating object from template raises PoolExhaustedError when NumberPool is exhausted."""
    small_pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await small_pool.new(
        db=db, name="small-rack-unit-pool", node=TestKind.DEVICE, node_attribute="rack_unit", start_range=1, end_range=2
    )
    await small_pool.save(db=db)

    template_schema = registry.schema.get_template_schema(name=f"Template{TestKind.DEVICE}", branch=default_branch)
    node_schema = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)

    template = await Node.init(schema=template_schema, db=db, branch=default_branch)
    await template.new(
        db=db,
        template_name="device-template-small-number-pool",
        rack_unit_from_resource_pool={"id": small_pool.id},
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

    with pytest.raises(PoolExhaustedError):
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


async def test_create_template_with_invalid_number_pool_id(
    db: InfrahubDatabase, default_branch: Branch, device_with_rack_unit_schema: None
) -> None:
    """Saving a template with _from_resource_pool referencing a nonexistent pool should fail."""
    fake_pool_id = str(uuid4())

    template_schema = registry.schema.get_template_schema(name=f"Template{TestKind.DEVICE}", branch=default_branch)
    template = await Node.init(schema=template_schema, db=db, branch=default_branch)
    await template.new(
        db=db,
        template_name="device-template-bad-pool",
        rack_unit_from_resource_pool=fake_pool_id,
    )
    with pytest.raises(NodeNotFoundError):
        await template.save(db=db)


@pytest.fixture
async def device_schema_with_component_pools(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
    init_nodes_registry: None,
) -> None:
    """Put a primary_ip on both levels of components, so one pool can serve the two of them."""
    schema = copy.deepcopy(DEVICE_SCHEMA)
    for kind in (TestKind.PHYSICAL_INTERFACE, TestKind.SFP):
        node = next(n for n in schema.nodes if n.kind == kind)
        node.relationships.append(
            RelationshipSchema(
                name="primary_ip", peer="IpamIPAddress", cardinality=RelationshipCardinality.ONE, optional=True
            )
        )
    registry.schema.register_schema(schema=schema, branch=default_branch.name)


async def test_one_pool_shared_by_two_component_levels_allocates_depth_first(
    db: InfrahubDatabase,
    default_branch: Branch,
    device_schema_with_component_pools: None,
    ip_address_pool: CoreIPAddressPool,
) -> None:
    """A component and the component it holds take adjacent addresses from a shared pool.

    The device template carries interfaces, each interface carries an SFP, and one pool serves both
    levels. The pool hands the next free address to each caller in turn, so the order the components
    are created in decides which address each one gets. An interface and its own SFP are created one
    after the other, which is what keeps their two addresses next to each other.
    """
    template_schema = registry.schema.get_template_schema(name=f"Template{TestKind.DEVICE}", branch=default_branch)
    interface_template_schema = registry.schema.get_template_schema(
        name=f"Template{TestKind.PHYSICAL_INTERFACE}", branch=default_branch
    )
    sfp_template_schema = registry.schema.get_template_schema(name=f"Template{TestKind.SFP}", branch=default_branch)

    template = await Node.init(schema=template_schema, db=db, branch=default_branch)
    await template.new(db=db, template_name="pool-order-template", manufacturer="Acme", weight=1, airflow="Passive")
    await template.save(db=db)

    for idx in range(3):
        interface = await Node.init(schema=interface_template_schema, db=db, branch=default_branch)
        await interface.new(
            db=db,
            template_name=f"pool-order-eth{idx}",
            name=f"eth{idx}",
            phys_type="SFP+ (10GE)",
            device=template.id,
            primary_ip_from_resource_pool={"id": ip_address_pool.id},
        )
        await interface.save(db=db)

        sfp = await Node.init(schema=sfp_template_schema, db=db, branch=default_branch)
        await sfp.new(
            db=db,
            template_name=f"pool-order-eth{idx}-sfp",
            phys_type="SFP+ (10GE)",
            serial_number=f"pool-order-sn{idx}",
            interface=interface.id,
            primary_ip_from_resource_pool={"id": ip_address_pool.id},
        )
        await sfp.save(db=db)

    node_schema = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)
    device = await create_node(
        data={"name": "pool-order-device", "object_template": {"id": template.id}},
        db=db,
        branch=default_branch,
        schema=node_schema,
    )

    reloaded = await NodeManager.get_one(db=db, id=device.id, branch=default_branch, raise_on_error=True)
    allocated: dict[str, tuple[int, int]] = {}
    for interface in (await reloaded.interfaces.get_peers(db=db)).values():
        sfp = await interface.sfp.get_peer(db=db)
        assert sfp is not None, "the second level of the template was not materialized"
        interface_ip = await interface.primary_ip.get_peer(db=db)
        sfp_ip = await sfp.primary_ip.get_peer(db=db)
        assert interface_ip is not None, f"{interface.name.value} was not allocated an address"
        assert sfp_ip is not None, f"the SFP of {interface.name.value} was not allocated an address"
        allocated[interface.name.value] = (
            int(ip_interface(interface_ip.address.value).ip),
            int(ip_interface(sfp_ip.address.value).ip),
        )

    assert len(allocated) == 3
    addresses = [address for pair in allocated.values() for address in pair]
    assert len(set(addresses)) == 6, f"an address was handed out twice: {allocated}"

    # Which interface the pool serves first is not fixed, so only the adjacency is asserted.
    for name, (interface_address, sfp_address) in sorted(allocated.items()):
        assert sfp_address == interface_address + 1, (
            f"{name} took {interface_address} and its SFP took {sfp_address}: the SFP is no longer "
            f"allocated right after the interface holding it"
        )
