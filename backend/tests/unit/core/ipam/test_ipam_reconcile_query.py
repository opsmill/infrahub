import ipaddress
from uuid import uuid4

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, SchemaPathType
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.initialization import create_branch, get_default_ipnamespace
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.query.ipam import IPPrefixReconcileQuery
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry


def randomized_branch_name(branch_name: str) -> str:
    return f"{branch_name}_{uuid4().hex[:8]}"


async def test_ipprefix_reconcile_query_simple(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01) -> None:
    default_ipnamespace = await get_default_ipnamespace(db=db)
    registry.default_ipnamespace = default_ipnamespace.id
    prefix_140 = ip_dataset_01["net140"]
    namespace = ip_dataset_01["ns1"]
    ip_network = ipaddress.ip_network(prefix_140.prefix.value)

    query = await IPPrefixReconcileQuery.init(db=db, branch=default_branch, ip_value=ip_network, namespace=namespace)
    await query.execute(db=db)

    data = query.get_data()
    assert data is not None
    assert data.ip_node_uuid == prefix_140.id
    assert data.current_parent_uuid == ip_dataset_01["net146"].id
    assert set(data.current_children_uuids) == {
        ip_dataset_01["net142"].id,
        ip_dataset_01["net144"].id,
        ip_dataset_01["net145"].id,
        ip_dataset_01["address10"].id,
    }
    assert data.calculated_parent_uuid == ip_dataset_01["net146"].id
    assert set(data.calculated_children_uuids) == {
        ip_dataset_01["net142"].id,
        ip_dataset_01["net144"].id,
        ip_dataset_01["net145"].id,
        ip_dataset_01["address10"].id,
    }


async def test_ipprefix_reconcile_query_for_new_prefix(
    db: InfrahubDatabase, default_branch: Branch, ip_dataset_01
) -> None:
    ns1_id = ip_dataset_01["ns1"].id
    query = await IPPrefixReconcileQuery.init(
        db=db, branch=default_branch, ip_value=ipaddress.ip_network("10.10.0.0/22"), namespace=ns1_id
    )
    await query.execute(db=db)

    data = query.get_data()
    assert data is not None
    assert data.ip_node_uuid is None
    assert data.current_parent_uuid is None
    assert data.current_children_uuids == ()
    assert data.calculated_parent_uuid == ip_dataset_01["net140"].id
    assert set(data.calculated_children_uuids) == {
        ip_dataset_01["net142"].id,
        ip_dataset_01["net144"].id,
        ip_dataset_01["net145"].id,
        ip_dataset_01["address10"].id,
    }


async def test_ipprefix_reconcile_query_for_new_address(
    db: InfrahubDatabase, default_branch: Branch, ip_dataset_01
) -> None:
    ns1_id = ip_dataset_01["ns1"].id
    query = await IPPrefixReconcileQuery.init(
        db=db, branch=default_branch, ip_value=ipaddress.ip_interface("10.10.3.0"), namespace=ns1_id
    )
    await query.execute(db=db)

    data = query.get_data()
    assert data is not None
    assert data.ip_node_uuid is None
    assert data.current_parent_uuid is None
    assert data.current_children_uuids == ()
    assert data.calculated_parent_uuid == ip_dataset_01["net145"].id
    assert data.calculated_children_uuids == ()


async def test_ipprefix_reconcile_query_for_new_address_with_node(
    db: InfrahubDatabase, default_branch: Branch, ip_dataset_01
) -> None:
    ns1_id = ip_dataset_01["ns1"].id
    address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)
    new_address = await Node.init(db=db, schema=address_schema)
    await new_address.new(db=db, address="10.10.3.1", ip_namespace=ns1_id)
    await new_address.save(db=db)

    query = await IPPrefixReconcileQuery.init(
        db=db, branch=default_branch, ip_value=ipaddress.ip_interface("10.10.3.1"), namespace=ns1_id
    )
    await query.execute(db=db)

    data = query.get_data()
    assert data is not None
    assert data.ip_node_uuid == new_address.id
    assert data.current_parent_uuid is None
    assert data.current_children_uuids == ()
    assert data.calculated_parent_uuid == ip_dataset_01["net145"].id
    assert data.calculated_children_uuids == ()


async def test_ipprefix_reconcile_query_for_new_prefix_multiple_possible_parents(
    db: InfrahubDatabase, default_branch: Branch, ip_dataset_01
) -> None:
    ns1_id = ip_dataset_01["ns1"].id
    query = await IPPrefixReconcileQuery.init(
        db=db, branch=default_branch, ip_value=ipaddress.ip_network("10.10.1.8/30"), namespace=ns1_id
    )
    await query.execute(db=db)

    data = query.get_data()
    assert data is not None
    assert data.ip_node_uuid is None
    assert data.current_parent_uuid is None
    assert data.current_children_uuids == ()
    assert data.calculated_parent_uuid == ip_dataset_01["net143"].id
    assert data.calculated_children_uuids == ()


async def test_ipprefix_reconcile_query_for_new_prefix_multiple_possible_children(
    db: InfrahubDatabase, default_branch: Branch, ip_dataset_01
) -> None:
    ns1_id = ip_dataset_01["ns1"].id
    query = await IPPrefixReconcileQuery.init(
        db=db, branch=default_branch, ip_value=ipaddress.ip_network("10.8.0.0/14"), namespace=ns1_id
    )
    await query.execute(db=db)

    data = query.get_data()
    assert data is not None
    assert data.ip_node_uuid is None
    assert data.current_parent_uuid is None
    assert data.current_children_uuids == ()
    assert data.calculated_parent_uuid == ip_dataset_01["net146"].id
    assert data.calculated_children_uuids == (ip_dataset_01["net140"].id,)


async def test_ipprefix_reconcile_query_for_new_address_multiple_possible_children(
    db: InfrahubDatabase, default_branch: Branch, ip_dataset_01
) -> None:
    ns1_id = ip_dataset_01["ns1"].id
    query = await IPPrefixReconcileQuery.init(
        db=db, branch=default_branch, ip_value=ipaddress.ip_interface("10.8.0.0"), namespace=ns1_id
    )
    await query.execute(db=db)

    data = query.get_data()
    assert data is not None
    assert data.ip_node_uuid is None
    assert data.current_parent_uuid is None
    assert data.current_children_uuids == ()
    assert data.calculated_parent_uuid == ip_dataset_01["net146"].id
    assert data.calculated_children_uuids == ()


async def test_ipprefix_reconcile_query_for_new_prefix_exactly_one_possible_child_address(
    db: InfrahubDatabase, default_branch: Branch, ip_dataset_01
) -> None:
    ns1_id = ip_dataset_01["ns1"].id
    query = await IPPrefixReconcileQuery.init(
        db=db, branch=default_branch, ip_value=ipaddress.ip_network("10.10.0.0/30"), namespace=ns1_id
    )
    await query.execute(db=db)

    data = query.get_data()
    assert data is not None
    assert data.ip_node_uuid is None
    assert data.current_parent_uuid is None
    assert data.current_children_uuids == ()
    assert data.calculated_parent_uuid == ip_dataset_01["net140"].id
    assert data.calculated_children_uuids == (ip_dataset_01["address10"].id,)


async def test_ipprefix_reconcile_query_for_new_prefix_v6(
    db: InfrahubDatabase, default_branch: Branch, ip_dataset_01
) -> None:
    ns1_id = ip_dataset_01["ns1"].id
    query = await IPPrefixReconcileQuery.init(
        db=db, branch=default_branch, ip_value=ipaddress.ip_network("2001:db8::/50"), namespace=ns1_id
    )
    await query.execute(db=db)

    data = query.get_data()
    assert data is not None
    assert data.ip_node_uuid is None
    assert data.current_parent_uuid is None
    assert data.current_children_uuids == ()
    assert data.calculated_parent_uuid == ip_dataset_01["net161"].id
    assert data.calculated_children_uuids == (ip_dataset_01["net162"].id,)


async def test_ipprefix_reconcile_query_for_new_address_v6(
    db: InfrahubDatabase, default_branch: Branch, ip_dataset_01
) -> None:
    ns1_id = ip_dataset_01["ns1"].id
    query = await IPPrefixReconcileQuery.init(
        db=db, branch=default_branch, ip_value=ipaddress.ip_interface("2001:db8::"), namespace=ns1_id
    )
    await query.execute(db=db)

    data = query.get_data()
    assert data is not None
    assert data.ip_node_uuid is None
    assert data.current_parent_uuid is None
    assert data.current_children_uuids == ()
    assert data.calculated_parent_uuid == ip_dataset_01["net162"].id
    assert data.calculated_children_uuids == ()


async def test_ipprefix_reconcile_query_get_deleted_node_by_prefix(
    db: InfrahubDatabase, default_branch: Branch, ip_dataset_01
) -> None:
    ns1_id = ip_dataset_01["ns1"].id
    net140 = ip_dataset_01["net140"]
    await net140.delete(db=db)

    query = await IPPrefixReconcileQuery.init(
        db=db, branch=default_branch, ip_value=ipaddress.ip_network(net140.prefix.value), namespace=ns1_id
    )
    await query.execute(db=db)

    data = query.get_data()
    assert data is not None
    assert data.ip_node_uuid is None
    assert data.current_parent_uuid is None
    assert data.current_children_uuids == ()
    assert data.calculated_parent_uuid == ip_dataset_01["net146"].id
    assert set(data.calculated_children_uuids) == {
        ip_dataset_01["net142"].id,
        ip_dataset_01["net144"].id,
        ip_dataset_01["net145"].id,
        ip_dataset_01["address10"].id,
    }


async def test_ipprefix_reconcile_query_get_deleted_node_by_uuid(
    db: InfrahubDatabase, default_branch: Branch, ip_dataset_01
) -> None:
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

    data = query.get_data()
    assert data is not None
    assert data.ip_node_uuid == net140.id
    assert data.current_parent_uuid is None
    assert data.current_children_uuids == ()
    assert data.calculated_parent_uuid == ip_dataset_01["net146"].id
    assert set(data.calculated_children_uuids) == {
        ip_dataset_01["net142"].id,
        ip_dataset_01["net144"].id,
        ip_dataset_01["net145"].id,
        ip_dataset_01["address10"].id,
    }


async def test_ipprefix_reconcile_query_deleted_children_ignored_on_branch(
    db: InfrahubDatabase, ip_dataset_01: dict[str, Node]
) -> None:
    branch = await create_branch(db=db, branch_name=randomized_branch_name("branch2"))

    ns1_id = ip_dataset_01["ns1"].id
    net140_branch = await NodeManager.get_one(db=db, branch=branch, id=ip_dataset_01["net140"].id)
    await net140_branch.delete(db=db)
    net145_branch = await NodeManager.get_one(db=db, branch=branch, id=ip_dataset_01["net145"].id)
    await net145_branch.delete(db=db)
    address_10_branch = await NodeManager.get_one(db=db, branch=branch, id=ip_dataset_01["address10"].id)
    await address_10_branch.delete(db=db)

    query = await IPPrefixReconcileQuery.init(
        db=db,
        branch=branch,
        ip_value=ipaddress.ip_network(net140_branch.prefix.value),
        node_uuid=net140_branch.id,
        namespace=ns1_id,
    )
    await query.execute(db=db)

    data = query.get_data()
    assert data is not None
    assert data.ip_node_uuid == net140_branch.id
    assert data.current_parent_uuid is None
    assert data.current_children_uuids == ()
    assert data.calculated_parent_uuid == ip_dataset_01["net146"].id
    assert set(data.calculated_children_uuids) == {
        ip_dataset_01["net142"].id,
        ip_dataset_01["net144"].id,
        # should not be included b/c the address was deleted
        # ip_dataset_01["net145"].id,
        # ip_dataset_01["address10"].id
    }


async def test_ipprefix_reconcile_query_deleted_parent_ignored_on_branch(
    db: InfrahubDatabase, ip_dataset_01: dict[str, Node]
) -> None:
    branch = await create_branch(db=db, branch_name=randomized_branch_name("branch2"))

    ns1_id = ip_dataset_01["ns1"].id
    net140_branch = await NodeManager.get_one(db=db, branch=branch, id=ip_dataset_01["net140"].id)
    await net140_branch.delete(db=db)
    net146_branch = await NodeManager.get_one(db=db, branch=branch, id=ip_dataset_01["net146"].id)
    await net146_branch.delete(db=db)

    query = await IPPrefixReconcileQuery.init(
        db=db,
        branch=branch,
        ip_value=ipaddress.ip_network(net140_branch.prefix.value),
        node_uuid=net140_branch.id,
        namespace=ns1_id,
    )
    await query.execute(db=db)

    data = query.get_data()
    assert data is not None
    assert data.ip_node_uuid == net140_branch.id
    assert data.current_parent_uuid is None
    assert data.current_children_uuids == ()
    assert data.calculated_parent_uuid is None
    assert set(data.calculated_children_uuids) == {
        ip_dataset_01["net142"].id,
        ip_dataset_01["net144"].id,
        ip_dataset_01["net145"].id,
        ip_dataset_01["address10"].id,
    }


async def test_branch_updates_respected(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01) -> None:
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)
    address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)

    branch2 = await create_branch(branch_name=randomized_branch_name("branch2"), db=db)

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

    data = query.get_data()
    assert data is not None
    assert data.ip_node_uuid is None
    assert data.current_parent_uuid is None
    assert data.current_children_uuids == ()
    assert data.calculated_parent_uuid == new_parent_branch.id
    expected_children = {
        ip_dataset_01["net142"].id,
        ip_dataset_01["net144"].id,
        ip_dataset_01["net145"].id,
        ip_dataset_01["address10"].id,
        new_address_branch.id,
    }
    assert set(data.calculated_children_uuids) == expected_children
    query = await IPPrefixReconcileQuery.init(
        db=db, branch=branch2, ip_value=ipaddress.ip_interface("10.10.0.1"), namespace=ns1_id
    )
    await query.execute(db=db)

    data = query.get_data()
    assert data is not None
    assert data.ip_node_uuid == new_address_branch.id
    assert data.current_parent_uuid is None
    assert data.current_children_uuids == ()
    assert data.calculated_parent_uuid == new_parent_branch.id
    assert data.calculated_children_uuids == ()

    await branch2.rebase(db=db)

    query = await IPPrefixReconcileQuery.init(
        db=db, branch=branch2, ip_value=ipaddress.ip_network("10.10.0.0/22"), namespace=ns1_id
    )
    await query.execute(db=db)

    data = query.get_data()
    assert data is not None
    assert data.ip_node_uuid is None
    assert data.current_parent_uuid is None
    assert data.current_children_uuids == ()
    assert data.calculated_parent_uuid == new_parent_branch.id

    expected_children_after_rebase = {
        ip_dataset_01["net142"].id,
        ip_dataset_01["net144"].id,
        ip_dataset_01["net145"].id,
        new_address_branch.id,
        new_address_main.id,
    }
    assert set(data.calculated_children_uuids) == expected_children_after_rebase
    query = await IPPrefixReconcileQuery.init(
        db=db, branch=branch2, ip_value=ipaddress.ip_interface("10.10.0.2"), namespace=ns1_id
    )
    await query.execute(db=db)

    data = query.get_data()
    assert data is not None
    assert data.ip_node_uuid == new_address_main.id
    assert data.current_parent_uuid is None
    assert data.current_children_uuids == ()
    assert data.calculated_parent_uuid == new_parent_branch.id
    assert data.calculated_children_uuids == ()


async def test_reconcile_parent_child_identification(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
) -> None:
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
        data = query.get_data()
        assert data is not None
        if parent is None:
            assert data.calculated_parent_uuid is None
        else:
            assert parent == prefix_id_map.get(data.calculated_parent_uuid)
        assert children == {prefix_id_map.get(ccu) for ccu in data.calculated_children_uuids}

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

        data = query.get_data()
        assert data is not None
        if parent is None:
            assert data.calculated_parent_uuid is None
        else:
            assert parent == prefix_id_map.get(data.calculated_parent_uuid)
        assert prefix_children == {prefix_id_map[ccu] for ccu in data.calculated_children_uuids if ccu in prefix_id_map}
        assert address_children == {
            address_id_map[ccu] for ccu in data.calculated_children_uuids if ccu in address_id_map
        }


async def test_address_cannot_be_parent(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
) -> None:
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)
    address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)
    ip_namespace = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
    await ip_namespace.new(db=db, name="ns1")
    await ip_namespace.save(db=db)
    prefix_node = await Node.init(db=db, schema=prefix_schema)
    await prefix_node.new(db=db, prefix="172.20.20.0/27", ip_namespace=ip_namespace)
    await prefix_node.save(db=db)
    address_node = await Node.init(db=db, schema=address_schema)
    await address_node.new(db=db, address="172.20.20.0/24", ip_namespace=ip_namespace)
    await address_node.save(db=db)

    for ip_value in (ipaddress.ip_interface("172.20.20.0/24"), ipaddress.ip_network("172.20.20.0/27")):
        query = await IPPrefixReconcileQuery.init(
            db=db, branch=default_branch, namespace=ip_namespace.id, ip_value=ip_value
        )
        await query.execute(db=db)
        data = query.get_data()
        assert data is not None
        assert data.calculated_parent_uuid is None
        assert data.calculated_children_uuids == ()


async def test_adjacent_parents_and_addresses(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
) -> None:
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)
    address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)
    ip_namespace = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
    await ip_namespace.new(db=db, name="ns1")
    await ip_namespace.save(db=db)
    prefix_id_map = {}
    for prefix in ("192.0.2.0/32", "192.0.2.0/31", "192.0.2.0/30", "192.0.2.0/29"):
        prefix_node = await Node.init(db=db, schema=prefix_schema)
        await prefix_node.new(db=db, prefix=prefix, ip_namespace=ip_namespace)
        await prefix_node.save(db=db)
        prefix_id_map[prefix_node.id] = prefix
    address_id_map = {}
    for i in range(7):
        address = f"192.0.2.{i}/31"
        address_node = await Node.init(db=db, schema=address_schema)
        await address_node.new(db=db, address=address, ip_namespace=ip_namespace)
        await address_node.save(db=db)
        address_id_map[address_node.id] = address

    # test prefix 192.0.2.0/32
    query = await IPPrefixReconcileQuery.init(
        db=db, branch=default_branch, namespace=ip_namespace.id, ip_value=ipaddress.ip_network("192.0.2.0/32")
    )
    await query.execute(db=db)
    data = query.get_data()
    assert data is not None
    assert prefix_id_map[data.calculated_parent_uuid] == "192.0.2.0/31"
    assert data.calculated_children_uuids == ()
    # test prefix 192.0.2.0/31
    query = await IPPrefixReconcileQuery.init(
        db=db, branch=default_branch, namespace=ip_namespace.id, ip_value=ipaddress.ip_network("192.0.2.0/31")
    )
    await query.execute(db=db)
    data = query.get_data()
    assert data is not None
    assert prefix_id_map[data.calculated_parent_uuid] == "192.0.2.0/30"
    assert {address_id_map[ccu] for ccu in data.calculated_children_uuids if ccu in address_id_map} == {
        "192.0.2.0/31",
        "192.0.2.1/31",
    }
    assert {prefix_id_map[ccu] for ccu in data.calculated_children_uuids if ccu in prefix_id_map} == {"192.0.2.0/32"}
    # test prefix 192.0.2.0/30
    query = await IPPrefixReconcileQuery.init(
        db=db, branch=default_branch, namespace=ip_namespace.id, ip_value=ipaddress.ip_network("192.0.2.0/30")
    )
    await query.execute(db=db)
    data = query.get_data()
    assert data is not None
    assert prefix_id_map[data.calculated_parent_uuid] == "192.0.2.0/29"
    assert {address_id_map[ccu] for ccu in data.calculated_children_uuids if ccu in address_id_map} == {
        "192.0.2.2/31",
        "192.0.2.3/31",
    }
    assert {prefix_id_map[ccu] for ccu in data.calculated_children_uuids if ccu in prefix_id_map} == {"192.0.2.0/31"}
    # test prefix 192.0.2.0/29
    query = await IPPrefixReconcileQuery.init(
        db=db, branch=default_branch, namespace=ip_namespace.id, ip_value=ipaddress.ip_network("192.0.2.0/29")
    )
    await query.execute(db=db)
    data = query.get_data()
    assert data is not None
    assert data.calculated_parent_uuid is None
    assert {address_id_map[ccu] for ccu in data.calculated_children_uuids if ccu in address_id_map} == {
        "192.0.2.4/31",
        "192.0.2.5/31",
        "192.0.2.6/31",
    }
    assert {prefix_id_map[ccu] for ccu in data.calculated_children_uuids if ccu in prefix_id_map} == {"192.0.2.0/30"}
    # test children address find correct parent
    for address in ("192.0.2.0/31", "192.0.2.1/31"):
        query = await IPPrefixReconcileQuery.init(
            db=db, branch=default_branch, namespace=ip_namespace.id, ip_value=ipaddress.ip_interface(address)
        )
        await query.execute(db=db)
        data = query.get_data()
        assert data is not None
        assert prefix_id_map[data.calculated_parent_uuid] == "192.0.2.0/31"
        assert data.calculated_children_uuids == ()
    for address in ("192.0.2.2/31", "192.0.2.3/31"):
        query = await IPPrefixReconcileQuery.init(
            db=db, branch=default_branch, namespace=ip_namespace.id, ip_value=ipaddress.ip_interface(address)
        )
        await query.execute(db=db)
        data = query.get_data()
        assert data is not None
        assert prefix_id_map[data.calculated_parent_uuid] == "192.0.2.0/30"
        assert data.calculated_children_uuids == ()
    for address in ("192.0.2.4/31", "192.0.2.5/31", "192.0.2.6/31"):
        query = await IPPrefixReconcileQuery.init(
            db=db, branch=default_branch, namespace=ip_namespace.id, ip_value=ipaddress.ip_interface(address)
        )
        await query.execute(db=db)
        data = query.get_data()
        assert data is not None
        assert prefix_id_map[data.calculated_parent_uuid] == "192.0.2.0/29"
        assert data.calculated_children_uuids == ()


async def test_root_ip_prefix_exists_reconcile(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
) -> None:
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)
    ip_namespace = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
    await ip_namespace.new(db=db, name="ns1")
    await ip_namespace.save(db=db)
    root_prefix_node = await Node.init(db=db, schema=prefix_schema)
    await root_prefix_node.new(db=db, prefix="0.0.0.0/0", ip_namespace=ip_namespace)
    await root_prefix_node.save(db=db)

    query = await IPPrefixReconcileQuery.init(
        db=db, branch=default_branch, namespace=ip_namespace.id, ip_value=ipaddress.ip_network("192.168.0.0/16")
    )
    await query.execute(db=db)
    data = query.get_data()
    assert data is not None
    assert data.calculated_parent_uuid == root_prefix_node.id
    assert data.calculated_children_uuids == ()


async def test_root_ip_prefix_added_reconcile(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
) -> None:
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)
    ip_namespace = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
    await ip_namespace.new(db=db, name="ns1")
    await ip_namespace.save(db=db)
    child_prefix_node = await Node.init(db=db, schema=prefix_schema)
    await child_prefix_node.new(db=db, prefix="192.168.0.0/16", ip_namespace=ip_namespace)
    await child_prefix_node.save(db=db)

    query = await IPPrefixReconcileQuery.init(
        db=db, branch=default_branch, namespace=ip_namespace.id, ip_value=ipaddress.ip_network("0.0.0.0/0")
    )
    await query.execute(db=db)
    data = query.get_data()
    assert data is not None
    assert data.calculated_parent_uuid is None
    assert data.calculated_children_uuids == (child_prefix_node.id,)


async def test_reconcile_query_on_migrated_kind_node(
    db: InfrahubDatabase, default_branch: Branch, ip_dataset_01
) -> None:
    default_ipnamespace = await get_default_ipnamespace(db=db)
    registry.default_ipnamespace = default_ipnamespace.id
    prefix_140 = ip_dataset_01["net140"]
    namespace = ip_dataset_01["ns1"]

    branch = await create_branch(db=db, branch_name=randomized_branch_name("migrated-branch"))

    # update IpamIPPrefix schema name
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch, duplicate=True)
    prefix_schema.name = "IPPrefixTwo"
    assert prefix_schema.kind == "IpamIPPrefixTwo"
    migration = NodeKindUpdateMigration(
        previous_node_schema=registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch),
        new_node_schema=prefix_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="IpamIPPrefixTwo", field_name="name"),
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=branch)
    assert not execution_result.errors

    registry.schema.set(name="IpamIPPrefixTwo", schema=prefix_schema, branch=branch.name)
    wrong_parent = await Node.init(db=db, schema=prefix_schema, branch=branch)
    await wrong_parent.new(db=db, prefix="192.168.0.0/16", ip_namespace=namespace)
    await wrong_parent.save(db=db)
    wrong_child = await Node.init(db=db, schema=prefix_schema, branch=branch)
    await wrong_child.new(db=db, prefix="192.168.0.0/24", ip_namespace=namespace)
    await wrong_child.save(db=db)
    branch_net_140 = await NodeManager.get_one(db=db, branch=branch, id=prefix_140.id)
    await branch_net_140.parent.update(db=db, data=wrong_parent.id)
    await branch_net_140.children.update(db=db, data=[wrong_child.id])
    await branch_net_140.ip_addresses.update(db=db, data=[None])
    await branch_net_140.save(db=db)

    ip_network = ipaddress.ip_network(prefix_140.prefix.value)
    query = await IPPrefixReconcileQuery.init(db=db, branch=branch, ip_value=ip_network, namespace=namespace)
    await query.execute(db=db)

    data = query.get_data()
    assert data is not None
    assert data.ip_node_uuid == prefix_140.id
    # the wrong parent and wrong child confirm that we retrieved the correct Node from the database: the IpamIPPrefixTwo instance
    assert data.current_parent_uuid == wrong_parent.id
    assert set(data.current_children_uuids) == {wrong_child.id}
    assert data.calculated_parent_uuid == ip_dataset_01["net146"].id
    assert set(data.calculated_children_uuids) == {
        ip_dataset_01["net142"].id,
        ip_dataset_01["net144"].id,
        ip_dataset_01["net145"].id,
        ip_dataset_01["address10"].id,
    }


async def test_reconcile_query_for_address_with_prefix_added_on_branch_and_merged(
    db: InfrahubDatabase, default_branch: Branch, ip_dataset_01
):
    """
    Test for bug that could cause an IP address to be its own parent after an update on a branch was merged
    """
    default_ipnamespace = await get_default_ipnamespace(db=db)
    registry.default_ipnamespace = default_ipnamespace.id
    address_10 = ip_dataset_01["address10"]
    namespace = ip_dataset_01["ns1"]

    branch = await create_branch(db=db, branch_name=randomized_branch_name("address-parent"))

    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=branch)
    new_prefix = await Node.init(db=db, branch=branch, schema=prefix_schema)
    await new_prefix.new(db=db, prefix="10.10.0.0/28", ip_namespace=namespace, ip_addresses=[address_10.id])
    await new_prefix.save(db=db)

    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    diff_merger = await component_registry.get_component(DiffMerger, db=db, branch=branch)
    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    await diff_merger.merge_graph(at=Timestamp())
    # get branch to make sure branched_from is refreshed
    branch = await Branch.get_by_name(db=db, name=branch.name)

    ip_interface = ipaddress.ip_interface(address_10.address.value)
    query = await IPPrefixReconcileQuery.init(db=db, branch=branch, ip_value=ip_interface, namespace=namespace)
    await query.execute(db=db)

    data = query.get_data()
    assert data is not None
    assert data.ip_node_uuid == address_10.id
    assert data.current_parent_uuid == new_prefix.id
    assert data.current_children_uuids == ()
    assert data.calculated_parent_uuid == new_prefix.id
    assert data.calculated_children_uuids == ()
