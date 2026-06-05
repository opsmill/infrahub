from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.ipam.constants import PrefixMemberType
from infrahub.core.ipam.utilization import PrefixUtilizationGetter
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.ipam import BuiltinIPPrefix
from infrahub.database import InfrahubDatabase


async def test_use_percentage(db: InfrahubDatabase, default_branch: Branch, ip_dataset_01: dict[str, Node]) -> None:
    net240 = ip_dataset_01["net240"]
    net240.member_type.value = PrefixMemberType.ADDRESS.value
    utilization = PrefixUtilizationGetter(db=db, ip_prefixes=[net240], branch=default_branch)
    percentage = await utilization.get_use_percentage()

    assert percentage == 0.0

    net240.member_type.value = PrefixMemberType.PREFIX.value
    utilization = PrefixUtilizationGetter(db=db, ip_prefixes=[net240], branch=default_branch)
    percentage = await utilization.get_use_percentage()

    assert percentage == 0.2197265625


async def test_use_percentage_no_prefixes(db: InfrahubDatabase, default_branch: Branch) -> None:
    utilization = PrefixUtilizationGetter(db=db, ip_prefixes=[], branch=default_branch)
    percentage = await utilization.get_use_percentage()

    assert percentage == 0.0


async def test_graphql_utilization_inherited_on_new_branch(
    db: InfrahubDatabase, default_branch: Branch, ip_dataset_01: dict[str, Node]
) -> None:
    registry.node[InfrahubKind.IPPREFIX] = BuiltinIPPrefix
    net143_id = ip_dataset_01["net143"].id

    main_prefix = await NodeManager.get_one(db=db, branch=default_branch, id=net143_id)
    assert isinstance(main_prefix, BuiltinIPPrefix)
    main_response = await main_prefix.to_graphql(db=db, fields={"utilization": None})
    assert main_response["utilization"] == {"value": 3}

    new_branch = await create_branch(db=db, branch_name="branch-utilization")

    branch_prefix = await NodeManager.get_one(db=db, branch=new_branch, id=net143_id)
    assert isinstance(branch_prefix, BuiltinIPPrefix)
    branch_response = await branch_prefix.to_graphql(db=db, fields={"utilization": None})

    assert branch_response["utilization"] == {"value": 3}


async def test_graphql_utilization_branch_addition(
    db: InfrahubDatabase, default_branch: Branch, ip_dataset_01: dict[str, Node]
) -> None:
    registry.node[InfrahubKind.IPPREFIX] = BuiltinIPPrefix
    net143_id = ip_dataset_01["net143"].id
    ns1 = ip_dataset_01["ns1"]

    new_branch = await create_branch(db=db, branch_name="branch-utilization-add")
    address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=new_branch)

    net143_on_branch = await NodeManager.get_one(db=db, branch=new_branch, id=net143_id)
    new_address = await Node.init(db=db, branch=new_branch, schema=address_schema)
    await new_address.new(db=db, address="10.10.1.2", ip_prefix=net143_on_branch, ip_namespace=ns1)
    await new_address.save(db=db)

    branch_prefix = await NodeManager.get_one(db=db, branch=new_branch, id=net143_id)
    assert isinstance(branch_prefix, BuiltinIPPrefix)
    branch_response = await branch_prefix.to_graphql(db=db, fields={"utilization": None})
    # net143 has 30 usable addresses, 1 from main + 1 added on branch = 2/30 -> int(6.66) = 6
    assert branch_response["utilization"] == {"value": 6}

    main_prefix = await NodeManager.get_one(db=db, branch=default_branch, id=net143_id)
    assert isinstance(main_prefix, BuiltinIPPrefix)
    main_response = await main_prefix.to_graphql(db=db, fields={"utilization": None})
    assert main_response["utilization"] == {"value": 3}


async def test_graphql_utilization_branch_deletion(
    db: InfrahubDatabase, default_branch: Branch, ip_dataset_01: dict[str, Node]
) -> None:
    registry.node[InfrahubKind.IPPREFIX] = BuiltinIPPrefix
    net143_id = ip_dataset_01["net143"].id
    address11_id = ip_dataset_01["address11"].id

    new_branch = await create_branch(db=db, branch_name="branch-utilization-delete")

    address_on_branch = await NodeManager.get_one(db=db, branch=new_branch, id=address11_id)
    assert address_on_branch is not None
    await address_on_branch.delete(db=db)

    branch_prefix = await NodeManager.get_one(db=db, branch=new_branch, id=net143_id)
    assert isinstance(branch_prefix, BuiltinIPPrefix)
    branch_response = await branch_prefix.to_graphql(db=db, fields={"utilization": None})
    assert branch_response["utilization"] == {"value": 0}

    main_prefix = await NodeManager.get_one(db=db, branch=default_branch, id=net143_id)
    assert isinstance(main_prefix, BuiltinIPPrefix)
    main_response = await main_prefix.to_graphql(db=db, fields={"utilization": None})
    assert main_response["utilization"] == {"value": 3}


async def test_graphql_utilization_main_addition_after_branch_creation(
    db: InfrahubDatabase, default_branch: Branch, ip_dataset_01: dict[str, Node]
) -> None:
    registry.node[InfrahubKind.IPPREFIX] = BuiltinIPPrefix
    net143_id = ip_dataset_01["net143"].id
    ns1 = ip_dataset_01["ns1"]

    new_branch = await create_branch(db=db, branch_name="branch-utilization-main-add")

    address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)
    net143_on_main = await NodeManager.get_one(db=db, branch=default_branch, id=net143_id)
    new_address = await Node.init(db=db, schema=address_schema)
    await new_address.new(db=db, address="10.10.1.2", ip_prefix=net143_on_main, ip_namespace=ns1)
    await new_address.save(db=db)

    main_prefix = await NodeManager.get_one(db=db, branch=default_branch, id=net143_id)
    assert isinstance(main_prefix, BuiltinIPPrefix)
    main_response = await main_prefix.to_graphql(db=db, fields={"utilization": None})
    assert main_response["utilization"] == {"value": 6}

    branch_prefix = await NodeManager.get_one(db=db, branch=new_branch, id=net143_id)
    assert isinstance(branch_prefix, BuiltinIPPrefix)
    branch_response = await branch_prefix.to_graphql(db=db, fields={"utilization": None})
    assert branch_response["utilization"] == {"value": 3}
