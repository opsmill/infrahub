import ipaddress

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_ipam_namespace, get_default_ipnamespace
from infrahub.core.node import Node
from infrahub.core.query.ipam import IPPrefixReconcileQuery
from infrahub.database import InfrahubDatabase


async def test_ipprefix_reconcile_simple(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01):
    await create_ipam_namespace(db=db)
    default_ipnamespace = await get_default_ipnamespace(db=db)
    registry.default_ipnamespace = default_ipnamespace.id
    prefix_140 = ip_dataset_01["net140"]
    namespace = ip_dataset_01["ns1"]
    ip_network = ipaddress.ip_network(prefix_140.prefix.value)

    query = await IPPrefixReconcileQuery.init(db=db, branch=default_branch, ip_value=ip_network, namespace=namespace)
    await query.execute(db=db)

    assert query.get_ip_node_uuid() == prefix_140.id
    assert query.get_current_parent_uuid() == ip_dataset_01["net146"].id
    assert set(query.get_current_children_uuids()) == {
        ip_dataset_01["net142"].id,
        ip_dataset_01["net144"].id,
        ip_dataset_01["net145"].id,
        ip_dataset_01["address10"].id,
    }
    assert query.get_calculated_parent_uuid() == ip_dataset_01["net146"].id
    assert set(query.get_calculated_children_uuids()) == {
        ip_dataset_01["net142"].id,
        ip_dataset_01["net144"].id,
        ip_dataset_01["net145"].id,
        ip_dataset_01["address10"].id,
    }


async def test_ipprefix_reconcile_for_new_prefix(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01):
    ns1_id = ip_dataset_01["ns1"].id
    query = await IPPrefixReconcileQuery.init(
        db=db, branch=default_branch, ip_value=ipaddress.ip_network("10.10.0.0/22"), namespace=ns1_id
    )
    await query.execute(db=db)

    assert query.get_ip_node_uuid() is None
    assert query.get_current_parent_uuid() is None
    assert query.get_current_children_uuids() == []
    assert query.get_calculated_parent_uuid() == ip_dataset_01["net140"].id
    assert set(query.get_calculated_children_uuids()) == {
        ip_dataset_01["net142"].id,
        ip_dataset_01["net144"].id,
        ip_dataset_01["net145"].id,
        ip_dataset_01["address10"].id,
    }


async def test_ipprefix_reconcile_for_new_address(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01):
    ns1_id = ip_dataset_01["ns1"].id
    query = await IPPrefixReconcileQuery.init(
        db=db, branch=default_branch, ip_value=ipaddress.ip_interface("10.10.3.0"), namespace=ns1_id
    )
    await query.execute(db=db)

    assert query.get_ip_node_uuid() is None
    assert query.get_current_parent_uuid() is None
    assert query.get_current_children_uuids() == []
    assert query.get_calculated_parent_uuid() == ip_dataset_01["net145"].id
    assert query.get_calculated_children_uuids() == []


async def test_ipprefix_reconcile_for_new_prefix_multiple_possible_parents(
    db: InfrahubDatabase, default_branch: Branch, ip_dataset_01
):
    ns1_id = ip_dataset_01["ns1"].id
    query = await IPPrefixReconcileQuery.init(
        db=db, branch=default_branch, ip_value=ipaddress.ip_network("10.10.1.8/30"), namespace=ns1_id
    )
    await query.execute(db=db)

    assert query.get_ip_node_uuid() is None
    assert query.get_current_parent_uuid() is None
    assert query.get_current_children_uuids() == []
    assert query.get_calculated_parent_uuid() == ip_dataset_01["net143"].id
    assert query.get_calculated_children_uuids() == []


async def test_ipprefix_reconcile_for_new_prefix_multiple_possible_children(
    db: InfrahubDatabase, default_branch: Branch, ip_dataset_01
):
    ns1_id = ip_dataset_01["ns1"].id
    query = await IPPrefixReconcileQuery.init(
        db=db, branch=default_branch, ip_value=ipaddress.ip_network("10.8.0.0/14"), namespace=ns1_id
    )
    await query.execute(db=db)

    assert query.get_ip_node_uuid() is None
    assert query.get_current_parent_uuid() is None
    assert query.get_current_children_uuids() == []
    assert query.get_calculated_parent_uuid() == ip_dataset_01["net146"].id
    assert query.get_calculated_children_uuids() == [ip_dataset_01["net140"].id]


async def test_ipprefix_reconcile_for_new_address_multiple_possible_children(
    db: InfrahubDatabase, default_branch: Branch, ip_dataset_01
):
    ns1_id = ip_dataset_01["ns1"].id
    query = await IPPrefixReconcileQuery.init(
        db=db, branch=default_branch, ip_value=ipaddress.ip_interface("10.8.0.0"), namespace=ns1_id
    )
    await query.execute(db=db)

    assert query.get_ip_node_uuid() is None
    assert query.get_current_parent_uuid() is None
    assert query.get_current_children_uuids() == []
    assert query.get_calculated_parent_uuid() == ip_dataset_01["net146"].id
    assert query.get_calculated_children_uuids() == []


async def test_ipprefix_reconcile_for_new_prefix_exactly_one_possible_child_address(
    db: InfrahubDatabase, default_branch: Branch, ip_dataset_01
):
    ns1_id = ip_dataset_01["ns1"].id
    query = await IPPrefixReconcileQuery.init(
        db=db, branch=default_branch, ip_value=ipaddress.ip_network("10.10.0.0/30"), namespace=ns1_id
    )
    await query.execute(db=db)

    assert query.get_ip_node_uuid() is None
    assert query.get_current_parent_uuid() is None
    assert query.get_current_children_uuids() == []
    assert query.get_calculated_parent_uuid() == ip_dataset_01["net140"].id
    assert query.get_calculated_children_uuids() == [ip_dataset_01["address10"].id]


async def test_ipprefix_reconcile_for_new_prefix_v6(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01):
    ns1_id = ip_dataset_01["ns1"].id
    query = await IPPrefixReconcileQuery.init(
        db=db, branch=default_branch, ip_value=ipaddress.ip_network("2001:db8::/50"), namespace=ns1_id
    )
    await query.execute(db=db)

    assert query.get_ip_node_uuid() is None
    assert query.get_current_parent_uuid() is None
    assert query.get_current_children_uuids() == []
    assert query.get_calculated_parent_uuid() == ip_dataset_01["net161"].id
    assert query.get_calculated_children_uuids() == [ip_dataset_01["net162"].id]


async def test_ipprefix_reconcile_for_new_address_v6(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01):
    ns1_id = ip_dataset_01["ns1"].id
    query = await IPPrefixReconcileQuery.init(
        db=db, branch=default_branch, ip_value=ipaddress.ip_interface("2001:db8::"), namespace=ns1_id
    )
    await query.execute(db=db)

    assert query.get_ip_node_uuid() is None
    assert query.get_current_parent_uuid() is None
    assert query.get_current_children_uuids() == []
    assert query.get_calculated_parent_uuid() == ip_dataset_01["net162"].id
    assert query.get_calculated_children_uuids() == []


async def test_ipprefix_reconcile_get_deleted_node_by_prefix(
    db: InfrahubDatabase, default_branch: Branch, ip_dataset_01
):
    ns1_id = ip_dataset_01["ns1"].id
    net140 = ip_dataset_01["net140"]
    await net140.delete(db=db)

    query = await IPPrefixReconcileQuery.init(
        db=db, branch=default_branch, ip_value=ipaddress.ip_network(net140.prefix.value), namespace=ns1_id
    )
    await query.execute(db=db)

    assert query.get_ip_node_uuid() is None
    assert query.get_current_parent_uuid() is None
    assert query.get_current_children_uuids() == []
    assert query.get_calculated_parent_uuid() == ip_dataset_01["net146"].id
    assert set(query.get_calculated_children_uuids()) == {
        ip_dataset_01["net142"].id,
        ip_dataset_01["net144"].id,
        ip_dataset_01["net145"].id,
        ip_dataset_01["address10"].id,
    }


async def test_ipprefix_reconcile_get_deleted_node_by_uuid(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01):
    ns1_id = ip_dataset_01["ns1"].id
    net140 = ip_dataset_01["net140"]
    await net140.delete(db=db)

    query = await IPPrefixReconcileQuery.init(
        db=db,
        branch=default_branch,
        ip_value=ipaddress.ip_network(net140.prefix.value),
        node_uuid=net140.id,
        namespace=ns1_id,
    )
    await query.execute(db=db)

    assert query.get_ip_node_uuid() == net140.id
    assert query.get_current_parent_uuid() is None
    assert query.get_current_children_uuids() == []
    assert query.get_calculated_parent_uuid() == ip_dataset_01["net146"].id
    assert set(query.get_calculated_children_uuids()) == {
        ip_dataset_01["net142"].id,
        ip_dataset_01["net144"].id,
        ip_dataset_01["net145"].id,
        ip_dataset_01["address10"].id,
    }


async def test_branch_updates_respected(db: InfrahubDatabase, branch: Branch, default_branch: Branch, ip_dataset_01):
    ns1_id = ip_dataset_01["ns1"].id
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=branch)
    address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=branch)
    await branch.rebase(db=db)
    net140 = ip_dataset_01["net140"]
    await net140.delete(db=db)
    address10 = ip_dataset_01["address10"]
    await address10.delete(db=db)
    new_parent_branch = await Node.init(db=db, schema=prefix_schema, branch=branch)
    await new_parent_branch.new(db=db, prefix="10.10.0.0/17", ip_namespace=ns1_id)
    await new_parent_branch.save(db=db)
    new_address_main = await Node.init(db=db, schema=address_schema, branch=default_branch)
    await new_address_main.new(db=db, address="10.10.0.2", ip_namespace=ns1_id)
    await new_address_main.save(db=db)
    new_address_branch = await Node.init(db=db, schema=address_schema, branch=branch)
    await new_address_branch.new(db=db, address="10.10.0.1", ip_namespace=ns1_id)
    await new_address_branch.save(db=db)

    query = await IPPrefixReconcileQuery.init(
        db=db, branch=branch, ip_value=ipaddress.ip_network("10.10.0.0/22"), namespace=ns1_id
    )
    await query.execute(db=db)

    assert query.get_ip_node_uuid() is None
    assert query.get_current_parent_uuid() is None
    assert query.get_current_children_uuids() == []
    assert query.get_calculated_parent_uuid() == new_parent_branch.id
    assert set(query.get_calculated_children_uuids()) == {
        ip_dataset_01["net142"].id,
        ip_dataset_01["net144"].id,
        ip_dataset_01["net145"].id,
        new_address_branch.id,
        new_address_main.id,
    }
