from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.ipam.constants import PrefixMemberType
from infrahub.core.ipam.utilization import PrefixUtilizationGetter
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.ipam import BuiltinIPPrefix
from infrahub.core.query.ipam import IPPrefixUtilization
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


async def test_utilization_query_pagination_is_stable(
    db: InfrahubDatabase, default_branch: Branch, ip_dataset_01: dict[str, Node]
) -> None:
    """offset/limit pages must be ordered by IP and never skip or duplicate children."""
    net140 = ip_dataset_01["net140"]
    ns1 = ip_dataset_01["ns1"]
    address_schema = registry.schema.get_node_schema(name="IpamIPAddress", branch=default_branch)

    # Map each direct child of net140 to its node id, keyed by IP address.
    id_by_ip: dict[str, str] = {
        "10.10.0.0": ip_dataset_01["address10"].id,
        "10.10.1.0": ip_dataset_01["net142"].id,
        "10.10.2.0": ip_dataset_01["net144"].id,
        "10.10.3.0": ip_dataset_01["net145"].id,
    }

    # Add more addresses in an order unrelated to their IP, so the database's natural
    # scan order diverges from the IP-sorted order the query must return.
    for addr in ["10.10.0.250", "10.10.0.5"]:
        node = await Node.init(db=db, schema=address_schema)
        await node.new(db=db, address=addr, ip_prefix=net140, ip_namespace=ns1)
        await node.save(db=db)
        id_by_ip[addr] = node.id

    # Expected pagination order, written out explicitly in ascending IP order.
    expected_order = [
        id_by_ip["10.10.0.0"],
        id_by_ip["10.10.0.5"],
        id_by_ip["10.10.0.250"],
        id_by_ip["10.10.1.0"],
        id_by_ip["10.10.2.0"],
        id_by_ip["10.10.3.0"],
    ]

    async def fetch(offset: int | None = None, limit: int | None = None) -> list[str]:
        query = await IPPrefixUtilization.init(
            db=db,
            branch=default_branch,
            ip_prefixes=[net140],
            allocated_kinds=[InfrahubKind.IPPREFIX, InfrahubKind.IPADDRESS],
            offset=offset,
            limit=limit,
        )
        await query.execute(db=db)
        return [item.child_uuid for item in query.get_data()]

    # Full result set comes back deterministically ordered by IP.
    assert await fetch() == expected_order

    # Paging through with limit/offset covers every child exactly once, same order.
    page_size = 2
    paged: list[str] = []
    for offset in range(0, len(expected_order), page_size):
        paged.extend(await fetch(offset=offset, limit=page_size))
    assert paged == expected_order

    # limit alone returns the deterministic prefix of the ordering.
    assert await fetch(limit=1) == expected_order[:1]
    assert await fetch(limit=3) == expected_order[:3]

    # offset alone skips the deterministic prefix.
    assert await fetch(offset=1) == expected_order[1:]


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
