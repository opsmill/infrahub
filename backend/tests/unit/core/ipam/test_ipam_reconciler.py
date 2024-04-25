import ipaddress

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_ipam_namespace, get_default_ipnamespace
from infrahub.core.ipam.reconciler import IpamReconciler
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import NodeNotFoundError


async def test_invalid_ip_node_raises_error(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema):
    await create_ipam_namespace(db=db)
    default_ipnamespace = await get_default_ipnamespace(db=db)

    reconciler = IpamReconciler(db=db, branch=default_branch)
    with pytest.raises(NodeNotFoundError):
        await reconciler.reconcile(ip_value=ipaddress.ip_interface("192.168.1.1"), namespace=default_ipnamespace)


async def test_first_prefix(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema, register_ipam_schema
):
    await create_ipam_namespace(db=db)
    default_ipnamespace = await get_default_ipnamespace(db=db)
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)
    net161 = await Node.init(db=db, schema=prefix_schema)
    await net161.new(db=db, prefix="2001:db8::/48", ip_namespace=default_ipnamespace)
    await net161.save(db=db)

    reconciler = IpamReconciler(db=db, branch=default_branch)
    await reconciler.reconcile(ip_value=ipaddress.ip_network(net161.prefix.value), namespace=default_ipnamespace)

    all_prefixes = await NodeManager.query(db=db, schema="BuiltinIPPrefix")
    assert len(all_prefixes) == 1
    assert all_prefixes[0].id == net161.id
    assert all_prefixes[0].is_top_level.value is True


async def test_ipprefix_reconciler_no_change(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01):
    await create_ipam_namespace(db=db)
    default_ipnamespace = await get_default_ipnamespace(db=db)
    registry.default_ipnamespace = default_ipnamespace.id
    prefix_140 = ip_dataset_01["net140"]
    namespace = ip_dataset_01["ns1"]
    ip_network = ipaddress.ip_network(prefix_140.prefix.value)

    reconciler = IpamReconciler(db=db, branch=default_branch)
    await reconciler.reconcile(ip_value=ip_network, namespace=namespace)

    updated_prefix_140 = await NodeManager.get_one(db=db, branch=default_branch, id=prefix_140.id)
    assert updated_prefix_140.is_top_level.value is False
    prefix_140_parent_rels = await updated_prefix_140.parent.get_relationships(db=db)
    assert len(prefix_140_parent_rels) == 1
    assert prefix_140_parent_rels[0].peer_id == ip_dataset_01["net146"].id
    updated_prefix_146 = await NodeManager.get_one(db=db, branch=default_branch, id=ip_dataset_01["net146"].id)
    prefix_146_children_rels = await updated_prefix_146.children.get_relationships(db=db)
    assert len(prefix_146_children_rels) == 1
    assert prefix_146_children_rels[0].peer_id == updated_prefix_140.id


async def test_ipprefix_reconciler_new_prefix_update(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01):
    await create_ipam_namespace(db=db)
    default_ipnamespace = await get_default_ipnamespace(db=db)
    registry.default_ipnamespace = default_ipnamespace.id
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)
    namespace = ip_dataset_01["ns1"]
    new_prefix = await Node.init(db=db, schema=prefix_schema)
    await new_prefix.new(db=db, prefix="10.10.0.0/18", ip_namespace=namespace, parent=ip_dataset_01["net146"])
    await new_prefix.save(db=db)
    ip_network = ipaddress.ip_network(new_prefix.prefix.value)

    reconciler = IpamReconciler(db=db, branch=default_branch)
    await reconciler.reconcile(ip_value=ip_network, namespace=namespace)

    # check new prefix parent
    updated_prefix = await NodeManager.get_one(db=db, branch=default_branch, id=new_prefix.id)
    assert updated_prefix.is_top_level.value is False
    updated_prefix_parent_rels = await updated_prefix.parent.get_relationships(db=db)
    assert len(updated_prefix_parent_rels) == 1
    assert updated_prefix_parent_rels[0].peer_id == ip_dataset_01["net140"].id
    # check new prefix children
    expected_child_prefix_ids = [ip_dataset_01["net142"].id, ip_dataset_01["net144"].id, ip_dataset_01["net145"].id]
    expected_child_address_ids = [ip_dataset_01["address10"].id]
    updated_prefix_child_rels = await updated_prefix.children.get_relationships(db=db)
    assert len(updated_prefix_child_rels) == 3
    assert {rel.peer_id for rel in updated_prefix_child_rels} == set(expected_child_prefix_ids)
    updated_address_child_rels = await updated_prefix.ip_addresses.get_relationships(db=db)
    assert len(updated_address_child_rels) == 1
    assert {rel.peer_id for rel in updated_address_child_rels} == set(expected_child_address_ids)
    # check new parent children
    updated_prefix_140 = await NodeManager.get_one(db=db, branch=default_branch, id=ip_dataset_01["net140"].id)
    prefix_140_children_rels = await updated_prefix_140.children.get_relationships(db=db)
    assert len(prefix_140_children_rels) == 1
    assert prefix_140_children_rels[0].peer_id == updated_prefix.id
    prefix_140_address_rels = await updated_prefix_140.ip_addresses.get_relationships(db=db)
    assert len(prefix_140_address_rels) == 0
    # check new child prefixes parents
    updated_children = await NodeManager.get_many(db=db, branch=default_branch, ids=expected_child_prefix_ids)
    for child in updated_children.values():
        child_parent_rels = await child.parent.get_relationships(db=db)
        assert len(child_parent_rels) == 1
        assert child_parent_rels[0].peer_id == updated_prefix.id
        assert child.is_top_level.value is False
    # check new child address parents
    updated_children = await NodeManager.get_many(db=db, branch=default_branch, ids=expected_child_address_ids)
    for child in updated_children.values():
        child_parent_rels = await child.ip_prefix.get_relationships(db=db)
        assert len(child_parent_rels) == 1
        assert child_parent_rels[0].peer_id == updated_prefix.id


async def test_ipprefix_reconciler_new_address_update(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01):
    await create_ipam_namespace(db=db)
    default_ipnamespace = await get_default_ipnamespace(db=db)
    registry.default_ipnamespace = default_ipnamespace.id
    address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)
    namespace = ip_dataset_01["ns1"]
    new_address = await Node.init(db=db, schema=address_schema)
    await new_address.new(db=db, address="10.10.3.1", ip_namespace=namespace)
    await new_address.save(db=db)
    ip_interface = ipaddress.ip_interface(new_address.address.value)

    reconciler = IpamReconciler(db=db, branch=default_branch)
    await reconciler.reconcile(ip_value=ip_interface, namespace=namespace)

    # check address parent
    updated_address = await NodeManager.get_one(db=db, branch=default_branch, id=new_address.id)
    prefix_rels = await updated_address.ip_prefix.get_relationships(db=db)
    assert len(prefix_rels) == 1
    assert prefix_rels[0].peer_id == ip_dataset_01["net145"].id
    # check prefix ip addresses
    updated_prefix = await NodeManager.get_one(db=db, branch=default_branch, id=ip_dataset_01["net145"].id)
    ip_address_rels = await updated_prefix.ip_addresses.get_relationships(db=db)
    assert len(ip_address_rels) == 1
    assert ip_address_rels[0].peer_id == new_address.id


async def test_ip_prefix_reconciler_delete_prefix(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01):
    await create_ipam_namespace(db=db)
    default_ipnamespace = await get_default_ipnamespace(db=db)
    registry.default_ipnamespace = default_ipnamespace.id
    namespace = ip_dataset_01["ns1"]
    net_140_prefix = ip_dataset_01["net140"]
    ip_network = ipaddress.ip_network(net_140_prefix.prefix.value)

    reconciler = IpamReconciler(db=db, branch=default_branch)
    await reconciler.reconcile(ip_value=ip_network, node_uuid=net_140_prefix.id, namespace=namespace, is_delete=True)

    # check prefix is deleted
    deleted = await NodeManager.get_one(db=db, branch=default_branch, id=net_140_prefix.id)
    assert deleted is None
    # check children of former parent
    expected_child_prefix_ids = [ip_dataset_01["net142"].id, ip_dataset_01["net144"].id, ip_dataset_01["net145"].id]
    expected_child_address_ids = [ip_dataset_01["address10"].id]
    updated_parent = await NodeManager.get_one(db=db, branch=default_branch, id=ip_dataset_01["net146"].id)
    updated_prefix_child_rels = await updated_parent.children.get_relationships(db=db)
    assert len(updated_prefix_child_rels) == 3
    assert {rel.peer_id for rel in updated_prefix_child_rels} == set(expected_child_prefix_ids)
    updated_address_child_rels = await updated_parent.ip_addresses.get_relationships(db=db)
    assert len(updated_address_child_rels) == 1
    assert {rel.peer_id for rel in updated_address_child_rels} == set(expected_child_address_ids)
    # check parent of former child prefixes
    updated_children = await NodeManager.get_many(db=db, branch=default_branch, ids=expected_child_prefix_ids)
    for child in updated_children.values():
        child_parent_rels = await child.parent.get_relationships(db=db)
        assert len(child_parent_rels) == 1
        assert child_parent_rels[0].peer_id == updated_parent.id
        assert child.is_top_level.value is False
    # check parent of former child addresses
    updated_children = await NodeManager.get_many(db=db, branch=default_branch, ids=expected_child_address_ids)
    for child in updated_children.values():
        child_parent_rels = await child.ip_prefix.get_relationships(db=db)
        assert len(child_parent_rels) == 1
        assert child_parent_rels[0].peer_id == updated_parent.id


async def test_ip_prefix_reconciler_delete_address(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01):
    await create_ipam_namespace(db=db)
    default_ipnamespace = await get_default_ipnamespace(db=db)
    registry.default_ipnamespace = default_ipnamespace.id
    namespace = ip_dataset_01["ns1"]
    address10 = ip_dataset_01["address10"]
    ip_network = ipaddress.ip_interface(address10.address.value)

    reconciler = IpamReconciler(db=db, branch=default_branch)
    await reconciler.reconcile(ip_value=ip_network, node_uuid=address10.id, namespace=namespace, is_delete=True)

    # check prefix is deleted
    deleted = await NodeManager.get_one(db=db, branch=default_branch, id=address10.id)
    assert deleted is None
    # check children of former parent
    expected_child_prefix_ids = [ip_dataset_01["net142"].id, ip_dataset_01["net144"].id, ip_dataset_01["net145"].id]
    updated_parent = await NodeManager.get_one(db=db, branch=default_branch, id=ip_dataset_01["net140"].id)
    updated_prefix_child_rels = await updated_parent.children.get_relationships(db=db)
    assert len(updated_prefix_child_rels) == 3
    assert {rel.peer_id for rel in updated_prefix_child_rels} == set(expected_child_prefix_ids)
    updated_address_child_rels = await updated_parent.ip_addresses.get_relationships(db=db)
    assert len(updated_address_child_rels) == 0


async def test_ipprefix_reconciler_prefix_value_update(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01):
    await create_ipam_namespace(db=db)
    default_ipnamespace = await get_default_ipnamespace(db=db)
    registry.default_ipnamespace = default_ipnamespace.id
    namespace = ip_dataset_01["ns1"]
    net_146 = ip_dataset_01["net146"]
    net_146.prefix.value = "10.10.0.0/18"
    await net_146.save(db=db)
    ip_network = ipaddress.ip_network(net_146.prefix.value)

    reconciler = IpamReconciler(db=db, branch=default_branch)
    await reconciler.reconcile(ip_value=ip_network, namespace=namespace)

    # check new prefix parent
    new_parent = await NodeManager.get_one(db=db, branch=default_branch, id=ip_dataset_01["net140"].id)
    assert new_parent.is_top_level.value is True
    new_parent_parent_rels = await new_parent.parent.get_relationships(db=db)
    assert len(new_parent_parent_rels) == 0
    new_parent_child_rels = await new_parent.children.get_relationships(db=db)
    assert len(new_parent_child_rels) == 1
    assert new_parent_child_rels[0].peer_id == net_146.id
    # check updated prefix parent relationship
    updated_prefix = await NodeManager.get_one(db=db, branch=default_branch, id=net_146.id)
    assert updated_prefix.is_top_level.value is False
    updated_prefix_parent_rels = await updated_prefix.parent.get_relationships(db=db)
    assert len(updated_prefix_parent_rels) == 1
    assert updated_prefix_parent_rels[0].peer_id == ip_dataset_01["net140"].id
    # check updated prefix child relationships
    expected_child_prefix_ids = [ip_dataset_01["net142"].id, ip_dataset_01["net144"].id, ip_dataset_01["net145"].id]
    expected_child_address_ids = [ip_dataset_01["address10"].id]
    updated_prefix_child_rels = await updated_prefix.children.get_relationships(db=db)
    assert len(updated_prefix_child_rels) == 3
    assert {rel.peer_id for rel in updated_prefix_child_rels} == set(expected_child_prefix_ids)
    updated_address_child_rels = await updated_prefix.ip_addresses.get_relationships(db=db)
    assert len(updated_address_child_rels) == 1
    assert {rel.peer_id for rel in updated_address_child_rels} == set(expected_child_address_ids)
    # check new child prefixes parents
    updated_children = await NodeManager.get_many(db=db, branch=default_branch, ids=expected_child_prefix_ids)
    for child in updated_children.values():
        child_parent_rels = await child.parent.get_relationships(db=db)
        assert len(child_parent_rels) == 1
        assert child_parent_rels[0].peer_id == updated_prefix.id
        assert child.is_top_level.value is False
    # check new child address parents
    updated_children = await NodeManager.get_many(db=db, branch=default_branch, ids=expected_child_address_ids)
    for child in updated_children.values():
        child_parent_rels = await child.ip_prefix.get_relationships(db=db)
        assert len(child_parent_rels) == 1
        assert child_parent_rels[0].peer_id == updated_prefix.id
