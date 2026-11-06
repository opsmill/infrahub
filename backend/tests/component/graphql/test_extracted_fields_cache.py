from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.node import Node
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.graphql.types import RELATIONS_PROPERTY_MAP
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

PERSONS_WITH_CARS_AND_OWNERS = """
query {
    TestPerson {
        edges {
            node {
                name { value }
                cars {
                    edges {
                        properties { is_protected }
                        node {
                            name { value }
                            owner {
                                properties { is_protected }
                                node { name { value } }
                            }
                        }
                    }
                }
            }
        }
    }
}
"""


def _all_dicts(fields: dict[str, Any]) -> list[dict[str, Any]]:
    found = [fields]
    for value in fields.values():
        if isinstance(value, dict):
            found.extend(_all_dicts(value))
    return found


async def test_resolvers_share_the_fields_of_a_query_field_without_changing_them(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    for person_name in ("John", "Jane"):
        person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
        await person.new(db=db, name=person_name, height=180)
        await person.save(db=db)
        for car_name in ("volt", "bolt"):
            car = await Node.init(db=db, schema="TestCar", branch=default_branch)
            await car.new(db=db, name=f"{car_name}-{person_name}", nbr_seats=4, owner=person.id)
            await car.save(db=db)

    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=PERSONS_WITH_CARS_AND_OWNERS,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    owners_by_car = {
        car["node"]["name"]["value"]: car["node"]["owner"]["node"]["name"]["value"]
        for person in result.data["TestPerson"]["edges"]
        for car in person["node"]["cars"]["edges"]
    }
    assert owners_by_car == {"volt-John": "John", "bolt-John": "John", "volt-Jane": "Jane", "bolt-Jane": "Jane"}

    # The relationship resolvers add the relationship properties to the node fields they load: on a copy only.
    cached = [fields for _, _, fields in gql_params.context.extracted_fields.values()]
    assert cached
    added_names = {name for key, name in RELATIONS_PROPERTY_MAP.items() if key != "__typename"} | {"human_friendly_id"}
    for fields in cached:
        for nested in _all_dicts(fields):
            assert not added_names & set(nested), nested
