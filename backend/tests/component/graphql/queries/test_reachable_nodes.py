from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.node import Node
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

REACHABLE_NODES_QUERY = """
query Reach($data: ReachableNodesInput!) {
  InfrahubReachableNodes(data: $data) {
    count
    source { id kind }
    dependencies {
      depth
      node { id kind }
      path {
        depth
        hops { node { id kind } }
      }
    }
  }
}
"""


@pytest.fixture
async def car_with_owner_and_driver(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> tuple[Node, Node, Node]:
    owner = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await owner.new(db=db, name="Owner", height=170)
    await owner.save(db=db)

    driver = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await driver.new(db=db, name="Driver", height=180)
    await driver.save(db=db)

    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="Roadster", is_electric=True, nbr_seats=2, color="#ff0000", owner=owner, driver=driver)
    await car.save(db=db)

    return car, owner, driver


async def _run_resolver(
    *,
    db: InfrahubDatabase,
    branch: Branch,
    session: AccountSession,
    variables: dict,
) -> tuple[dict | None, list | None]:
    gql_params = await prepare_graphql_params(db=db, branch=branch, account_session=session)
    result = await graphql(
        schema=gql_params.schema,
        source=REACHABLE_NODES_QUERY,
        context_value=gql_params.context,
        variable_values=variables,
    )
    return result.data, list(result.errors) if result.errors else None


async def test_resolver_short_circuits_when_no_route_to_target_kind(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    session_admin: AccountSession,
    car_with_owner_and_driver: tuple[Node, Node, Node],
) -> None:
    # Terminal kind is in a namespace that the default user-filter set excludes,
    # so no schema route
    car, _owner, _driver = car_with_owner_and_driver
    default_branch.update_schema_hash()

    variables = {
        "data": {
            "source_id": car.id,
            "target_kinds": ["BuiltinTag"],
            "max_depth": 5,
            "max_results": 50,
        }
    }

    data, errors = await _run_resolver(db=db, branch=default_branch, session=session_admin, variables=variables)

    assert errors is None
    assert data is not None
    result = data["InfrahubReachableNodes"]
    assert result["count"] == 0
    assert result["dependencies"] == []
    assert result["source"]["id"] == car.id


async def test_resolver_returns_reachable_targets(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    session_admin: AccountSession,
    car_with_owner_and_driver: tuple[Node, Node, Node],
) -> None:
    car, owner, driver = car_with_owner_and_driver
    default_branch.update_schema_hash()

    variables = {
        "data": {
            "source_id": car.id,
            "target_kinds": ["TestPerson"],
            # max_depth=1 so results are easier to assert
            "max_depth": 1,
            "max_results": 50,
        }
    }

    data, errors = await _run_resolver(db=db, branch=default_branch, session=session_admin, variables=variables)

    assert errors is None
    assert data is not None
    result = data["InfrahubReachableNodes"]
    assert result["count"] == 2
    by_id = {dep["node"]["id"]: dep for dep in result["dependencies"]}
    assert set(by_id) == {owner.id, driver.id}
    for dep in by_id.values():
        assert dep["depth"] == 1
        assert dep["node"]["kind"] == "TestPerson"
        assert [hop["node"]["id"] for hop in dep["path"]["hops"]] == [car.id, dep["node"]["id"]]


async def test_resolver_supports_multiple_target_kinds(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    session_admin: AccountSession,
    two_cars_one_owner: tuple[Node, Node, Node],
) -> None:
    # Person at depth 1 (owner-edge), car_b at depth 2 (car_a → person → car_b).
    # Trail semantics prevent looping back to car_a, so the source kind doesn't
    # appear in the result.
    car_a, car_b, person = two_cars_one_owner
    default_branch.update_schema_hash()

    variables = {
        "data": {
            "source_id": car_a.id,
            "target_kinds": ["TestPerson", "TestCar"],
            "max_depth": 2,
            "max_results": 100,
        }
    }

    data, errors = await _run_resolver(db=db, branch=default_branch, session=session_admin, variables=variables)

    assert errors is None
    assert data is not None
    result = data["InfrahubReachableNodes"]
    returned_kind_by_id = {dep["node"]["id"]: dep["node"]["kind"] for dep in result["dependencies"]}
    assert returned_kind_by_id == {
        person.id: "TestPerson",
        car_b.id: "TestCar",
    }


async def test_resolver_raises_for_missing_source(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    session_admin: AccountSession,
    car_with_owner_and_driver: tuple[Node, Node, Node],
) -> None:
    default_branch.update_schema_hash()

    missing_id = "00000000-0000-0000-0000-000000000001"
    variables = {"data": {"source_id": missing_id, "target_kinds": ["TestPerson"]}}

    _data, errors = await _run_resolver(db=db, branch=default_branch, session=session_admin, variables=variables)
    assert errors is not None
    assert errors[0].message == f"Source node not found: {missing_id}"


async def test_resolver_raises_for_unknown_target_kind(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    session_admin: AccountSession,
    car_with_owner_and_driver: tuple[Node, Node, Node],
) -> None:
    car, _owner, _driver = car_with_owner_and_driver
    default_branch.update_schema_hash()

    bogus_kind = "DoesNotExistKind"
    variables = {"data": {"source_id": car.id, "target_kinds": [bogus_kind]}}

    _data, errors = await _run_resolver(db=db, branch=default_branch, session=session_admin, variables=variables)
    assert errors is not None
    assert errors[0].message == f"Unknown target kind: {bogus_kind}"


async def test_resolver_respects_session_permissions(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    authentication_base: Node,
    session_first_account: AccountSession,
    car_with_owner_and_driver: tuple[Node, Node, Node],
) -> None:
    # Account has no view permissions assigned
    car, _owner, _driver = car_with_owner_and_driver
    default_branch.update_schema_hash()

    variables = {
        "data": {
            "source_id": car.id,
            "target_kinds": ["TestPerson"],
            "max_depth": 1,
            "max_results": 50,
        }
    }

    data, errors = await _run_resolver(db=db, branch=default_branch, session=session_first_account, variables=variables)

    assert errors is None
    assert data is not None
    result = data["InfrahubReachableNodes"]
    assert result["count"] == 0
    assert result["dependencies"] == []
