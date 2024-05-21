import ipaddress

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch, create_ipam_namespace, get_default_ipnamespace
from infrahub.core.node import Node
from infrahub.core.query.ipam import IPPrefixReconcileQuery
from infrahub.core.schema_manager import SchemaBranch
from infrahub.database import InfrahubDatabase


async def test_ipprefix_reconcile_query_simple(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01):
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


async def test_ipprefix_reconcile_query_for_new_prefix(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01):
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


async def test_ipprefix_reconcile_query_for_new_address(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01):
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


async def test_ipprefix_reconcile_query_for_new_address_with_node(
    db: InfrahubDatabase, default_branch: Branch, ip_dataset_01
):
    ns1_id = ip_dataset_01["ns1"].id
    address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)
    new_address = await Node.init(db=db, schema=address_schema)
    await new_address.new(db=db, address="10.10.3.1", ip_namespace=ns1_id)
    await new_address.save(db=db)

    query = await IPPrefixReconcileQuery.init(
        db=db, branch=default_branch, ip_value=ipaddress.ip_interface("10.10.3.1"), namespace=ns1_id
    )
    await query.execute(db=db)

    assert query.get_ip_node_uuid() == new_address.id
    assert query.get_current_parent_uuid() is None
    assert query.get_current_children_uuids() == []
    assert query.get_calculated_parent_uuid() == ip_dataset_01["net145"].id
    assert query.get_calculated_children_uuids() == []


async def test_ipprefix_reconcile_query_for_new_prefix_multiple_possible_parents(
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


async def test_ipprefix_reconcile_query_for_new_prefix_multiple_possible_children(
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


async def test_ipprefix_reconcile_query_for_new_address_multiple_possible_children(
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


async def test_ipprefix_reconcile_query_for_new_prefix_exactly_one_possible_child_address(
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


async def test_ipprefix_reconcile_query_for_new_prefix_v6(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01):
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


async def test_ipprefix_reconcile_query_for_new_address_v6(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01):
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


async def test_ipprefix_reconcile_query_get_deleted_node_by_prefix(
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


async def test_ipprefix_reconcile_query_get_deleted_node_by_uuid(
    db: InfrahubDatabase, default_branch: Branch, ip_dataset_01
):
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


async def test_branch_updates_respected(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01):
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)
    address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)

    branch2 = await create_branch(branch_name="branch2", db=db)

    ns1_id = ip_dataset_01["ns1"].id
    net140 = ip_dataset_01["net140"]
    await net140.delete(db=db)
    address10 = ip_dataset_01["address10"]
    await address10.delete(db=db)
    new_parent_branch = await Node.init(db=db, schema=prefix_schema, branch=branch2)
    await new_parent_branch.new(db=db, prefix="10.10.0.0/17", ip_namespace=ns1_id)
    await new_parent_branch.save(db=db)
    new_address_main = await Node.init(db=db, schema=address_schema, branch=default_branch)
    await new_address_main.new(db=db, address="10.10.0.2", ip_namespace=ns1_id)
    await new_address_main.save(db=db)
    new_address_branch = await Node.init(db=db, schema=address_schema, branch=branch2)
    await new_address_branch.new(db=db, address="10.10.0.1", ip_namespace=ns1_id)
    await new_address_branch.save(db=db)

    query = await IPPrefixReconcileQuery.init(
        db=db, branch=branch2, ip_value=ipaddress.ip_network("10.10.0.0/22"), namespace=ns1_id
    )
    await query.execute(db=db)

    assert query.get_ip_node_uuid() is None
    assert query.get_current_parent_uuid() is None
    assert query.get_current_children_uuids() == []
    assert query.get_calculated_parent_uuid() == new_parent_branch.id
    expected_children = {
        ip_dataset_01["net142"].id,
        ip_dataset_01["net144"].id,
        ip_dataset_01["net145"].id,
        ip_dataset_01["address10"].id,
        new_address_branch.id,
    }
    assert set(query.get_calculated_children_uuids()) == expected_children

    await branch2.rebase(db=db)

    query = await IPPrefixReconcileQuery.init(
        db=db, branch=branch2, ip_value=ipaddress.ip_network("10.10.0.0/22"), namespace=ns1_id
    )
    await query.execute(db=db)

    assert query.get_ip_node_uuid() is None
    assert query.get_current_parent_uuid() is None
    assert query.get_current_children_uuids() == []
    assert query.get_calculated_parent_uuid() == new_parent_branch.id

    expected_children_after_rebase = {
        ip_dataset_01["net142"].id,
        ip_dataset_01["net144"].id,
        ip_dataset_01["net145"].id,
        new_address_branch.id,
        new_address_main.id,
    }
    assert set(query.get_calculated_children_uuids()) == expected_children_after_rebase


async def test_reconcile_parent_child_identification(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)
    address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)
    ip_namespace = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
    await ip_namespace.new(db=db, name="ns1")
    await ip_namespace.save(db=db)
    prefix_id_map = {}
    for network in [
        "136.0.0.0/8",
        "136.128.0.0/12",
        "136.136.0.0/16",
        "136.136.128.0/20",
        "136.136.136.0/24",
        "136.136.136.128/28",
        "136.136.136.136/32",
    ]:
        prefix_node = await Node.init(db=db, schema=prefix_schema)
        await prefix_node.new(db=db, prefix=network, ip_namespace=ip_namespace)
        await prefix_node.save(db=db)
        prefix_id_map[prefix_node.id] = network
    address_id_map = {}
    for address in ["136.136.136.136/30", "136.136.136.136/31", "136.136.136.136/32"]:
        address_node = await Node.init(db=db, schema=address_schema)
        await address_node.new(db=db, address=address, ip_namespace=ip_namespace)
        await address_node.save(db=db)
        address_id_map[address_node.id] = address

    for prefix_to_check, parent, children in (
        (ipaddress.ip_network("136.0.0.0/8"), None, {"136.128.0.0/12"}),
        (ipaddress.ip_network("136.128.0.0/12"), "136.0.0.0/8", {"136.136.0.0/16"}),
        (ipaddress.ip_network("136.136.0.0/16"), "136.128.0.0/12", {"136.136.128.0/20"}),
    ):
        query = await IPPrefixReconcileQuery.init(
            db=db, branch=default_branch, namespace=ip_namespace.id, ip_value=prefix_to_check
        )
        await query.execute(db=db)
        calculated_parent_uuid = query.get_calculated_parent_uuid()
        if parent is None:
            assert calculated_parent_uuid is None
        else:
            assert parent == prefix_id_map.get(calculated_parent_uuid)
        assert children == {prefix_id_map.get(ccu) for ccu in query.get_calculated_children_uuids()}

    for prefix_to_check, parent, prefix_children, address_children in (
        (ipaddress.ip_network("136.136.136.136/32"), "136.136.136.128/28", set(), {"136.136.136.136/32"}),
        # 136.136.136.136/32 is not an address child for the below b/c its correct parent is prefix 136.136.136.136/32, not 136.136.136.136/30
        (
            ipaddress.ip_network("136.136.136.136/30"),
            "136.136.136.128/28",
            {"136.136.136.136/32"},
            {"136.136.136.136/30", "136.136.136.136/31"},
        ),
    ):
        query = await IPPrefixReconcileQuery.init(
            db=db, branch=default_branch, namespace=ip_namespace.id, ip_value=prefix_to_check
        )
        await query.execute(db=db)

        calculated_parent_uuid = query.get_calculated_parent_uuid()
        if parent is None:
            assert calculated_parent_uuid is None
        else:
            assert parent == prefix_id_map.get(calculated_parent_uuid)
        assert prefix_children == {
            prefix_id_map[ccu] for ccu in query.get_calculated_children_uuids() if ccu in prefix_id_map
        }
        assert address_children == {
            address_id_map[ccu] for ccu in query.get_calculated_children_uuids() if ccu in address_id_map
        }
