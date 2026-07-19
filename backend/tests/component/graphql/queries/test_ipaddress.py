from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql


async def test_ipaddress_bare_value_and_hfid_roundtrip_via_graphql(
    db: InfrahubDatabase, default_branch: Branch, data_schema: None
) -> None:
    """An IPAddress value is exposed bare (no prefix) via GraphQL and its hfid round-trips.

    Unlike IPHost, no /32 or /128 is appended, so the hfid returned by a query can be fed
    straight back as lookup input without adding or stripping a mask.
    """
    schema_root = SchemaRoot(
        nodes=[
            {
                "name": "DnsRecord",
                "namespace": "Test",
                "human_friendly_id": ["address__value"],
                "display_label": "address__value",
                "attributes": [{"name": "address", "kind": "IPAddress", "unique": True}],
            }
        ]
    )
    registry.schema.register_schema(schema=schema_root, branch=default_branch.name)

    node_v4 = await Node.init(db=db, schema="TestDnsRecord", branch=default_branch)
    await node_v4.new(db=db, address="192.0.2.10")
    await node_v4.save(db=db)

    node_v6 = await Node.init(db=db, schema="TestDnsRecord", branch=default_branch)
    await node_v6.new(db=db, address="2001:0db8::0001")
    await node_v6.save(db=db)

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    fetch_query = """
    query {
        TestDnsRecord {
            edges {
                node {
                    id
                    hfid
                    address { value version }
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
    edges = fetch_result.data["TestDnsRecord"]["edges"]
    by_id = {edge["node"]["id"]: edge["node"] for edge in edges}
    assert len(by_id) == 2

    v4 = by_id[node_v4.id]
    assert v4["address"]["value"] == "192.0.2.10"
    assert v4["address"]["version"] == 4
    assert v4["hfid"] == ["192.0.2.10"]

    v6 = by_id[node_v6.id]
    assert v6["address"]["value"] == "2001:db8::1"
    assert v6["address"]["version"] == 6
    assert v6["hfid"] == ["2001:db8::1"]

    lookup_query = """
    query LookupByHfid($hfid: [String]) {
        TestDnsRecord(hfid: $hfid) {
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
        variable_values={"hfid": v4["hfid"]},
    )

    assert lookup_result.errors is None
    assert lookup_result.data
    looked_up = lookup_result.data["TestDnsRecord"]["edges"]
    assert len(looked_up) == 1
    assert looked_up[0]["node"]["id"] == node_v4.id
    assert looked_up[0]["node"]["hfid"] == ["192.0.2.10"]


async def test_ipaddress_create_mutation_rejects_prefix(
    db: InfrahubDatabase, default_branch: Branch, data_schema: None
) -> None:
    """Creating a node with a prefixed value on an IPAddress attribute fails validation."""
    schema_root = SchemaRoot(
        nodes=[
            {
                "name": "NtpServer",
                "namespace": "Test",
                "attributes": [{"name": "address", "kind": "IPAddress"}],
            }
        ]
    )
    registry.schema.register_schema(schema=schema_root, branch=default_branch.name)

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)

    create_query = """
    mutation {
        TestNtpServerCreate(data: {address: {value: "10.0.0.1/24"}}) {
            ok
            object { id }
        }
    }
    """
    result = await graphql(
        schema=gql_params.schema,
        source=create_query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is not None
    assert len(result.errors) == 1
    assert result.errors[0].message == "10.0.0.1/24 is not a valid IPAddress at address"
