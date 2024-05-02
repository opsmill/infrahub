from graphql import graphql

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.node.resource_manager import CorePrefixPool
from infrahub.core.schema_manager import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql import prepare_graphql_params


async def test_assign_from_pool(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_ipnamespace: Node,
    register_ipam_extended_schema: SchemaBranch,
    init_nodes_registry,
    ip_dataset_prefix_v4,
):
    ns1 = ip_dataset_prefix_v4["ns1"]
    net140 = ip_dataset_prefix_v4["net140"]

    prefix_pool_schema = registry.schema.get_node_schema(name="CorePrefixPool", branch=default_branch)

    pool = await CorePrefixPool.init(schema=prefix_pool_schema, db=db, branch=default_branch)
    await pool.new(
        db=db,
        name="pool1",
        default_prefix_size=24,
        default_prefix_type="IpamIPPrefix",
        resources=[net140],
        ip_namespace=ns1,
    )
    await pool.save(db=db)

    query = (
        """
    mutation {
        TestMandatoryPrefixCreate(data: {
            name: { value: "site1" }
            prefix: {
                from_pool: {
                    id: "%s"
                }
            }
        }) {
            ok
            object {
                name {
                    value
                }
                prefix {
                    node {
                        prefix {
                            value
                        }
                    }
                    properties {
                        source {
                            id
                        }
                    }
                }
            }
        }
    }
    """
        % pool.id
    )

    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert not result.errors
    assert result.data["TestMandatoryPrefixCreate"]["ok"]
    assert result.data["TestMandatoryPrefixCreate"]["object"] == {
        "name": {"value": "site1"},
        "prefix": {
            "node": {"prefix": {"value": "10.10.0.0/24"}},
            "properties": {
                "source": {"id": pool.id},
            },
        },
    }
