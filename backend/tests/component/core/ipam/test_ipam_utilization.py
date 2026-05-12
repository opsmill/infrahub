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
    utilization = PrefixUtilizationGetter(db=db, ip_prefixes=[net240])
    percentage = await utilization.get_use_percentage()

    assert percentage == 0.0

    net240.member_type.value = PrefixMemberType.PREFIX.value
    utilization = PrefixUtilizationGetter(db=db, ip_prefixes=[net240])
    percentage = await utilization.get_use_percentage()

    assert percentage == 0.2197265625


async def test_use_percentage_no_prefixes(db: InfrahubDatabase, default_branch: Branch) -> None:
    utilization = PrefixUtilizationGetter(db=db, ip_prefixes=[])
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

    assert branch_response["utilization"] == main_response["utilization"]
