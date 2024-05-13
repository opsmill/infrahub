import pytest
from graphql import graphql

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.schema_manager import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql import prepare_graphql_params


@pytest.fixture
async def ip_dataset_01(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_ipam_schema: SchemaBranch,
):
    prefix_schema = registry.schema.get_node_schema(name="IpamIPPrefix", branch=default_branch)

    # -----------------------
    # Namespace NS1
    # -----------------------

    ns1 = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
    await ns1.new(db=db, name="ns1")
    await ns1.save(db=db)

    net146 = await Node.init(db=db, schema=prefix_schema)
    await net146.new(db=db, prefix="10.0.0.0/8", ip_namespace=ns1)
    await net146.save(db=db)

    net140 = await Node.init(db=db, schema=prefix_schema)
    await net140.new(db=db, prefix="10.10.0.0/16", ip_namespace=ns1, parent=net146)
    await net140.save(db=db)

    net142 = await Node.init(db=db, schema=prefix_schema)
    await net142.new(db=db, prefix="10.10.1.0/24", parent=net140, ip_namespace=ns1)
    await net142.save(db=db)

    net143 = await Node.init(db=db, schema=prefix_schema)
    await net143.new(db=db, prefix="10.10.1.0/27", parent=net142, ip_namespace=ns1)
    await net143.save(db=db)

    net144 = await Node.init(db=db, schema=prefix_schema)
    await net144.new(db=db, prefix="10.10.2.0/24", parent=net140, ip_namespace=ns1)
    await net144.save(db=db)

    net145 = await Node.init(db=db, schema=prefix_schema)
    await net145.new(db=db, prefix="10.10.3.0/27", parent=net140, ip_namespace=ns1)
    await net145.save(db=db)

    data = {
        "ns1": ns1,
        # "ns2": ns2,
        # "net161": net161,
        # "net162": net162,
        "net140": net140,
        "net142": net142,
        "net143": net143,
        "net144": net144,
        "net145": net145,
        "net146": net146,
        # "address10": address10,
        # "address11": address11,
        # "net240": net240,
        # "net241": net241,
        # "net242": net242,
    }
    return data


@pytest.mark.parametrize(
    "prefix,size,response",
    [
        ("net146", 16, "10.11.0.0/16"),
        ("net146", 24, "10.11.0.0/24"),
        ("net142", 26, "10.10.1.64/26"),
        ("net142", 27, "10.10.1.32/27"),
    ],
)
async def test_ipprefix_nextavailable(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_schema: SchemaBranch,
    ip_dataset_01,
    prefix,
    size,
    response,
):
    obj = ip_dataset_01[prefix]

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)

    query = """
    query($prefix: String!, $size: Int!) {
        IPPrefixGetNextAvailable(prefix_id: $prefix, size: $size) {
            prefix
        }
    }
    """

    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        variable_values={"prefix": obj.id, "size": size},
    )

    assert not result.errors
    assert result.data["IPPrefixGetNextAvailable"]["prefix"] == response
