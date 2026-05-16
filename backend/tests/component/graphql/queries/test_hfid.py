from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql


async def test_iphost_hfid_roundtrip_via_graphql(
    db: InfrahubDatabase, default_branch: Branch, data_schema: None
) -> None:
    """A bare IPHost value provided at creation time is exposed in canonical form via GraphQL.

    The returned hfid can be fed back as input to retrieve the same node.
    """
    schema_root = SchemaRoot(
        nodes=[
            {
                "name": "HostAddress",
                "namespace": "Test",
                "human_friendly_id": ["address__value"],
                "display_label": "address__value",
                "attributes": [{"name": "address", "kind": "IPHost", "unique": True}],
            }
        ]
    )
    registry.schema.register_schema(schema=schema_root, branch=default_branch.name)

    node = await Node.init(db=db, schema="TestHostAddress", branch=default_branch)
    await node.new(db=db, address="192.0.2.10")
    await node.save(db=db)

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    fetch_query = """
    query {
        TestHostAddress {
            edges {
                node {
                    id
                    hfid
                    address { value }
                }
            }
        }
    }
    """
    fetch_result = await graphql(
        schema=gql_params.schema,
        source=fetch_query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert fetch_result.errors is None
    assert fetch_result.data
    edges = fetch_result.data["TestHostAddress"]["edges"]
    assert len(edges) == 1
    returned_node = edges[0]["node"]
    assert returned_node["address"]["value"] == "192.0.2.10/32"
    assert returned_node["hfid"] == ["192.0.2.10/32"]

    lookup_query = """
    query LookupByHfid($hfid: [String]) {
        TestHostAddress(hfid: $hfid) {
            edges {
                node {
                    id
                    hfid
                }
            }
        }
    }
    """
    lookup_result = await graphql(
        schema=gql_params.schema,
        source=lookup_query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"hfid": returned_node["hfid"]},
    )

    assert lookup_result.errors is None
    assert lookup_result.data
    looked_up = lookup_result.data["TestHostAddress"]["edges"]
    assert len(looked_up) == 1
    assert looked_up[0]["node"]["id"] == node.id
    assert looked_up[0]["node"]["hfid"] == ["192.0.2.10/32"]
