from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.initialization import create_branch
from infrahub.core.schema_change.enums import (
    SchemaChangeApplicationStatus,
    SchemaChangeMigrationStatus,
    SchemaChangeStatus,
)
from infrahub.core.schema_change.factory import build_schema_change_history_reader
from infrahub.core.timestamp import Timestamp
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.db_query_counter import CountingInfrahubDatabase
from tests.helpers.graphql import graphql
from tests.helpers.schema_change import (
    SEEDED_FAILURE_ERROR,
    BranchHistorySeed,
    MigrationSeed,
    SeededSchemaChangeHistory,
    attribute_migration,
    seed_application,
    seed_schema_change_history,
)

if TYPE_CHECKING:
    from graphql import ExecutionResult

    from infrahub.auth.session import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.schema_change.models import SchemaChange
    from infrahub.database import InfrahubDatabase

BRANCH_WITH_CHANGES = "schema-change-branch"
BRANCH_WITHOUT_CHANGE = "branch-without-schema-change"
MIGRATION_ERROR = "Unable to convert the value of 2 nodes"
NBR_OPERATIONS = 3
MAIN_SUMMARY = "testcar_color_update_and_2_more"
BRANCH_SUMMARY = "testcar_color_update"

SCHEMA_CHANGES_QUERY = """
query($limit: Int, $offset: Int, $status: [SchemaChangeStatus!]) {
  InfrahubSchemaChange(limit: $limit, offset: $offset, status: $status) {
    count
    edges {
      node {
        id
        name
        summary
        version
        status
        source
        branch
        created_at
        updated_at
        applied_at
        parent { id name version branch }
      }
    }
  }
}
"""

OPERATIONS_QUERY = """
query($operations_limit: Int, $operations_offset: Int) {
  InfrahubSchemaChange(limit: 1, offset: 0) {
    edges {
      node {
        id
        operations(limit: $operations_limit, offset: $operations_offset) {
          count
          edges {
            node {
              position
              operation_type
              kind
              node_type
              section
              element_name
              property_name
              value
              previous_value
            }
          }
        }
      }
    }
  }
}
"""

APPLICATIONS_QUERY = """
query(
  $limit: Int
  $applications_limit: Int
  $applications_offset: Int
  $migrations_limit: Int
  $migrations_offset: Int
) {
  InfrahubSchemaChange(limit: $limit) {
    edges {
      node {
        id
        applications(limit: $applications_limit, offset: $applications_offset) {
          count
          edges {
            node {
              id
              status
              branch
              at
              error
              created_at
              updated_at
              migrations(limit: $migrations_limit, offset: $migrations_offset) {
                count
                edges {
                  node {
                    id
                    position
                    migration_name
                    path
                    path_type
                    schema_kind
                    field_name
                    property_name
                    status
                    errors
                    updated_at
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
"""

NESTED_FIELDS_QUERY = """
query($limit: Int) {
  InfrahubSchemaChange(limit: $limit, offset: 0) {
    count
    edges {
      node {
        name
        parent { name }
        operations(limit: 2) { count edges { node { position value } } }
        applications(limit: 2) {
          count
          edges { node { status migrations(limit: 1) { count edges { node { status errors } } } } }
        }
      }
    }
  }
}
"""


@dataclass(frozen=True)
class RefusedPageCase:
    name: str
    query: str
    variables: dict[str, Any]
    expected_error: str


REFUSED_PAGE_CASES: list[RefusedPageCase] = [
    RefusedPageCase(
        name="limit_below_1", query=SCHEMA_CHANGES_QUERY, variables={"limit": 0}, expected_error="limit must be >= 1"
    ),
    RefusedPageCase(
        name="limit_above_maximum",
        query=SCHEMA_CHANGES_QUERY,
        variables={"limit": 51},
        expected_error="limit must be <= 50",
    ),
    RefusedPageCase(
        name="offset_below_0",
        query=SCHEMA_CHANGES_QUERY,
        variables={"offset": -1},
        expected_error="offset must be >= 0",
    ),
    RefusedPageCase(
        name="operations_limit_below_1",
        query=OPERATIONS_QUERY,
        variables={"operations_limit": 0},
        expected_error="limit must be >= 1",
    ),
    RefusedPageCase(
        name="operations_limit_above_maximum",
        query=OPERATIONS_QUERY,
        variables={"operations_limit": 501},
        expected_error="limit must be <= 500",
    ),
    RefusedPageCase(
        name="operations_offset_below_0",
        query=OPERATIONS_QUERY,
        variables={"operations_offset": -1},
        expected_error="offset must be >= 0",
    ),
    RefusedPageCase(
        name="applications_limit_below_1",
        query=APPLICATIONS_QUERY,
        variables={"limit": 1, "applications_limit": 0},
        expected_error="limit must be >= 1",
    ),
    RefusedPageCase(
        name="applications_limit_above_maximum",
        query=APPLICATIONS_QUERY,
        variables={"limit": 1, "applications_limit": 51},
        expected_error="limit must be <= 50",
    ),
    RefusedPageCase(
        name="applications_offset_below_0",
        query=APPLICATIONS_QUERY,
        variables={"limit": 1, "applications_offset": -1},
        expected_error="offset must be >= 0",
    ),
    RefusedPageCase(
        name="migrations_limit_below_1",
        query=APPLICATIONS_QUERY,
        variables={"limit": 1, "applications_limit": 1, "migrations_limit": 0},
        expected_error="limit must be >= 1",
    ),
    RefusedPageCase(
        name="migrations_limit_above_maximum",
        query=APPLICATIONS_QUERY,
        variables={"limit": 1, "applications_limit": 1, "migrations_limit": 501},
        expected_error="limit must be <= 500",
    ),
    RefusedPageCase(
        name="migrations_offset_below_0",
        query=APPLICATIONS_QUERY,
        variables={"limit": 1, "applications_limit": 1, "migrations_offset": -1},
        expected_error="offset must be >= 0",
    ),
]


@dataclass(frozen=True)
class NestedPageCase:
    name: str
    variables: dict[str, Any]
    expected: dict[str, tuple[int, list[tuple[str, int, list[int]]]]]
    """For each schema change of main, its number of applications and, for each application on the page, its
    name, its number of migration records and the positions of the migration records on the page."""


NESTED_PAGE_CASES: list[NestedPageCase] = [
    NestedPageCase(
        name="second_application_of_each_schema_change",
        variables={"applications_limit": 1, "applications_offset": 1},
        expected={"applied_1": (3, [("later_1", 0, [])]), "failed": (1, []), "applied_2": (1, [])},
    ),
    NestedPageCase(
        name="applications_past_the_end",
        variables={"applications_offset": 3},
        expected={"applied_1": (3, []), "failed": (1, []), "applied_2": (1, [])},
    ),
    NestedPageCase(
        name="second_migration_record_of_each_first_application",
        variables={"applications_limit": 1, "migrations_limit": 1, "migrations_offset": 1},
        expected={
            "applied_1": (3, [("applied_1", 2, [1])]),
            "failed": (1, [("failed", 2, [1])]),
            "applied_2": (1, [("applied_2", 2, [1])]),
        },
    ),
    NestedPageCase(
        name="migration_records_past_the_end",
        variables={"applications_limit": 2, "migrations_offset": 2},
        expected={
            "applied_1": (3, [("applied_1", 2, []), ("later_1", 0, [])]),
            "failed": (1, [("failed", 2, [])]),
            "applied_2": (1, [("applied_2", 2, [])]),
        },
    ),
]


@dataclass(frozen=True)
class LaterApplication:
    id: str
    branch: str
    status: str
    at: Timestamp


@dataclass(frozen=True)
class SeededQueryHistory:
    branches: dict[str, Branch]
    history: SeededSchemaChangeHistory
    later_applications: list[LaterApplication]
    """Two more applications of the first schema change of main, in the order of their `at`."""


@pytest.fixture(scope="class")
async def seeded_query_history(
    db: InfrahubDatabase,
    default_branch_scope_class: Branch,
    register_core_models_schema_scope_class: SchemaBranch,
    session_admin_scope_class: AccountSession,
) -> SeededQueryHistory:
    branch_with_changes = await create_branch(branch_name=BRANCH_WITH_CHANGES, db=db)
    branch_without_change = await create_branch(branch_name=BRANCH_WITHOUT_CHANGE, db=db)
    main_history = await seed_schema_change_history(
        db=db,
        branches=[
            BranchHistorySeed(
                branch=default_branch_scope_class.name,
                changes=[SchemaChangeStatus.APPLIED, SchemaChangeStatus.FAILED, SchemaChangeStatus.APPLIED],
                nbr_operations=NBR_OPERATIONS,
                migrations=[
                    MigrationSeed(
                        migration=attribute_migration(),
                        status=SchemaChangeMigrationStatus.APPLIED,
                        nbr_migrations_executed=0,
                    ),
                    MigrationSeed(
                        migration=attribute_migration(migration_name="attribute.kind.update", field_name="name"),
                        status=SchemaChangeMigrationStatus.FAILED,
                        nbr_migrations_executed=1,
                        errors=(MIGRATION_ERROR,),
                    ),
                ],
            )
        ],
    )
    branch_history = await seed_schema_change_history(
        db=db,
        branches=[
            BranchHistorySeed(
                branch=BRANCH_WITH_CHANGES,
                changes=[SchemaChangeStatus.APPLIED, SchemaChangeStatus.APPLIED],
                first_version=3,
                first_parent_id=main_history.applied_on_branch(default_branch_scope_class.name)[-1].id,
            )
        ],
    )
    first_main_change = main_history.on_branch(default_branch_scope_class.name)[0]
    later_applications = [
        LaterApplication(
            id="",
            branch=BRANCH_WITH_CHANGES,
            status=SchemaChangeApplicationStatus.APPLIED.value,
            at=first_main_change.at.add(minutes=1),
        ),
        LaterApplication(
            id="",
            branch=BRANCH_WITHOUT_CHANGE,
            status=SchemaChangeApplicationStatus.RUNNING.value,
            at=first_main_change.at.add(minutes=2),
        ),
    ]
    later_application_ids = {
        application.branch: await seed_application(
            db=db,
            schema_change_id=first_main_change.id,
            branch=application.branch,
            status=SchemaChangeApplicationStatus(application.status),
            at=application.at,
        )
        for application in reversed(later_applications)
    }
    return SeededQueryHistory(
        later_applications=[
            replace(application, id=later_application_ids[application.branch]) for application in later_applications
        ],
        branches={
            default_branch_scope_class.name: default_branch_scope_class,
            BRANCH_WITH_CHANGES: branch_with_changes,
            BRANCH_WITHOUT_CHANGE: branch_without_change,
        },
        history=SeededSchemaChangeHistory(schema_changes=main_history.schema_changes + branch_history.schema_changes),
    )


class TestSchemaChangeHistoryQuery:
    async def _run_query(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        account_session: AccountSession,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        gql_params = await prepare_graphql_params(db=db, branch=branch, account_session=account_session)
        return await graphql(
            schema=gql_params.schema,
            source=query,
            context_value=gql_params.context,
            root_value=None,
            variable_values=variables or {},
        )

    async def _query_data(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        account_session: AccountSession,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = await self._run_query(
            db=db, branch=branch, account_session=account_session, query=query, variables=variables
        )
        assert result.errors is None, f"GraphQL errors: {result.errors}"
        assert result.data
        return result.data["InfrahubSchemaChange"]

    async def test_query_returns_the_schema_changes_of_the_branch_of_the_request_only(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        session_admin_scope_class: AccountSession,
        seeded_query_history: SeededQueryHistory,
    ) -> None:
        history = seeded_query_history.history

        main_data = await self._query_data(
            db=db,
            branch=default_branch_scope_class,
            account_session=session_admin_scope_class,
            query=SCHEMA_CHANGES_QUERY,
        )
        branch_data = await self._query_data(
            db=db,
            branch=seeded_query_history.branches[BRANCH_WITH_CHANGES],
            account_session=session_admin_scope_class,
            query=SCHEMA_CHANGES_QUERY,
        )

        applied_1, failed, applied_2 = history.on_branch(default_branch_scope_class.name)
        assert main_data["count"] == 3
        assert [(edge["node"]["id"], edge["node"]["branch"]) for edge in main_data["edges"]] == [
            (applied_2.id, default_branch_scope_class.name),
            (failed.id, default_branch_scope_class.name),
            (applied_1.id, default_branch_scope_class.name),
        ]
        branch_change_3, branch_change_4 = history.on_branch(BRANCH_WITH_CHANGES)
        assert branch_data["count"] == 2
        assert [(edge["node"]["id"], edge["node"]["branch"]) for edge in branch_data["edges"]] == [
            (branch_change_4.id, BRANCH_WITH_CHANGES),
            (branch_change_3.id, BRANCH_WITH_CHANGES),
        ]

    async def test_count_and_edges_follow_limit_and_offset(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        session_admin_scope_class: AccountSession,
        seeded_query_history: SeededQueryHistory,
    ) -> None:
        applied_1, failed, applied_2 = seeded_query_history.history.on_branch(default_branch_scope_class.name)

        first_page = await self._query_data(
            db=db,
            branch=default_branch_scope_class,
            account_session=session_admin_scope_class,
            query=SCHEMA_CHANGES_QUERY,
            variables={"limit": 2, "offset": 0},
        )
        second_page = await self._query_data(
            db=db,
            branch=default_branch_scope_class,
            account_session=session_admin_scope_class,
            query=SCHEMA_CHANGES_QUERY,
            variables={"limit": 2, "offset": 2},
        )
        failed_only = await self._query_data(
            db=db,
            branch=default_branch_scope_class,
            account_session=session_admin_scope_class,
            query=SCHEMA_CHANGES_QUERY,
            variables={"status": ["FAILED"]},
        )
        no_status = await self._query_data(
            db=db,
            branch=default_branch_scope_class,
            account_session=session_admin_scope_class,
            query=SCHEMA_CHANGES_QUERY,
            variables={"status": []},
        )

        assert (first_page["count"], [edge["node"]["id"] for edge in first_page["edges"]]) == (
            3,
            [applied_2.id, failed.id],
        )
        assert (second_page["count"], [edge["node"]["id"] for edge in second_page["edges"]]) == (3, [applied_1.id])
        assert (failed_only["count"], [edge["node"]["id"] for edge in failed_only["edges"]]) == (1, [failed.id])
        assert (no_status["count"], no_status["edges"]) == (0, [])

    async def test_schema_change_fields_have_the_values_of_the_contract(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        session_admin_scope_class: AccountSession,
        seeded_query_history: SeededQueryHistory,
    ) -> None:
        history = seeded_query_history.history
        applied_1, failed, applied_2 = history.on_branch(default_branch_scope_class.name)
        branch_change_3, branch_change_4 = history.on_branch(BRANCH_WITH_CHANGES)

        main_data = await self._query_data(
            db=db,
            branch=default_branch_scope_class,
            account_session=session_admin_scope_class,
            query=SCHEMA_CHANGES_QUERY,
        )
        branch_data = await self._query_data(
            db=db,
            branch=seeded_query_history.branches[BRANCH_WITH_CHANGES],
            account_session=session_admin_scope_class,
            query=SCHEMA_CHANGES_QUERY,
        )

        nodes = [edge["node"] for edge in [*reversed(main_data["edges"]), *reversed(branch_data["edges"])]]
        assert [
            {key: value for key, value in node.items() if key not in {"created_at", "updated_at", "applied_at"}}
            for node in nodes
        ] == [
            {
                "id": applied_1.id,
                "name": f"00001_{MAIN_SUMMARY}",
                "summary": MAIN_SUMMARY,
                "version": 1,
                "status": "APPLIED",
                "source": "USER",
                "branch": "main",
                "parent": None,
            },
            {
                "id": failed.id,
                "name": MAIN_SUMMARY,
                "summary": MAIN_SUMMARY,
                "version": None,
                "status": "FAILED",
                "source": "USER",
                "branch": "main",
                "parent": None,
            },
            {
                "id": applied_2.id,
                "name": f"00002_{MAIN_SUMMARY}",
                "summary": MAIN_SUMMARY,
                "version": 2,
                "status": "APPLIED",
                "source": "USER",
                "branch": "main",
                "parent": {"id": applied_1.id, "name": f"00001_{MAIN_SUMMARY}", "version": 1, "branch": "main"},
            },
            {
                "id": branch_change_3.id,
                "name": f"00003_{BRANCH_SUMMARY}",
                "summary": BRANCH_SUMMARY,
                "version": 3,
                "status": "APPLIED",
                "source": "USER",
                "branch": BRANCH_WITH_CHANGES,
                "parent": {"id": applied_2.id, "name": f"00002_{MAIN_SUMMARY}", "version": 2, "branch": "main"},
            },
            {
                "id": branch_change_4.id,
                "name": f"00004_{BRANCH_SUMMARY}",
                "summary": BRANCH_SUMMARY,
                "version": 4,
                "status": "APPLIED",
                "source": "USER",
                "branch": BRANCH_WITH_CHANGES,
                "parent": {
                    "id": branch_change_3.id,
                    "name": f"00003_{BRANCH_SUMMARY}",
                    "version": 3,
                    "branch": BRANCH_WITH_CHANGES,
                },
            },
        ]
        assert [Timestamp(node["applied_at"]) if node["applied_at"] else None for node in nodes] == [
            applied_1.at,
            None,
            applied_2.at,
            branch_change_3.at,
            branch_change_4.at,
        ]

        reader = build_schema_change_history_reader(db=db)
        stored: dict[str, SchemaChange] = {}
        for branch_name in (default_branch_scope_class.name, BRANCH_WITH_CHANGES):
            page = await reader.list_schema_changes(branch=branch_name, limit=10, offset=0)
            stored.update({str(entry.schema_change.uuid): entry.schema_change for entry in page.entries})
        assert len(stored) == len(nodes)
        assert [(Timestamp(node["created_at"]), Timestamp(node["updated_at"])) for node in nodes] == [
            (Timestamp(stored[node["id"]].created_at), Timestamp(stored[node["id"]].updated_at)) for node in nodes
        ]

    async def test_operations_come_in_pages_in_the_order_of_position_with_the_count(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        session_admin_scope_class: AccountSession,
        seeded_query_history: SeededQueryHistory,
    ) -> None:
        latest_change = seeded_query_history.history.on_branch(default_branch_scope_class.name)[-1]

        data = await self._query_data(
            db=db,
            branch=default_branch_scope_class,
            account_session=session_admin_scope_class,
            query=OPERATIONS_QUERY,
            variables={"operations_limit": 2, "operations_offset": 1},
        )

        (edge,) = data["edges"]
        assert edge["node"]["id"] == latest_change.id
        operations = edge["node"]["operations"]
        assert operations["count"] == NBR_OPERATIONS
        assert [operation["node"] for operation in operations["edges"]] == [
            {
                "position": position,
                "operation_type": "ELEMENT_PROPERTY",
                "kind": "TestCar",
                "node_type": None,
                "section": "ATTRIBUTES",
                "element_name": "color",
                "property_name": "label",
                "value": f"Color {position}",
                "previous_value": f"Color {position - 1}",
            }
            for position in (1, 2)
        ]

    async def test_applications_and_their_migration_records_have_the_values_of_the_contract(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        session_admin_scope_class: AccountSession,
        seeded_query_history: SeededQueryHistory,
    ) -> None:
        applied_1, failed, applied_2 = seeded_query_history.history.on_branch(default_branch_scope_class.name)
        later_1, later_2 = seeded_query_history.later_applications

        data = await self._query_data(
            db=db,
            branch=default_branch_scope_class,
            account_session=session_admin_scope_class,
            query=APPLICATIONS_QUERY,
        )

        def describe(application: dict[str, Any]) -> dict[str, Any]:
            return {
                "id": application["id"],
                "status": application["status"],
                "branch": application["branch"],
                "at": Timestamp(application["at"]),
                "error": application["error"],
                "migrations": {
                    "count": application["migrations"]["count"],
                    "edges": [
                        {key: value for key, value in edge["node"].items() if key not in {"id", "updated_at"}}
                        for edge in application["migrations"]["edges"]
                    ],
                },
            }

        def migration(position: int, status: str) -> dict[str, Any]:
            first = position == 0
            return {
                "position": position,
                "migration_name": "node.attribute.add" if first else "attribute.kind.update",
                "path": "schema/TestCar/color" if first else "schema/TestCar/name",
                "path_type": "ATTRIBUTE",
                "schema_kind": "TestCar",
                "field_name": "color" if first else "name",
                "property_name": None,
                "status": status,
                "errors": [] if first else [MIGRATION_ERROR],
            }

        assert {
            edge["node"]["id"]: {
                "count": edge["node"]["applications"]["count"],
                "edges": [describe(application["node"]) for application in edge["node"]["applications"]["edges"]],
            }
            for edge in data["edges"]
        } == {
            applied_1.id: {
                "count": 3,
                "edges": [
                    {
                        "id": applied_1.application_id,
                        "status": "APPLIED",
                        "branch": "main",
                        "at": applied_1.at,
                        "error": None,
                        "migrations": {"count": 2, "edges": [migration(0, "APPLIED"), migration(1, "FAILED")]},
                    },
                    {
                        "id": later_1.id,
                        "status": "APPLIED",
                        "branch": BRANCH_WITH_CHANGES,
                        "at": later_1.at,
                        "error": None,
                        "migrations": {"count": 0, "edges": []},
                    },
                    {
                        "id": later_2.id,
                        "status": "RUNNING",
                        "branch": BRANCH_WITHOUT_CHANGE,
                        "at": later_2.at,
                        "error": None,
                        "migrations": {"count": 0, "edges": []},
                    },
                ],
            },
            failed.id: {
                "count": 1,
                "edges": [
                    {
                        "id": failed.application_id,
                        "status": "FAILED",
                        "branch": "main",
                        "at": failed.at,
                        "error": SEEDED_FAILURE_ERROR,
                        "migrations": {"count": 2, "edges": [migration(0, "ROLLED_BACK"), migration(1, "FAILED")]},
                    }
                ],
            },
            applied_2.id: {
                "count": 1,
                "edges": [
                    {
                        "id": applied_2.application_id,
                        "status": "APPLIED",
                        "branch": "main",
                        "at": applied_2.at,
                        "error": None,
                        "migrations": {"count": 2, "edges": [migration(0, "APPLIED"), migration(1, "FAILED")]},
                    }
                ],
            },
        }

    @pytest.mark.parametrize("test_case", [pytest.param(case, id=case.name) for case in NESTED_PAGE_CASES])
    async def test_applications_and_migration_records_come_in_pages_with_their_count(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        session_admin_scope_class: AccountSession,
        seeded_query_history: SeededQueryHistory,
        test_case: NestedPageCase,
    ) -> None:
        applied_1, failed, applied_2 = seeded_query_history.history.on_branch(default_branch_scope_class.name)
        later_1, later_2 = seeded_query_history.later_applications
        application_ids = {
            "applied_1": applied_1.application_id,
            "later_1": later_1.id,
            "later_2": later_2.id,
            "failed": failed.application_id,
            "applied_2": applied_2.application_id,
        }
        names = {application_id: name for name, application_id in application_ids.items()}

        data = await self._query_data(
            db=db,
            branch=default_branch_scope_class,
            account_session=session_admin_scope_class,
            query=APPLICATIONS_QUERY,
            variables=test_case.variables,
        )

        assert {
            edge["node"]["id"]: (
                edge["node"]["applications"]["count"],
                [
                    (
                        names[application["node"]["id"]],
                        application["node"]["migrations"]["count"],
                        [migration["node"]["position"] for migration in application["node"]["migrations"]["edges"]],
                    )
                    for application in edge["node"]["applications"]["edges"]
                ],
            )
            for edge in data["edges"]
        } == {
            applied_1.id: test_case.expected["applied_1"],
            failed.id: test_case.expected["failed"],
            applied_2.id: test_case.expected["applied_2"],
        }

    @pytest.mark.parametrize("test_case", [pytest.param(case, id=case.name) for case in REFUSED_PAGE_CASES])
    async def test_out_of_range_limit_or_offset_is_refused(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        session_admin_scope_class: AccountSession,
        seeded_query_history: SeededQueryHistory,
        test_case: RefusedPageCase,
    ) -> None:
        result = await self._run_query(
            db=db,
            branch=default_branch_scope_class,
            account_session=session_admin_scope_class,
            query=test_case.query,
            variables=test_case.variables,
        )

        assert result.errors
        assert [error.message for error in result.errors] == [test_case.expected_error]

    async def test_branch_without_schema_change_returns_an_empty_page(
        self,
        db: InfrahubDatabase,
        session_admin_scope_class: AccountSession,
        seeded_query_history: SeededQueryHistory,
    ) -> None:
        data = await self._query_data(
            db=db,
            branch=seeded_query_history.branches[BRANCH_WITHOUT_CHANGE],
            account_session=session_admin_scope_class,
            query=SCHEMA_CHANGES_QUERY,
        )

        assert data == {"count": 0, "edges": []}

    async def test_a_page_runs_the_same_number_of_queries_whatever_its_number_of_schema_changes(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        session_admin_scope_class: AccountSession,
        seeded_query_history: SeededQueryHistory,
    ) -> None:
        counting_db = CountingInfrahubDatabase.from_db(db=db)

        async def count_queries(limit: int) -> tuple[int, int]:
            counting_db.reset_counts()
            data = await self._query_data(
                db=counting_db,
                branch=default_branch_scope_class,
                account_session=session_admin_scope_class,
                query=NESTED_FIELDS_QUERY,
                variables={"limit": limit},
            )
            return len(data["edges"]), sum(counting_db.query_counts.values())

        await count_queries(limit=1)
        nbr_edges_small_page, nbr_queries_small_page = await count_queries(limit=1)
        nbr_edges_full_page, nbr_queries_full_page = await count_queries(limit=3)

        assert (nbr_edges_small_page, nbr_edges_full_page) == (1, 3)
        assert nbr_queries_small_page > 0
        assert nbr_queries_full_page == nbr_queries_small_page
