from typing import Any

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.ip_address_pool import CoreIPAddressPool
from infrahub.core.node.resource_manager.ip_prefix_pool import CoreIPPrefixPool
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql

PREFIX_POOL_GET_RESOURCE_WITH_DATA = """
mutation PrefixPoolGetResourceWithData($pool_id: String!, $desc: String!) {
    InfrahubIPPrefixPoolGetResource(data: {
        id: $pool_id
        data: { description: $desc }
    }) {
        ok
        node {
            id
            kind
        }
    }
}
"""

ADDRESS_POOL_GET_RESOURCE_WITH_DATA = """
mutation AddressPoolGetResourceWithData($pool_id: String!, $desc: String!) {
    InfrahubIPAddressPoolGetResource(data: {
        id: $pool_id
        data: { description: $desc }
    }) {
        ok
        node {
            id
            kind
        }
    }
}
"""


async def test_ip_prefix_pool_get_resource_data_variable(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_extended_schema: SchemaBranch,
    init_nodes_registry: None,
    ip_dataset_prefix_v4: dict[str, Any],
) -> None:
    ns1 = ip_dataset_prefix_v4["ns1"]
    net140 = ip_dataset_prefix_v4["net140"]

    prefix_pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPPREFIXPOOL, branch=default_branch)
    pool = await CoreIPPrefixPool.init(schema=prefix_pool_schema, db=db, branch=default_branch)
    await pool.new(
        db=db,
        name="pool1",
        default_prefix_length=24,
        default_prefix_type="IpamIPPrefix",
        resources=[net140],
        ip_namespace=ns1,
    )
    await pool.save(db=db)

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=PREFIX_POOL_GET_RESOURCE_WITH_DATA,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"pool_id": pool.id, "desc": "test-prefix-desc"},
    )

    assert not result.errors
    assert result.data
    assert result.data["InfrahubIPPrefixPoolGetResource"]["ok"]
    assert result.data["InfrahubIPPrefixPoolGetResource"]["node"]["kind"] == "IpamIPPrefix"

    node_id = result.data["InfrahubIPPrefixPoolGetResource"]["node"]["id"]
    allocated = await NodeManager.get_one(db=db, branch=default_branch, id=node_id)
    assert allocated is not None
    assert allocated.description.value == "test-prefix-desc"  # type: ignore[attr-defined]


async def test_ip_address_pool_get_resource_data_variable(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_extended_schema: SchemaBranch,
    init_nodes_registry: None,
    ip_dataset_prefix_v4: dict[str, Any],
) -> None:
    ns1 = ip_dataset_prefix_v4["ns1"]
    net145 = ip_dataset_prefix_v4["net145"]

    address_pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPADDRESSPOOL, branch=default_branch)
    pool = await CoreIPAddressPool.init(schema=address_pool_schema, db=db, branch=default_branch)
    await pool.new(
        db=db,
        name="pool1",
        default_address_type="IpamIPAddress",
        resources=[net145],
        ip_namespace=ns1,
    )
    await pool.save(db=db)

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=ADDRESS_POOL_GET_RESOURCE_WITH_DATA,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"pool_id": pool.id, "desc": "test-address-desc"},
    )

    assert not result.errors
    assert result.data
    assert result.data["InfrahubIPAddressPoolGetResource"]["ok"]
    assert result.data["InfrahubIPAddressPoolGetResource"]["node"]["kind"] == "IpamIPAddress"

    node_id = result.data["InfrahubIPAddressPoolGetResource"]["node"]["id"]
    allocated = await NodeManager.get_one(db=db, branch=default_branch, id=node_id)
    assert allocated is not None
    assert allocated.description.value == "test-address-desc"  # type: ignore[attr-defined]
