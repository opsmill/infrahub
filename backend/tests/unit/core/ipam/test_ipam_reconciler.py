import ipaddress

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_ipam_namespace, get_default_ipnamespace
from infrahub.core.ipam.reconciler import IpamReconciler
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase


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
