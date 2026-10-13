from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import RelationshipCardinality
from infrahub.graphql.cost.models import FieldDescription
from infrahub.graphql.cost.recorder import QueryCostRecorder, activate_recorder
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase

RACK_HIERARCHY_QUERY = """
query {
    LocationRack(name__value: "paris-r1") {
        edges {
            node {
                ancestors { edges { node { name { value } } } }
                parent { node { name { value } } }
            }
        }
    }
}
"""

CHILD_PREFIXES_QUERY = """
query($prefix: ID!) {
    BuiltinIPPrefix(parent__ids: [$prefix]) {
        edges { node { prefix { value } } }
    }
}
"""


async def run_with_recorder(
    db: InfrahubDatabase, branch: Branch, query: str, variables: dict[str, Any]
) -> tuple[dict[str, Any], QueryCostRecorder]:
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    recorder = QueryCostRecorder()
    with activate_recorder(recorder=recorder):
        result = await graphql(
            schema=gql_params.schema, source=query, context_value=gql_params.context, variable_values=variables
        )
    assert result.errors is None
    assert result.data is not None
    return result.data, recorder


def calls_and_nodes(recorder: QueryCostRecorder) -> dict[str, tuple[FieldDescription | None, int, int]]:
    return {path: (actual.field, actual.resolver_calls, actual.nodes) for path, actual in recorder.fields.items()}


async def test_hierarchy_fields_are_recorded_with_the_hierarchy_kind(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data: dict[str, Node]
) -> None:
    data, recorder = await run_with_recorder(db=db, branch=default_branch, query=RACK_HIERARCHY_QUERY, variables={})

    rack = data["LocationRack"]["edges"][0]["node"]
    assert [edge["node"]["name"]["value"] for edge in rack["ancestors"]["edges"]] == ["europe", "paris"]
    assert rack["parent"]["node"]["name"]["value"] == "paris"
    assert calls_and_nodes(recorder=recorder) == {
        "LocationRack": (
            FieldDescription(
                kind="LocationRack", relationship_identifier=None, cardinality=RelationshipCardinality.MANY
            ),
            1,
            1,
        ),
        "LocationRack/ancestors": (
            FieldDescription(
                kind="LocationGeneric",
                relationship_identifier="parent__child",
                cardinality=RelationshipCardinality.MANY,
            ),
            1,
            2,
        ),
        "LocationRack/parent": (
            FieldDescription(
                kind="LocationSite", relationship_identifier="parent__child", cardinality=RelationshipCardinality.ONE
            ),
            1,
            1,
        ),
    }
    assert all(actual.database_rows > 0 for actual in recorder.fields.values())


async def test_ip_prefix_list_is_recorded_as_a_top_level_field(
    db: InfrahubDatabase, default_branch: Branch, ip_dataset_01: dict[str, Node]
) -> None:
    data, recorder = await run_with_recorder(
        db=db, branch=default_branch, query=CHILD_PREFIXES_QUERY, variables={"prefix": ip_dataset_01["net140"].id}
    )

    assert sorted(edge["node"]["prefix"]["value"] for edge in data["BuiltinIPPrefix"]["edges"]) == [
        "10.10.1.0/24",
        "10.10.2.0/24",
        "10.10.3.0/27",
    ]
    assert calls_and_nodes(recorder=recorder) == {
        "BuiltinIPPrefix": (
            FieldDescription(
                kind="BuiltinIPPrefix", relationship_identifier=None, cardinality=RelationshipCardinality.MANY
            ),
            1,
            3,
        ),
    }
    assert recorder.fields["BuiltinIPPrefix"].database_rows > 0
