from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.diff.branch_differ import BranchDiffer
from infrahub.core.diff.ipam_diff_parser import IpamDiffParser
from infrahub.core.initialization import create_branch
from infrahub.core.ipam.model import IpamNodeDetails
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase


async def test_ipam_diff_parser_update(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01):
    branch_2 = await create_branch(db=db, branch_name="branch_2")

    # updated prefix value
    net146_branch = await NodeManager.get_one(db=db, branch=branch_2, id=ip_dataset_01["net146"].id)
    net146_branch.prefix.value = "10.0.0.0/9"
    await net146_branch.save(db=db)
    # updated address
    address11_branch = await NodeManager.get_one(db=db, branch=branch_2, id=ip_dataset_01["address11"].id)
    address11_branch.address.value = "10.10.1.2/32"
    await address11_branch.save(db=db)

    differ = await BranchDiffer.init(db=db, branch=branch_2)
    parser = IpamDiffParser(
        db=db, differ=differ, source_branch_name=branch_2.name, target_branch_name=default_branch.name
    )
    ipam_diffs = await parser.get_changed_ipam_node_details()

    assert len(ipam_diffs) == 2
    assert (
        IpamNodeDetails(
            node_uuid=net146_branch.id, is_address=False, namespace_id=ip_dataset_01["ns1"].id, ip_value="10.0.0.0/9"
        )
        in ipam_diffs
    )
    assert (
        IpamNodeDetails(
            node_uuid=address11_branch.id,
            is_address=True,
            namespace_id=ip_dataset_01["ns1"].id,
            ip_value="10.10.1.2/32",
        )
        in ipam_diffs
    )


async def test_ipam_diff_parser_create(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01):
    branch_2 = await create_branch(db=db, branch_name="branch_2")
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)
    address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)

    # new prefix
    new_prefix_branch = await Node.init(db=db, branch=branch_2, schema=prefix_schema)
    await new_prefix_branch.new(db=db, prefix="10.10.3.0/26", ip_namespace=ip_dataset_01["ns2"].id)
    await new_prefix_branch.save(db=db)
    # new address
    new_address_branch = await Node.init(db=db, branch=branch_2, schema=address_schema)
    await new_address_branch.new(db=db, address="10.10.4.5/32", ip_namespace=ip_dataset_01["ns2"].id)
    await new_address_branch.save(db=db)

    differ = await BranchDiffer.init(db=db, branch=branch_2)
    parser = IpamDiffParser(
        db=db, differ=differ, source_branch_name=branch_2.name, target_branch_name=default_branch.name
    )
    ipam_diffs = await parser.get_changed_ipam_node_details()

    assert len(ipam_diffs) == 2
    assert (
        IpamNodeDetails(
            node_uuid=new_prefix_branch.id,
            is_address=False,
            namespace_id=ip_dataset_01["ns2"].id,
            ip_value="10.10.3.0/26",
        )
        in ipam_diffs
    )
    assert (
        IpamNodeDetails(
            node_uuid=new_address_branch.id,
            is_address=True,
            namespace_id=ip_dataset_01["ns2"].id,
            ip_value="10.10.4.5/32",
        )
        in ipam_diffs
    )


async def test_ipam_diff_parser_delete(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01):
    branch_2 = await create_branch(db=db, branch_name="branch_2")

    # delete prefix
    net146_branch = await NodeManager.get_one(db=db, branch=branch_2, id=ip_dataset_01["net146"].id)
    await net146_branch.delete(db=db)
    # delete address
    address11_branch = await NodeManager.get_one(db=db, branch=branch_2, id=ip_dataset_01["address11"].id)
    await address11_branch.delete(db=db)

    differ = await BranchDiffer.init(db=db, branch=branch_2)
    parser = IpamDiffParser(
        db=db, differ=differ, source_branch_name=branch_2.name, target_branch_name=default_branch.name
    )
    ipam_diffs = await parser.get_changed_ipam_node_details()

    assert len(ipam_diffs) == 2
    assert (
        IpamNodeDetails(
            node_uuid=net146_branch.id,
            is_address=False,
            namespace_id=ip_dataset_01["ns1"].id,
            ip_value=net146_branch.prefix.value,
        )
        in ipam_diffs
    )
    assert (
        IpamNodeDetails(
            node_uuid=address11_branch.id,
            is_address=True,
            namespace_id=ip_dataset_01["ns1"].id,
            ip_value=address11_branch.address.value,
        )
        in ipam_diffs
    )
