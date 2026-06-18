from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    from infrahub.auth.session import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase

PATH_TRAVERSAL_QUERY = """
query Traverse($data: PathTraversalInput!) {
  InfrahubPathTraversal(data: $data) {
    count
    excluded_kinds
    source { id kind }
    destination { id kind }
    paths {
      depth
      hops {
        node { id kind }
      }
    }
  }
}
"""


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
        source=PATH_TRAVERSAL_QUERY,
        context_value=gql_params.context,
        variable_values=variables,
    )
    return result.data, list(result.errors) if result.errors else None


class TestPathTraversalResolver:
    """Resolver behavior against one shared, read-only dataset.

    Every test runs queries only — none mutates the database — so the data is
    loaded once for the class via the ``_scope_class`` fixture chain.
    """

    async def test_resolver_returns_empty_when_no_schema_route(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        default_permission_backend_scope_class: None,
        session_admin_scope_class: AccountSession,
        two_cars_one_owner_scope_class: tuple[Node, Node, Node],
    ) -> None:
        # No schema route survives planning → resolver returns the empty shape
        car_a, car_b, _person = two_cars_one_owner_scope_class
        default_branch_scope_class.update_schema_hash()

        variables = {
            "data": {
                "source_id": car_a.id,
                "destination_id": car_b.id,
                "max_depth": 5,
                "max_paths": 10,
                "excluded_kinds": ["TestPerson"],
            }
        }

        data, errors = await _run_resolver(
            db=db, branch=default_branch_scope_class, session=session_admin_scope_class, variables=variables
        )

        assert errors is None
        assert data is not None
        result = data["InfrahubPathTraversal"]
        assert result["count"] == 0
        assert result["paths"] == []
        assert result["source"]["id"] == car_a.id
        assert result["destination"]["id"] == car_b.id

    async def test_resolver_returns_paths_when_route_exists(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        default_permission_backend_scope_class: None,
        session_admin_scope_class: AccountSession,
        two_cars_one_owner_scope_class: tuple[Node, Node, Node],
    ) -> None:
        car_a, _car_b, person = two_cars_one_owner_scope_class
        default_branch_scope_class.update_schema_hash()

        variables = {
            "data": {
                "source_id": car_a.id,
                "destination_id": person.id,
                # max_depth=1 so paths are easier to assert
                "max_depth": 1,
                "max_paths": 10,
            }
        }

        data, errors = await _run_resolver(
            db=db, branch=default_branch_scope_class, session=session_admin_scope_class, variables=variables
        )

        assert errors is None
        assert data is not None
        result = data["InfrahubPathTraversal"]
        assert result["count"] == 1
        only = result["paths"][0]
        assert only["depth"] == 1
        assert [hop["node"]["id"] for hop in only["hops"]] == [car_a.id, person.id]

    async def test_resolver_kind_filter_blocks_intermediate_kind(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        default_permission_backend_scope_class: None,
        session_admin_scope_class: AccountSession,
        two_cars_one_owner_scope_class: tuple[Node, Node, Node],
    ) -> None:
        # kind_filter applies to intermediates only (source/terminal are exempt).
        # The only schema route between two TestCars goes through TestPerson, so a
        # kind_filter that omits TestPerson prunes the intermediate and zeroes the plan.
        car_a, car_b, _person = two_cars_one_owner_scope_class
        default_branch_scope_class.update_schema_hash()

        variables = {
            "data": {
                "source_id": car_a.id,
                "destination_id": car_b.id,
                "max_depth": 5,
                "max_paths": 10,
                "kind_filter": ["TestCar"],
            }
        }

        data, errors = await _run_resolver(
            db=db, branch=default_branch_scope_class, session=session_admin_scope_class, variables=variables
        )

        assert errors is None
        assert data is not None
        assert data["InfrahubPathTraversal"]["count"] == 0

    async def test_resolver_rejects_max_paths_above_maximum(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        default_permission_backend_scope_class: None,
        session_admin_scope_class: AccountSession,
        two_cars_one_owner_scope_class: tuple[Node, Node, Node],
    ) -> None:
        car_a, car_b, _person = two_cars_one_owner_scope_class
        default_branch_scope_class.update_schema_hash()

        variables = {
            "data": {
                "source_id": car_a.id,
                "destination_id": car_b.id,
                "max_depth": 5,
                "max_paths": 101,
            }
        }

        _, errors = await _run_resolver(
            db=db, branch=default_branch_scope_class, session=session_admin_scope_class, variables=variables
        )

        assert errors is not None
        assert errors[0].message == "max_paths must be in [1, 100], got 101"

    async def test_resolver_rejects_max_paths_below_minimum(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        default_permission_backend_scope_class: None,
        session_admin_scope_class: AccountSession,
        two_cars_one_owner_scope_class: tuple[Node, Node, Node],
    ) -> None:
        car_a, car_b, _person = two_cars_one_owner_scope_class
        default_branch_scope_class.update_schema_hash()

        variables = {
            "data": {
                "source_id": car_a.id,
                "destination_id": car_b.id,
                "max_depth": 5,
                "max_paths": -1,
            }
        }

        _, errors = await _run_resolver(
            db=db, branch=default_branch_scope_class, session=session_admin_scope_class, variables=variables
        )

        assert errors is not None
        assert errors[0].message == "max_paths must be in [1, 100], got -1"

    async def test_resolver_kind_filter_admits_intermediate_kind(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        default_permission_backend_scope_class: None,
        session_admin_scope_class: AccountSession,
        two_cars_one_owner_scope_class: tuple[Node, Node, Node],
    ) -> None:
        car_a, car_b, person = two_cars_one_owner_scope_class
        default_branch_scope_class.update_schema_hash()

        variables = {
            "data": {
                "source_id": car_a.id,
                "destination_id": car_b.id,
                # max_depth=2 keeps the results easier to assert
                "max_depth": 2,
                "max_paths": 10,
                "kind_filter": ["TestPerson"],
            }
        }

        data, errors = await _run_resolver(
            db=db, branch=default_branch_scope_class, session=session_admin_scope_class, variables=variables
        )

        assert errors is None
        assert data is not None
        result = data["InfrahubPathTraversal"]
        assert result["count"] == 1
        only = result["paths"][0]
        assert only["depth"] == 2
        assert [hop["node"]["id"] for hop in only["hops"]] == [car_a.id, person.id, car_b.id]

    async def test_resolver_relationship_filter_blocks_all_hops(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        default_permission_backend_scope_class: None,
        session_admin_scope_class: AccountSession,
        two_cars_one_owner_scope_class: tuple[Node, Node, Node],
    ) -> None:
        # No schema relationship matches the supplied identifier
        car_a, _car_b, person = two_cars_one_owner_scope_class
        default_branch_scope_class.update_schema_hash()

        variables = {
            "data": {
                "source_id": car_a.id,
                "destination_id": person.id,
                "max_depth": 5,
                "max_paths": 10,
                "relationship_filter": ["nonexistent_relationship_identifier"],
            }
        }

        data, errors = await _run_resolver(
            db=db, branch=default_branch_scope_class, session=session_admin_scope_class, variables=variables
        )

        assert errors is None
        assert data is not None
        assert data["InfrahubPathTraversal"]["count"] == 0

    async def test_resolver_excluded_namespaces_prunes_intermediate_kind(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        default_permission_backend_scope_class: None,
        session_admin_scope_class: AccountSession,
        two_cars_one_owner_scope_class: tuple[Node, Node, Node],
    ) -> None:
        # excluded_namespaces blocks all schemas in the path
        car_a, _car_b, person = two_cars_one_owner_scope_class
        default_branch_scope_class.update_schema_hash()

        variables = {
            "data": {
                "source_id": car_a.id,
                "destination_id": person.id,
                "max_depth": 5,
                "max_paths": 10,
                "excluded_namespaces": ["Test"],
            }
        }

        data, errors = await _run_resolver(
            db=db, branch=default_branch_scope_class, session=session_admin_scope_class, variables=variables
        )

        assert errors is None
        assert data is not None
        assert data["InfrahubPathTraversal"]["count"] == 0

    async def test_resolver_reports_effective_excluded_kinds(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        default_permission_backend_scope_class: None,
        session_admin_scope_class: AccountSession,
        two_cars_one_owner_scope_class: tuple[Node, Node, Node],
    ) -> None:
        car_a, _car_b, person = two_cars_one_owner_scope_class
        default_branch_scope_class.update_schema_hash()

        base = {"source_id": car_a.id, "destination_id": person.id, "max_depth": 1, "max_paths": 10}

        # Default: the BuiltinIPNamespace implementers are excluded.
        data, errors = await _run_resolver(
            db=db, branch=default_branch_scope_class, session=session_admin_scope_class, variables={"data": dict(base)}
        )
        assert errors is None
        assert data is not None
        assert data["InfrahubPathTraversal"]["excluded_kinds"] == ["IpamNamespace"]

        # included_kinds lifts the default exclusion.
        data, errors = await _run_resolver(
            db=db,
            branch=default_branch_scope_class,
            session=session_admin_scope_class,
            variables={"data": dict(base, included_kinds=["IpamNamespace"])},
        )
        assert errors is None
        assert data is not None
        assert data["InfrahubPathTraversal"]["excluded_kinds"] == []

        # Requested exclusions are reported alongside the defaults.
        data, errors = await _run_resolver(
            db=db,
            branch=default_branch_scope_class,
            session=session_admin_scope_class,
            variables={"data": dict(base, excluded_kinds=["TestCar"])},
        )
        assert errors is None
        assert data is not None
        assert data["InfrahubPathTraversal"]["excluded_kinds"] == ["IpamNamespace", "TestCar"]

    async def test_resolver_raises_for_missing_source(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        default_permission_backend_scope_class: None,
        session_admin_scope_class: AccountSession,
        two_cars_one_owner_scope_class: tuple[Node, Node, Node],
    ) -> None:
        _car_a, car_b, _person = two_cars_one_owner_scope_class
        default_branch_scope_class.update_schema_hash()

        missing_id = "00000000-0000-0000-0000-000000000001"
        variables = {"data": {"source_id": missing_id, "destination_id": car_b.id}}

        _data, errors = await _run_resolver(
            db=db, branch=default_branch_scope_class, session=session_admin_scope_class, variables=variables
        )
        assert errors is not None
        assert errors[0].message == f"Source node not found: {missing_id}"

    async def test_resolver_raises_for_missing_destination(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        default_permission_backend_scope_class: None,
        session_admin_scope_class: AccountSession,
        two_cars_one_owner_scope_class: tuple[Node, Node, Node],
    ) -> None:
        car_a, _car_b, _person = two_cars_one_owner_scope_class
        default_branch_scope_class.update_schema_hash()

        missing_id = "00000000-0000-0000-0000-000000000002"
        variables = {"data": {"source_id": car_a.id, "destination_id": missing_id}}

        _data, errors = await _run_resolver(
            db=db, branch=default_branch_scope_class, session=session_admin_scope_class, variables=variables
        )
        assert errors is not None
        assert errors[0].message == f"Destination node not found: {missing_id}"

    async def test_resolver_raises_when_source_equals_destination(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        default_permission_backend_scope_class: None,
        session_admin_scope_class: AccountSession,
        two_cars_one_owner_scope_class: tuple[Node, Node, Node],
    ) -> None:
        car_a, _car_b, _person = two_cars_one_owner_scope_class
        default_branch_scope_class.update_schema_hash()

        variables = {"data": {"source_id": car_a.id, "destination_id": car_a.id}}

        _data, errors = await _run_resolver(
            db=db, branch=default_branch_scope_class, session=session_admin_scope_class, variables=variables
        )
        assert errors is not None
        assert errors[0].message == "Source and destination nodes must be different"


async def test_resolver_respects_session_permissions(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    authentication_base: Node,
    session_first_account: AccountSession,
    two_cars_one_owner: tuple[Node, Node, Node],
) -> None:
    # Account has no view permissions assigned. Stays function-scoped: its
    # account/permission fixture chain has no class-scoped variants.
    car_a, _car_b, person = two_cars_one_owner
    default_branch.update_schema_hash()

    variables = {
        "data": {
            "source_id": car_a.id,
            "destination_id": person.id,
            "max_depth": 1,
            "max_paths": 10,
        }
    }

    data, errors = await _run_resolver(db=db, branch=default_branch, session=session_first_account, variables=variables)

    assert errors is None
    assert data is not None
    result = data["InfrahubPathTraversal"]
    assert result["count"] == 0
    assert result["paths"] == []
