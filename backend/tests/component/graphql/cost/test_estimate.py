from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub import config
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot
from infrahub.core.timestamp import Timestamp
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.cost.models import EstimateMode, EstimateSource
from infrahub.graphql.cost.request_estimate import build_query_cost_estimator
from infrahub.graphql.cost.tasks import refresh_query_cost_statistics
from infrahub.graphql.execution import cached_parse
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.workers.dependencies import build_cache
from tests.component.graphql.cost.helpers import ADMIN_HEADERS, QUERY_COST_HEADERS, StatisticsUnreachableCache
from tests.helpers.dependency_override import override_dependency

if TYPE_CHECKING:
    from collections.abc import Generator

    from fast_depends import Provider
    from fastapi.testclient import TestClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from tests.adapters.cache import MemoryCache

# Electric and gaz cars are as many overall, while the first person owns one electric car and eight gaz cars.
CARS_BY_OWNER = {
    "Ann": ("TestElectricCar",) + ("TestGazCar",) * 8,
    "Ben": ("TestElectricCar",) * 6,
    "Cid": ("TestElectricCar",) * 2 + ("TestGazCar",),
    "Dee": (),
}

CARS_OF_PERSON_QUERY = """
query($name: String!) {
    TestPerson(name__value: $name) {
        edges {
            node {
                name { value }
                cars { edges { node { name { value } owner { node { name { value } } } } } }
            }
        }
    }
}
"""

OWNERS_BY_CAR_KIND_QUERY = """
query($name: String!) {
    TestPerson(name__value: $name) {
        edges {
            node {
                cars {
                    edges {
                        node {
                            name { value }
                            ... on TestElectricCar { electric_owner: owner { node { name { value } } } }
                            ... on TestGazCar { gaz_owner: owner { node { name { value } } } }
                        }
                    }
                }
            }
        }
    }
}
"""

PERSONS_CARS_OWNERS_CARS_QUERY = """
query {
    TestPerson {
        edges {
            node {
                name { value }
                cars {
                    edges {
                        node {
                            name { value }
                            owner { node { name { value } cars { edges { node { name { value } } } } } }
                        }
                    }
                }
            }
        }
    }
}
"""

CARS_OF_PERSON_OWNERS_CARS_QUERY = """
query($name: String!) {
    TestPerson(name__value: $name) {
        edges {
            node {
                name { value }
                cars {
                    edges {
                        node {
                            name { value }
                            owner { node { name { value } cars { edges { node { name { value } } } } } }
                        }
                    }
                }
            }
        }
    }
}
"""

CARS_OWNERS_CARS_QUERY = """
query {
    TestCar {
        edges {
            node {
                name { value }
                owner { node { name { value } cars { edges { node { name { value } } } } } }
            }
        }
    }
}
"""

CAR_NAMES_OF_PERSON_QUERY = """
query($name: String!) {
    TestPerson(name__value: $name) {
        edges { node { cars { edges { node { name { value } } } } } }
    }
}
"""

CAR_NAMES_AND_COUNT_OF_PERSON_QUERY = """
query($name: String!) {
    TestPerson(name__value: $name) {
        edges { node { cars { count edges { node { name { value } } } } } }
    }
}
"""

CAR_NAMES_LABELS_AND_COUNT_OF_PERSON_QUERY = """
query($name: String!) {
    TestPerson(name__value: $name) {
        edges { node { cars { count edges { node { name { value } display_label } } } } }
    }
}
"""

FAVORITE_CARS_OF_PERSON_QUERY = """
query($name: String!) {
    TestPerson(name__value: $name) {
        edges {
            node {
                cars { edges { node { name { value } } } }
                favorite_cars { edges { node { name { value } } } }
            }
        }
    }
}
"""

PERSONS_QUERY = "query { TestPerson { edges { node { name { value } } } } }"

CARS_TWICE_OF_PERSON_QUERY = """
query($name: String!) {
    TestPerson(name__value: $name) {
        edges {
            node {
                cars { edges { node { name { value } } } }
                first_car: cars(limit: 1) { edges { node { name { value } } } }
            }
        }
    }
}
"""

CAR_WINDOW_OWNERS_QUERY = """
query {
    TestCar(offset: 1, limit: 9, order: {by: [{field: "name__value", direction: DESC}]}) {
        edges {
            node {
                name { value }
                ... on TestElectricCar { electric_owner: owner { node { name { value } } } }
                ... on TestGazCar { gaz_owner: owner { node { name { value } } } }
            }
        }
    }
}
"""

PERSONS_CARS_OWNERS_QUERY = """
query {
    TestPerson {
        edges {
            node {
                name { value }
                cars { edges { node { name { value } owner { node { name { value } } } } } }
            }
        }
    }
}
"""

FIRST_PERSON_BY_NAME_QUERY = """
query {
    TestPerson(limit: 1, order: {by: [{field: "name__value", direction: %(direction)s}]}) {
        edges { node { name { value } cars { edges { node { name { value } } } } } }
    }
}
"""

CAR_WINDOW_OF_PERSON_QUERY = """
query($name: String!) {
    TestPerson(name__value: $name) {
        edges {
            node {
                cars(%(window)s) { edges { node { name { value } owner { node { name { value } } } } } }
            }
        }
    }
}
"""

CAR_WINDOW_OF_PERSONS_QUERY = """
query {
    TestPerson {
        edges {
            node {
                cars(%(window)s) { edges { node { name { value } owner { node { name { value } } } } } }
            }
        }
    }
}
"""

FILTERED_CAR_OF_PERSON_QUERY = """
query {
    TestPerson(name__value: "Ann") {
        edges {
            node {
                cars(name__value: "ann-3") { edges { node { name { value } owner { node { name { value } } } } } }
            }
        }
    }
}
"""

REPORT_FIELD_ESTIMATES_QUERY = """
query ($q: String!, $variables: GenericScalar) {
    InfrahubGraphQLQueryReport(query: $q, variables: $variables) {
        cost_estimate { mode fields { path source worst_case_is_bound expected { nodes } } }
    }
}
"""

REPORT_COST_ESTIMATE_QUERY = """
query ($q: String!, $variables: GenericScalar) {
    InfrahubGraphQLQueryReport(query: $q, variables: $variables) { cost_estimate { mode } }
}
"""


@pytest.fixture
async def car_fleet(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_generics: SchemaRoot, create_test_admin: Node
) -> dict[str, Node]:
    """Persons owning the cars of `CARS_BY_OWNER`, by name."""
    persons: dict[str, Node] = {}
    for owner_name, car_kinds in CARS_BY_OWNER.items():
        person = await Node.init(db=db, schema="TestPerson")
        await person.new(db=db, name=owner_name)
        await person.save(db=db)
        persons[owner_name] = person
        for index, kind in enumerate(car_kinds):
            await _create_car(db=db, kind=kind, name=f"{owner_name.lower()}-{index}", owner=person)
    return persons


@pytest.fixture
async def car_fleet_with_statistics(car_fleet: dict[str, Node], memory_cache: MemoryCache) -> dict[str, Node]:
    """The persons of `car_fleet`, with the statistics refreshed on their data."""
    await refresh_query_cost_statistics()
    return car_fleet


@pytest.fixture
def statistics_unreachable_cache(dependency_provider: Provider) -> Generator[StatisticsUnreachableCache, None, None]:
    cache = StatisticsUnreachableCache()
    with override_dependency(build_cache, lambda: cache, dependency_provider=dependency_provider):
        yield cache


async def _create_car(db: InfrahubDatabase, kind: str, name: str, owner: Node, branch: Branch | None = None) -> Node:
    car = await Node.init(db=db, schema=kind, branch=branch)
    if kind == "TestElectricCar":
        await car.new(db=db, name=name, nbr_seats=4, nbr_engine=1, owner=owner)
    else:
        await car.new(db=db, name=name, nbr_seats=5, mpg=40, owner=owner)
    await car.save(db=db)
    return car


def post_query(
    client: TestClient,
    query: str,
    headers: dict[str, str],
    variables: dict[str, Any] | None = None,
    branch: str | None = None,
    at: Timestamp | None = None,
) -> dict[str, Any]:
    response = client.post(
        f"/graphql/{branch}" if branch else "/graphql",
        json={"query": query, "variables": variables or {}},
        headers=headers,
        params={"at": at.to_string()} if at is not None else None,
    )
    assert response.status_code == 200
    return response.json()


def post_with_details(
    client: TestClient,
    query: str,
    variables: dict[str, Any] | None = None,
    branch: str | None = None,
    at: Timestamp | None = None,
) -> dict[str, Any]:
    payload = post_query(
        client=client, query=query, headers=QUERY_COST_HEADERS, variables=variables, branch=branch, at=at
    )
    assert "errors" not in payload
    return payload["extensions"]["query_cost"]


def fields_by_path(query_cost: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {field["path"]: field for field in query_cost["fields"]}


def figures_above_worst_case(query_cost: dict[str, Any]) -> list[tuple[str, str, int, int]]:
    """List each figure of each field whose actual value exceeds its worst case, as (path, figure, actual, worst)."""
    return [
        (field["path"], figure, field["actual"][figure], field["estimate"]["worst_case"][figure])
        for field in query_cost["fields"]
        for figure in ("nodes", "resolver_calls", "database_rows")
        if field["actual"][figure] > field["estimate"]["worst_case"][figure]
    ]


async def test_every_field_has_an_estimate_next_to_its_actual_counts(
    counting_client: TestClient, car_fleet_with_statistics: dict[str, Node]
) -> None:
    with counting_client:
        query_cost = post_with_details(client=counting_client, query=CARS_OF_PERSON_QUERY, variables={"name": "Ann"})

    assert query_cost["estimate_mode"] == "counted_first_step"
    assert query_cost["statistics"] is not None
    assert (query_cost["statistics"]["branch"], query_cost["statistics"]["version"]) == ("main", 1)
    fields = fields_by_path(query_cost=query_cost)
    assert list(fields) == ["TestPerson", "TestPerson/cars", "TestPerson/cars/owner"]
    assert {path: field["estimate"]["source"] for path, field in fields.items()} == {
        "TestPerson": "counted",
        "TestPerson/cars": "counted",
        "TestPerson/cars/owner": "statistics",
    }
    for field in fields.values():
        assert field["estimate"]["reason"] is None
        assert field["estimate"]["worst_case_is_bound"] is True
    assert {
        path: (field["estimate"]["expected"]["nodes"], field["estimate"]["expected"]["resolver_calls"])
        for path, field in fields.items()
    } == {"TestPerson": (1, 1), "TestPerson/cars": (9, 1), "TestPerson/cars/owner": (9, 9)}
    assert {path: (field["actual"]["nodes"], field["actual"]["resolver_calls"]) for path, field in fields.items()} == {
        "TestPerson": (1, 1),
        "TestPerson/cars": (9, 1),
        "TestPerson/cars/owner": (9, 9),
    }
    assert all(field["actual"]["database_rows"] > 0 for field in fields.values())


async def test_first_step_is_counted_for_each_concrete_peer_kind(
    counting_client: TestClient, car_fleet_with_statistics: dict[str, Node]
) -> None:
    with counting_client:
        query_cost = post_with_details(
            client=counting_client, query=OWNERS_BY_CAR_KIND_QUERY, variables={"name": "Ann"}
        )

    fields = fields_by_path(query_cost=query_cost)
    assert fields["TestPerson/cars"]["estimate"]["source"] == "counted"
    # Over every person, half the cars are electric; the counted first step finds 1 electric and 8 gaz cars.
    assert {
        path: (
            fields[path]["estimate"]["expected"]["resolver_calls"],
            fields[path]["estimate"]["expected"]["nodes"],
            fields[path]["actual"]["resolver_calls"],
            fields[path]["actual"]["nodes"],
        )
        for path in ("TestPerson/cars/electric_owner", "TestPerson/cars/gaz_owner")
    } == {"TestPerson/cars/electric_owner": (1, 1, 1, 1), "TestPerson/cars/gaz_owner": (8, 8, 8, 8)}


async def test_first_step_counts_the_nodes_in_the_window_of_the_top_level_field(
    counting_client: TestClient, car_fleet_with_statistics: dict[str, Node]
) -> None:
    with counting_client:
        payload = post_query(client=counting_client, query=CAR_WINDOW_OWNERS_QUERY, headers=QUERY_COST_HEADERS)

    # In the order they were created, the window would hold 8 gaz cars of Ann and 1 electric car of Ben.
    cars = [edge["node"]["name"]["value"] for edge in payload["data"]["TestCar"]["edges"]]
    assert cars == ["cid-1", "cid-0", "ben-5", "ben-4", "ben-3", "ben-2", "ben-1", "ben-0", "ann-8"]
    fields = fields_by_path(query_cost=payload["extensions"]["query_cost"])
    assert {
        path: (
            field["estimate"]["source"],
            field["estimate"]["expected"]["nodes"],
            field["estimate"]["expected"]["resolver_calls"],
            field["actual"]["nodes"],
            field["actual"]["resolver_calls"],
        )
        for path, field in fields.items()
    } == {
        "TestCar": ("counted", 9, 1, 9, 1),
        "TestCar/electric_owner": ("counted", 8, 8, 8, 8),
        "TestCar/gaz_owner": ("counted", 1, 1, 1, 1),
    }


async def test_first_step_counts_the_node_that_a_limit_of_one_returns_whatever_the_order(
    counting_client: TestClient, car_fleet_with_statistics: dict[str, Node]
) -> None:
    names_by_id = {person.id: name for name, person in car_fleet_with_statistics.items()}
    smallest_id_name = names_by_id[min(names_by_id)]
    # The order puts another person first, so only a count that drops the order finds the person returned.
    direction = "DESC" if smallest_id_name == min(names_by_id.values()) else "ASC"

    with counting_client:
        payload = post_query(
            client=counting_client,
            query=FIRST_PERSON_BY_NAME_QUERY % {"direction": direction},
            headers=QUERY_COST_HEADERS,
        )

    assert [edge["node"]["name"]["value"] for edge in payload["data"]["TestPerson"]["edges"]] == [smallest_id_name]
    cars = fields_by_path(query_cost=payload["extensions"]["query_cost"])["TestPerson/cars"]
    assert cars["estimate"]["source"] == "counted"
    assert (cars["estimate"]["expected"]["nodes"], cars["estimate"]["worst_case"]["nodes"]) == (
        len(CARS_BY_OWNER[smallest_id_name]),
        len(CARS_BY_OWNER[smallest_id_name]),
    )
    assert cars["actual"]["nodes"] == len(CARS_BY_OWNER[smallest_id_name])


@dataclass
class PeerWindowTestCase:
    name: str
    query: str
    variables: dict[str, Any]
    returned_cars: int
    """Cars the field returns, over every person the top-level field returns."""


PEER_WINDOW_TEST_CASES: list[PeerWindowTestCase] = [
    PeerWindowTestCase(
        name="offset_on_a_person_with_one_car_kind",
        query=CAR_WINDOW_OF_PERSON_QUERY % {"window": "offset: 3"},
        variables={"name": "Ben"},
        returned_cars=3,
    ),
    PeerWindowTestCase(
        name="offset_and_limit_on_a_person_with_two_car_kinds",
        query=CAR_WINDOW_OF_PERSON_QUERY % {"window": "offset: 7, limit: 5"},
        variables={"name": "Ann"},
        returned_cars=2,
    ),
    PeerWindowTestCase(
        name="offset_and_limit_on_every_person",
        query=CAR_WINDOW_OF_PERSONS_QUERY % {"window": "offset: 2, limit: 5"},
        variables={},
        returned_cars=5 + 4 + 1,
    ),
    PeerWindowTestCase(
        name="limit_on_every_person",
        query=CAR_WINDOW_OF_PERSONS_QUERY % {"window": "limit: 4"},
        variables={},
        returned_cars=4 + 4 + 3,
    ),
]


@pytest.mark.parametrize(
    "test_case", [pytest.param(test_case, id=test_case.name) for test_case in PEER_WINDOW_TEST_CASES]
)
async def test_first_step_counts_the_peers_in_the_window_of_each_parent(
    counting_client: TestClient, car_fleet_with_statistics: dict[str, Node], test_case: PeerWindowTestCase
) -> None:
    with counting_client:
        query_cost = post_with_details(client=counting_client, query=test_case.query, variables=test_case.variables)

    cars = fields_by_path(query_cost=query_cost)["TestPerson/cars"]
    assert cars["estimate"]["source"] == "counted"
    assert (cars["estimate"]["expected"]["nodes"], cars["estimate"]["worst_case"]["nodes"]) == (
        test_case.returned_cars,
        test_case.returned_cars,
    )
    assert cars["actual"]["nodes"] == test_case.returned_cars
    assert figures_above_worst_case(query_cost=query_cost) == []


async def test_first_step_counts_the_branch_of_the_request(
    db: InfrahubDatabase, counting_client: TestClient, car_fleet_with_statistics: dict[str, Node]
) -> None:
    branch = await create_branch(branch_name="cost-estimate", db=db)
    owner_on_branch = await NodeManager.get_one(db=db, branch=branch, id=car_fleet_with_statistics["Ann"].id)
    assert owner_on_branch is not None
    for index in range(3):
        await _create_car(
            db=db, kind="TestElectricCar", name=f"ann-branch-{index}", owner=owner_on_branch, branch=branch
        )

    with counting_client:
        on_main = post_with_details(client=counting_client, query=CARS_OF_PERSON_QUERY, variables={"name": "Ann"})
        on_branch = post_with_details(
            client=counting_client, query=CARS_OF_PERSON_QUERY, variables={"name": "Ann"}, branch=branch.name
        )

    main_cars = fields_by_path(query_cost=on_main)["TestPerson/cars"]
    branch_cars = fields_by_path(query_cost=on_branch)["TestPerson/cars"]
    assert (main_cars["estimate"]["expected"]["nodes"], main_cars["actual"]["nodes"]) == (9, 9)
    assert (branch_cars["estimate"]["source"], branch_cars["estimate"]["expected"]["nodes"]) == ("counted", 12)
    assert branch_cars["actual"]["nodes"] == 12
    assert [field["estimate"]["worst_case_is_bound"] for field in on_branch["fields"]] == [False, False, False]


async def test_first_step_counts_the_time_of_the_request(
    db: InfrahubDatabase, counting_client: TestClient, car_fleet_with_statistics: dict[str, Node]
) -> None:
    before_new_cars = Timestamp()
    for index in range(2):
        await _create_car(db=db, kind="TestGazCar", name=f"ben-later-{index}", owner=car_fleet_with_statistics["Ben"])
    variables = {"name": "Ben"}

    with counting_client:
        now = post_with_details(client=counting_client, query=CARS_OF_PERSON_QUERY, variables=variables)
        earlier = post_with_details(
            client=counting_client, query=CARS_OF_PERSON_QUERY, variables=variables, at=before_new_cars
        )
        report = post_query(
            client=counting_client,
            query=REPORT_FIELD_ESTIMATES_QUERY,
            headers=ADMIN_HEADERS,
            variables={"q": CARS_OF_PERSON_QUERY, "variables": variables},
            at=before_new_cars,
        )

    now_cars = fields_by_path(query_cost=now)["TestPerson/cars"]
    earlier_cars = fields_by_path(query_cost=earlier)["TestPerson/cars"]
    assert (now_cars["estimate"]["expected"]["nodes"], now_cars["actual"]["nodes"]) == (8, 8)
    assert (
        earlier_cars["estimate"]["source"],
        earlier_cars["estimate"]["expected"]["nodes"],
        earlier_cars["actual"]["nodes"],
    ) == ("counted", 6, 6)
    assert [field["estimate"]["worst_case_is_bound"] for field in earlier["fields"]] == [False, False, False]
    assert "errors" not in report
    assert [
        (field["path"], field["source"], field["expected"]["nodes"], field["worst_case_is_bound"])
        for field in report["data"]["InfrahubGraphQLQueryReport"]["cost_estimate"]["fields"]
    ] == [
        ("TestPerson", "COUNTED", 1, False),
        ("TestPerson/cars", "COUNTED", 6, False),
        ("TestPerson/cars/owner", "STATISTICS", 6, False),
    ]


async def test_first_step_counts_the_peers_that_match_the_filters_of_the_relationship_field(
    counting_client: TestClient, car_fleet_with_statistics: dict[str, Node]
) -> None:
    with counting_client:
        query_cost = post_with_details(client=counting_client, query=FILTERED_CAR_OF_PERSON_QUERY)

    cars = fields_by_path(query_cost=query_cost)["TestPerson/cars"]
    assert (
        cars["estimate"]["source"],
        cars["estimate"]["expected"]["nodes"],
        cars["estimate"]["worst_case"]["nodes"],
        cars["actual"]["nodes"],
    ) == ("counted", 1, 1, 1)


@dataclass
class WorstCaseTestCase:
    name: str
    query: str
    variables: dict[str, Any]


WORST_CASE_TEST_CASES: list[WorstCaseTestCase] = [
    WorstCaseTestCase(name="every_person", query=PERSONS_CARS_OWNERS_CARS_QUERY, variables={}),
    WorstCaseTestCase(name="one_person", query=CARS_OF_PERSON_OWNERS_CARS_QUERY, variables={"name": "Ann"}),
    WorstCaseTestCase(name="every_car", query=CARS_OWNERS_CARS_QUERY, variables={}),
]


@pytest.mark.parametrize(
    "test_case", [pytest.param(test_case, id=test_case.name) for test_case in WORST_CASE_TEST_CASES]
)
async def test_actual_counts_stay_within_the_worst_case_on_unchanged_data(
    counting_client: TestClient, car_fleet_with_statistics: dict[str, Node], test_case: WorstCaseTestCase
) -> None:
    with counting_client:
        query_cost = post_with_details(client=counting_client, query=test_case.query, variables=test_case.variables)

    paths = [field["path"] for field in query_cost["fields"]]
    assert paths[-1].endswith("owner/cars")
    assert all(field["estimate"]["worst_case_is_bound"] for field in query_cost["fields"])
    assert figures_above_worst_case(query_cost=query_cost) == []


async def test_relationship_added_after_the_refresh_has_no_statistics_and_its_actual_counts(
    db: InfrahubDatabase,
    default_branch: Branch,
    counting_client: TestClient,
    car_fleet_with_statistics: dict[str, Node],
    car_person_schema_generics_unregistered: dict[str, Any],
) -> None:
    extended_schema = copy.deepcopy(car_person_schema_generics_unregistered)
    person_schema = next(node for node in extended_schema["nodes"] if node["name"] == "Person")
    person_schema["relationships"].append(
        {
            "name": "favorite_cars",
            "peer": "TestCar",
            "identifier": "person_favorite__car",
            "cardinality": "many",
            "optional": True,
        }
    )
    registry.schema.register_schema(schema=SchemaRoot(**extended_schema), branch=default_branch.name)
    ann = await NodeManager.get_one(db=db, id=car_fleet_with_statistics["Ann"].id)
    assert ann is not None
    ben_cars = await NodeManager.query(
        db=db, schema="TestCar", filters={"owner__ids": [car_fleet_with_statistics["Ben"].id]}
    )
    await ann.get_relationship(name="favorite_cars").update(db=db, data=[ben_cars[0], ben_cars[1]])
    await ann.save(db=db)

    with counting_client:
        query_cost = post_with_details(
            client=counting_client, query=FAVORITE_CARS_OF_PERSON_QUERY, variables={"name": "Ann"}
        )

    fields = fields_by_path(query_cost=query_cost)
    assert fields["TestPerson/cars"]["estimate"]["reason"] is None
    assert fields["TestPerson/favorite_cars"]["estimate"] == {
        "expected": None,
        "worst_case": None,
        "worst_case_is_bound": False,
        "source": None,
        "reason": "no statistics",
    }
    assert (
        fields["TestPerson/favorite_cars"]["actual"]["nodes"],
        fields["TestPerson/favorite_cars"]["actual"]["resolver_calls"],
    ) == (2, 1)
    assert fields["TestPerson/favorite_cars"]["actual"]["database_rows"] > 0


async def test_estimate_covers_count_but_not_display_label_reads(
    counting_client: TestClient, car_fleet_with_statistics: dict[str, Node]
) -> None:
    variables = {"name": "Ann"}
    with counting_client:
        names = post_with_details(client=counting_client, query=CAR_NAMES_OF_PERSON_QUERY, variables=variables)
        with_count = post_with_details(
            client=counting_client, query=CAR_NAMES_AND_COUNT_OF_PERSON_QUERY, variables=variables
        )
        with_labels = post_with_details(
            client=counting_client, query=CAR_NAMES_LABELS_AND_COUNT_OF_PERSON_QUERY, variables=variables
        )

    cars = fields_by_path(query_cost=names)["TestPerson/cars"]
    cars_with_count = fields_by_path(query_cost=with_count)["TestPerson/cars"]
    cars_with_labels = fields_by_path(query_cost=with_labels)["TestPerson/cars"]
    # The count reads one row for each resolver call of the field.
    assert cars_with_count["estimate"]["expected"]["resolver_calls"] == 1
    assert cars_with_count["estimate"]["expected"]["database_rows"] == cars["estimate"]["expected"]["database_rows"] + 1
    assert cars_with_count["estimate"]["worst_case"]["database_rows"] == (
        cars["estimate"]["worst_case"]["database_rows"] + 1
    )
    assert cars_with_count["actual"]["database_rows"] > cars["actual"]["database_rows"]
    assert cars_with_labels["estimate"] == cars_with_count["estimate"]
    assert cars_with_labels["actual"]["database_rows"] > cars_with_count["actual"]["database_rows"]


async def test_statistics_only_estimate_counts_the_nodes_created_after_the_refresh(
    db: InfrahubDatabase, default_branch: Branch, car_fleet_with_statistics: dict[str, Node], memory_cache: MemoryCache
) -> None:
    for name in ("Eve", "Fox"):
        person = await Node.init(db=db, schema="TestPerson")
        await person.new(db=db, name=name)
        await person.save(db=db)
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    graphql_params = await prepare_graphql_params(db=db, branch=default_branch)
    analyzer = InfrahubGraphQLQueryAnalyzer(
        query=PERSONS_QUERY,
        schema=graphql_params.schema,
        schema_branch=schema_branch,
        branch=default_branch,
        document=cached_parse(PERSONS_QUERY),
    )
    estimator = build_query_cost_estimator(
        db=db,
        branch=default_branch,
        at=Timestamp(),
        reads_current_time=True,
        schema_branch=schema_branch,
        cache=memory_cache,
    )

    query_estimate = await estimator.estimate(analyzer=analyzer, schema=graphql_params.schema, variable_values=None)

    assert query_estimate.mode == EstimateMode.STATISTICS_ONLY
    persons = query_estimate.estimates["TestPerson"]
    assert persons.source == EstimateSource.STATISTICS
    assert persons.expected is not None
    assert persons.worst_case is not None
    # 4 persons existed at the refresh, and 2 more since.
    assert (persons.expected.nodes, persons.worst_case.nodes) == (6, 6)


async def test_first_step_runs_one_query_for_the_top_level_and_one_for_each_relationship_under_it(
    counting_client: TestClient, car_fleet_with_statistics: dict[str, Node]
) -> None:
    with counting_client:
        query_cost = post_with_details(
            client=counting_client, query=CARS_TWICE_OF_PERSON_QUERY, variables={"name": "Ann"}
        )

    assert [field["path"] for field in query_cost["fields"]] == [
        "TestPerson",
        "TestPerson/cars",
        "TestPerson/first_car",
    ]
    assert query_cost["estimate_queries"]["queries"] == 1 + 2
    assert query_cost["estimate_queries"]["database_rows"] > 0
    first_car = fields_by_path(query_cost=query_cost)["TestPerson/first_car"]
    assert (first_car["estimate"]["expected"]["nodes"], first_car["actual"]["nodes"]) == (1, 1)


async def test_field_with_the_most_resolver_calls_is_the_one_under_the_peers_that_multiply_them(
    counting_client: TestClient, car_fleet_with_statistics: dict[str, Node]
) -> None:
    with counting_client:
        query_cost = post_with_details(client=counting_client, query=CARS_OF_PERSON_QUERY, variables={"name": "Ann"})

    fields = query_cost["fields"]
    assert max(fields, key=lambda field: field["actual"]["resolver_calls"])["path"] == "TestPerson/cars/owner"
    assert (
        max(fields, key=lambda field: field["estimate"]["expected"]["resolver_calls"])["path"]
        == "TestPerson/cars/owner"
    )


async def test_fields_under_a_top_level_above_the_size_limit_are_estimated_from_the_statistics(
    counting_client: TestClient, car_fleet_with_statistics: dict[str, Node], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config.SETTINGS.database, "query_size_limit", 2)

    with counting_client:
        query_cost = post_with_details(client=counting_client, query=PERSONS_CARS_OWNERS_QUERY)

    fields = fields_by_path(query_cost=query_cost)
    assert {path: field["estimate"]["source"] for path, field in fields.items()} == {
        "TestPerson": "counted",
        "TestPerson/cars": "statistics",
        "TestPerson/cars/owner": "statistics",
    }
    assert fields["TestPerson"]["estimate"]["expected"]["nodes"] == 4
    assert query_cost["estimate_queries"]["queries"] == 1


async def test_variables_of_the_wrong_type_return_the_same_response_without_an_estimate(
    counting_client: TestClient, car_fleet_with_statistics: dict[str, Node]
) -> None:
    with counting_client:
        without_header = post_query(
            client=counting_client, query=CARS_OF_PERSON_QUERY, headers=ADMIN_HEADERS, variables={"name": 5}
        )
        with_header = post_query(
            client=counting_client, query=CARS_OF_PERSON_QUERY, headers=QUERY_COST_HEADERS, variables={"name": 5}
        )

    assert without_header == {
        "data": None,
        "errors": [
            {
                "message": "Variable '$name' got invalid value 5; String cannot represent a non string value: 5",
                "locations": [{"line": 2, "column": 7}],
                "extensions": {"code": "UNDEFINED_ERROR", "data": {}, "http_status": 500},
            }
        ],
    }
    assert list(with_header) == ["data", "errors", "extensions"]
    assert {key: with_header[key] for key in ("data", "errors")} == without_header
    query_cost = with_header["extensions"]["query_cost"]
    assert {key: value for key, value in query_cost.items() if key != "unattributed"} == {
        "estimate_mode": "statistics_only",
        "statistics": None,
        "fields": [],
        "estimate_queries": {"queries": 0, "database_rows": 0},
    }


async def test_unreachable_statistics_return_the_same_data_without_an_estimate(
    statistics_unreachable_cache: StatisticsUnreachableCache, counting_client: TestClient, car_fleet: dict[str, Node]
) -> None:
    with counting_client:
        without_header = post_query(client=counting_client, query=PERSONS_CARS_OWNERS_QUERY, headers=ADMIN_HEADERS)
        with_header = post_query(client=counting_client, query=PERSONS_CARS_OWNERS_QUERY, headers=QUERY_COST_HEADERS)

    assert list(without_header) == ["data"]
    assert list(with_header) == ["data", "extensions"]
    assert with_header["data"] == without_header["data"]
    query_cost = with_header["extensions"]["query_cost"]
    assert (query_cost["estimate_mode"], query_cost["statistics"]) == ("statistics_only", None)
    # The first step is counted before the statistics are read.
    assert query_cost["estimate_queries"]["queries"] == 2
    assert [
        (field["path"], field["estimate"]["reason"], field["actual"]["nodes"]) for field in query_cost["fields"]
    ] == [
        ("TestPerson", "no statistics", 4),
        ("TestPerson/cars", "no statistics", 18),
        ("TestPerson/cars/owner", "no statistics", 18),
    ]


async def test_report_sent_with_the_header_reports_the_counting_queries_of_its_estimate(
    counting_client: TestClient, car_fleet_with_statistics: dict[str, Node]
) -> None:
    with counting_client:
        payload = post_query(
            client=counting_client,
            query=REPORT_COST_ESTIMATE_QUERY,
            headers=QUERY_COST_HEADERS,
            variables={"q": CARS_OF_PERSON_QUERY, "variables": {"name": "Ann"}},
        )

    assert payload["data"] == {"InfrahubGraphQLQueryReport": {"cost_estimate": {"mode": "COUNTED_FIRST_STEP"}}}
    query_cost = payload["extensions"]["query_cost"]
    # The report maps to no kind, and its estimate counts the person, then the cars of that person.
    assert query_cost["fields"] == []
    assert query_cost["estimate_queries"]["queries"] == 2
