from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub import config
from infrahub.auth.session import AccountSession, AnonymousSession
from infrahub.auth.types import AuthType
from infrahub.core.account import ObjectPermission
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.constants import (
    GLOBAL_BRANCH_NAME,
    InfrahubKind,
    PermissionDecision,
    RepositoryInternalStatus,
    RepositorySyncStatus,
)
from infrahub.core.node import Node
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices
from tests.component.conftest import make_repository_pair
from tests.conftest import TestHelper
from tests.helpers.db_query_counter import CountingInfrahubDatabase
from tests.helpers.graphql import graphql
from tests.helpers.permissions import define_permissions

if TYPE_CHECKING:
    from collections.abc import Generator, Mapping

    from graphql import ExecutionResult

    from infrahub.core.protocols import CoreReadOnlyRepository, CoreRepository
    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusRecorder
    from tests.component.conftest import RepositoryBranchStatusBranches

ANONYMOUS_UNKNOWN_ROLE = "rbs-anonymous-without-a-role"

# The shared branch fixture saves 214 branches; two carry a terminal status, so 212 remain
# alongside the default branch. The read-write kind drops the one non-syncing branch on top.
READ_ONLY_ROW_COUNT = 213
READ_WRITE_ROW_COUNT = 212

ANONYMOUS_GRANTED_ROLE = "rbs-anonymous-granted"

ROWS_QUERY = """
query(
    $id: String!
    $limit: Int
    $offset: Int
    $name: String
    $partial_match: Boolean
    $status: BranchStatus
) {
  InfrahubRepositoryBranchStatus(
    id: $id
    limit: $limit
    offset: $offset
    name__value: $name
    partial_match: $partial_match
    status__value: $status
  ) {
    count
    edges {
      node {
        name
        status
        is_default
        sync_with_git
        branched_from
        commit { value }
        sync_status { value label color }
        internal_status { value }
      }
    }
  }
}
"""

ORDERED_ROWS_QUERY = """
query($id: String!, $limit: Int, $direction: OrderDirection!) {
  InfrahubRepositoryBranchStatus(id: $id, limit: $limit, order: {node_metadata: {created_at: $direction}}) {
    count
    edges {
      node { name }
    }
  }
}
"""

REF_QUERY = """
query($id: String!, $limit: Int, $name: String, $partial_match: Boolean) {
  InfrahubRepositoryBranchStatus(id: $id, limit: $limit, name__value: $name, partial_match: $partial_match) {
    count
    edges {
      node {
        name
        ref { value }
        commit { value }
      }
    }
  }
}
"""

NAMES_ONLY_QUERY = """
query($id: String!, $limit: Int) {
  InfrahubRepositoryBranchStatus(id: $id, limit: $limit) {
    edges {
      node { name }
    }
  }
}
"""

UPDATED_AT_QUERY = """
query($id: String!, $limit: Int, $name: String) {
  InfrahubRepositoryBranchStatus(id: $id, limit: $limit, name__value: $name) {
    edges {
      node {
        name
        commit { value updated_at }
        sync_status { value updated_at }
        internal_status { value updated_at }
      }
    }
  }
}
"""

EMPTY_ORDER_QUERY = """
query($id: String!, $limit: Int) {
  InfrahubRepositoryBranchStatus(id: $id, limit: $limit, order: {}) {
    edges {
      node { name }
    }
  }
}
"""

EMPTY_NODE_METADATA_ORDER_QUERY = """
query($id: String!, $limit: Int) {
  InfrahubRepositoryBranchStatus(id: $id, limit: $limit, order: {node_metadata: {}}) {
    edges {
      node { name }
    }
  }
}
"""

CONTRADICTORY_ORDER_QUERY = """
query($id: String!, $limit: Int) {
  InfrahubRepositoryBranchStatus(
    id: $id
    limit: $limit
    order: {node_metadata: {created_at: ASC, updated_at: ASC}}
  ) {
    edges {
      node { name }
    }
  }
}
"""

# The placeholder source dates every value at 2026-01-01T00:00:00Z; graphene renders it in this shape.
EXPECTED_UPDATED_AT = "2026-01-01T00:00:00+00:00"


@dataclass(frozen=True)
class PermissionGrant:
    """One caller shape in the view-permission matrix."""

    name: str
    """Identifier of the grant, also used to name the account, role and group."""

    decisions: tuple[PermissionDecision, ...]
    """Decisions granted on viewing the read-write repository kind, one object permission each."""

    allowed: bool
    """Whether the caller is expected to see rows."""


PERMISSION_GRANTS = (
    PermissionGrant(name="allow-all", decisions=(PermissionDecision.ALLOW_ALL,), allowed=True),
    PermissionGrant(
        name="allow-default-and-other",
        decisions=(PermissionDecision.ALLOW_DEFAULT, PermissionDecision.ALLOW_OTHER),
        allowed=True,
    ),
    PermissionGrant(name="allow-default-only", decisions=(PermissionDecision.ALLOW_DEFAULT,), allowed=False),
    PermissionGrant(name="allow-other-only", decisions=(PermissionDecision.ALLOW_OTHER,), allowed=False),
    PermissionGrant(name="no-grant", decisions=(), allowed=False),
)

DENIAL_MESSAGE = "You do not have the following permission: object:Core:Repository:view:allow_all"
READ_ONLY_DENIAL_MESSAGE = "You do not have the following permission: object:Core:ReadOnlyRepository:view:allow_all"


@dataclass(frozen=True)
class SingleKindCase:
    """A caller granted view on exactly one repository kind, querying one of the two kinds."""

    name: str
    """Identifier of the case, also used as the pytest id."""

    granted_kind_name: str
    """Repository kind name the caller is granted view on, within the Core namespace."""

    query_read_only_repository: bool
    """Whether the query targets the read-only repository rather than the read-write one."""

    denial_message: str | None
    """Exact error message the caller receives, or None when the caller is expected to see rows."""


SINGLE_KIND_NAMES = ("Repository", "ReadOnlyRepository")

SINGLE_KIND_CASES = (
    SingleKindCase(
        name="read-write-grant-on-read-write-repository",
        granted_kind_name="Repository",
        query_read_only_repository=False,
        denial_message=None,
    ),
    SingleKindCase(
        name="read-write-grant-on-read-only-repository",
        granted_kind_name="Repository",
        query_read_only_repository=True,
        denial_message=READ_ONLY_DENIAL_MESSAGE,
    ),
    SingleKindCase(
        name="read-only-grant-on-read-only-repository",
        granted_kind_name="ReadOnlyRepository",
        query_read_only_repository=True,
        denial_message=None,
    ),
    SingleKindCase(
        name="read-only-grant-on-read-write-repository",
        granted_kind_name="ReadOnlyRepository",
        query_read_only_repository=False,
        denial_message=DENIAL_MESSAGE,
    ),
)


@dataclass(frozen=True)
class InvalidPagingCase:
    """A paging argument the resolver must reject before it reads anything."""

    name: str
    """Identifier of the case, also used as the pytest id."""

    variables: Mapping[str, Any]
    """Query variables overriding the paging arguments."""

    message: str
    """Exact error message the caller receives."""


INVALID_PAGING_CASES = (
    InvalidPagingCase(name="limit-below-one", variables={"limit": 0}, message="limit must be >= 1"),
    InvalidPagingCase(name="negative-offset", variables={"offset": -1}, message="offset must be >= 0"),
    InvalidPagingCase(name="explicit-null-limit", variables={"limit": None}, message="limit must be >= 1"),
    InvalidPagingCase(name="explicit-null-offset", variables={"offset": None}, message="offset must be >= 0"),
)


def _view_repository_permission(decision: PermissionDecision) -> ObjectPermission:
    return ObjectPermission(namespace="Core", name="Repository", action="view", decision=decision.value)


async def _create_role_with_repository_view(db: InfrahubDatabase, name: str) -> Node:
    permission = await Node.init(db=db, schema=InfrahubKind.OBJECTPERMISSION)
    await permission.new(
        db=db, namespace="Core", name="Repository", action="view", decision=PermissionDecision.ALLOW_ALL.value
    )
    await permission.save(db=db)

    role = await Node.init(db=db, schema=InfrahubKind.ACCOUNTROLE)
    await role.new(db=db, name=name, permissions=[permission])
    await role.save(db=db)
    return role


@pytest.fixture(scope="module")
async def repositories(
    db: InfrahubDatabase, repository_branch_status_branches: RepositoryBranchStatusBranches
) -> tuple[CoreRepository, CoreReadOnlyRepository]:
    return await make_repository_pair(db=db)


@pytest.fixture(scope="module")
async def reader_session(
    db: InfrahubDatabase, repository_branch_status_branches: RepositoryBranchStatusBranches
) -> AccountSession:
    """Session allowed to view every repository kind on every branch."""
    account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await account.new(db=db, name="rbs-reader", account_type="User", password="rbs-reader-password")
    await account.save(db=db)
    await define_permissions(
        account=account,
        db=db,
        object_permissions=[
            ObjectPermission(namespace="Core", name="*", action="view", decision=PermissionDecision.ALLOW_ALL.value)
        ],
        role_name="rbs-reader-role",
        group_name="rbs-reader-group",
    )
    return AccountSession(authenticated=True, auth_type=AuthType.API, account_id=account.id)


@pytest.fixture(scope="module")
async def matrix_sessions(
    db: InfrahubDatabase, repository_branch_status_branches: RepositoryBranchStatusBranches
) -> Mapping[str, AccountSession]:
    sessions: dict[str, AccountSession] = {}
    for grant in PERMISSION_GRANTS:
        account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
        await account.new(db=db, name=f"rbs-{grant.name}", account_type="User", password=f"rbs-{grant.name}-password")
        await account.save(db=db)
        await define_permissions(
            account=account,
            db=db,
            object_permissions=[_view_repository_permission(decision=decision) for decision in grant.decisions],
            role_name=f"rbs-{grant.name}-role",
            group_name=f"rbs-{grant.name}-group",
        )
        sessions[grant.name] = AccountSession(authenticated=True, auth_type=AuthType.API, account_id=account.id)
    return sessions


@pytest.fixture(scope="module")
async def single_kind_sessions(
    db: InfrahubDatabase, repository_branch_status_branches: RepositoryBranchStatusBranches
) -> Mapping[str, AccountSession]:
    """One session per repository kind, each granted view on that kind alone."""
    sessions: dict[str, AccountSession] = {}
    for kind_name in SINGLE_KIND_NAMES:
        slug = f"rbs-only-{kind_name.lower()}"
        account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
        await account.new(db=db, name=slug, account_type="User", password=f"{slug}-password")
        await account.save(db=db)
        await define_permissions(
            account=account,
            db=db,
            object_permissions=[
                ObjectPermission(
                    namespace="Core", name=kind_name, action="view", decision=PermissionDecision.ALLOW_ALL.value
                )
            ],
            role_name=f"{slug}-role",
            group_name=f"{slug}-group",
        )
        sessions[kind_name] = AccountSession(authenticated=True, auth_type=AuthType.API, account_id=account.id)
    return sessions


@pytest.fixture(scope="module")
async def anonymous_granted_role(
    db: InfrahubDatabase, repository_branch_status_branches: RepositoryBranchStatusBranches
) -> Node:
    return await _create_role_with_repository_view(db=db, name=ANONYMOUS_GRANTED_ROLE)


@pytest.fixture
def anonymous_access_granted(anonymous_granted_role: Node) -> Generator[None, None, None]:
    """Point anonymous access at the role that grants the repository view, restoring the setting after."""
    original = config.SETTINGS.main.anonymous_access_role
    config.SETTINGS.main.anonymous_access_role = ANONYMOUS_GRANTED_ROLE
    yield
    config.SETTINGS.main.anonymous_access_role = original


@pytest.fixture
def anonymous_access_without_a_role() -> Generator[None, None, None]:
    """Point anonymous access at a role that does not exist, restoring the setting after."""
    original = config.SETTINGS.main.anonymous_access_role
    config.SETTINGS.main.anonymous_access_role = ANONYMOUS_UNKNOWN_ROLE
    yield
    config.SETTINGS.main.anonymous_access_role = original


@dataclass(frozen=True)
class RecordingBus:
    """A service and the recorder behind its message bus, so a test can read back what was published."""

    service: InfrahubServices
    recorder: BusRecorder


@pytest.fixture
async def recording_bus(db: InfrahubDatabase) -> RecordingBus:
    """Service whose message bus records every publish, so a send cannot go unnoticed."""
    recorder = TestHelper.get_message_bus_recorder()
    service = await InfrahubServices.new(database=db, message_bus=recorder)
    return RecordingBus(service=service, recorder=recorder)


async def _run(
    db: InfrahubDatabase,
    branch_name: str,
    source: str,
    variables: dict[str, Any],
    account_session: AccountSession | None = None,
    service: InfrahubServices | None = None,
) -> ExecutionResult:
    gql_params = await prepare_graphql_params(
        db=db, branch=branch_name, account_session=account_session, service=service
    )
    return await graphql(
        schema=gql_params.schema,
        source=source,
        context_value=gql_params.context,
        root_value=None,
        variable_values=variables,
    )


def _names(result: ExecutionResult) -> list[str]:
    assert result.data
    return [edge["node"]["name"] for edge in result.data["InfrahubRepositoryBranchStatus"]["edges"]]


def _nodes(result: ExecutionResult) -> list[dict[str, Any]]:
    assert result.data
    return [edge["node"] for edge in result.data["InfrahubRepositoryBranchStatus"]["edges"]]


class TestRepositoryBranchStatusRows:
    async def test_read_write_kind_returns_every_syncing_non_terminal_branch(
        self,
        db: InfrahubDatabase,
        repository_branch_status_branches: RepositoryBranchStatusBranches,
        repositories: tuple[CoreRepository, CoreReadOnlyRepository],
        reader_session: AccountSession,
        default_permission_backend: None,
    ) -> None:
        branches = repository_branch_status_branches
        repository, _ = repositories

        result = await _run(
            db=db,
            branch_name=branches.default_branch.name,
            source=ROWS_QUERY,
            variables={"id": repository.id, "limit": 1000},
            account_session=reader_session,
        )

        assert result.errors is None
        assert result.data
        assert result.data["InfrahubRepositoryBranchStatus"]["count"] == READ_WRITE_ROW_COUNT
        names = _names(result)
        assert len(names) == READ_WRITE_ROW_COUNT
        assert GLOBAL_BRANCH_NAME not in names
        assert branches.non_syncing not in names
        assert set(branches.terminal_status_names) & set(names) == set()
        assert set(branches.non_terminal_status_names) <= set(names)
        assert len(branches.non_terminal_status_names) == 5
        assert branches.default_branch.name in names
        assert branches.legacy_non_isolated in names
        assert {node["sync_with_git"] for node in _nodes(result)} == {True}

    async def test_read_only_kind_also_returns_the_non_syncing_branch(
        self,
        db: InfrahubDatabase,
        repository_branch_status_branches: RepositoryBranchStatusBranches,
        repositories: tuple[CoreRepository, CoreReadOnlyRepository],
        reader_session: AccountSession,
        default_permission_backend: None,
    ) -> None:
        branches = repository_branch_status_branches
        _, read_only_repository = repositories

        result = await _run(
            db=db,
            branch_name=branches.default_branch.name,
            source=ROWS_QUERY,
            variables={"id": read_only_repository.id, "limit": 1000},
            account_session=reader_session,
        )

        assert result.errors is None
        assert result.data
        assert result.data["InfrahubRepositoryBranchStatus"]["count"] == READ_ONLY_ROW_COUNT
        names = _names(result)
        assert len(names) == READ_ONLY_ROW_COUNT
        assert GLOBAL_BRANCH_NAME not in names
        assert branches.non_syncing in names
        assert set(branches.terminal_status_names) & set(names) == set()
        assert set(branches.non_terminal_status_names) <= set(names)
        sync_with_git = {node["name"]: node["sync_with_git"] for node in _nodes(result)}
        assert sync_with_git[branches.non_syncing] is False
        assert sync_with_git[branches.default_branch.name] is True
        assert set(sync_with_git.values()) == {True, False}

    async def test_every_non_terminal_status_is_reported(
        self,
        db: InfrahubDatabase,
        repository_branch_status_branches: RepositoryBranchStatusBranches,
        repositories: tuple[CoreRepository, CoreReadOnlyRepository],
        reader_session: AccountSession,
        default_permission_backend: None,
    ) -> None:
        branches = repository_branch_status_branches
        repository, _ = repositories

        result = await _run(
            db=db,
            branch_name=branches.default_branch.name,
            source=ROWS_QUERY,
            variables={"id": repository.id, "limit": 1000, "name": "rbs-status-", "partial_match": True},
            account_session=reader_session,
        )

        assert result.errors is None
        assert result.data
        assert result.data["InfrahubRepositoryBranchStatus"]["count"] == 5
        statuses = {node["name"]: node["status"] for node in _nodes(result)}
        assert statuses == {
            branches.by_status[BranchStatus.OPEN]: BranchStatus.OPEN.value,
            branches.by_status[BranchStatus.NEED_REBASE]: BranchStatus.NEED_REBASE.value,
            branches.by_status[BranchStatus.NEED_UPGRADE_REBASE]: BranchStatus.NEED_UPGRADE_REBASE.value,
            branches.by_status[BranchStatus.MERGING]: BranchStatus.MERGING.value,
            branches.by_status[BranchStatus.MERGE_FAILED]: BranchStatus.MERGE_FAILED.value,
        }

    async def test_count_and_default_order_across_pages(
        self,
        db: InfrahubDatabase,
        repository_branch_status_branches: RepositoryBranchStatusBranches,
        repositories: tuple[CoreRepository, CoreReadOnlyRepository],
        reader_session: AccountSession,
        default_permission_backend: None,
    ) -> None:
        branches = repository_branch_status_branches
        repository, _ = repositories

        first_page = await _run(
            db=db,
            branch_name=branches.default_branch.name,
            source=ROWS_QUERY,
            variables={"id": repository.id, "limit": 5, "offset": 0},
            account_session=reader_session,
        )
        assert first_page.errors is None
        assert first_page.data
        assert first_page.data["InfrahubRepositoryBranchStatus"]["count"] == READ_WRITE_ROW_COUNT
        assert _names(first_page) == [branches.default_branch.name, *branches.five[:4]]
        assert _nodes(first_page)[0]["is_default"] is True
        assert [node["is_default"] for node in _nodes(first_page)[1:]] == [False, False, False, False]

        tail_page = await _run(
            db=db,
            branch_name=branches.default_branch.name,
            source=ROWS_QUERY,
            variables={"id": repository.id, "limit": 40, "offset": READ_WRITE_ROW_COUNT - 3},
            account_session=reader_session,
        )
        assert tail_page.errors is None
        assert tail_page.data
        assert tail_page.data["InfrahubRepositoryBranchStatus"]["count"] == READ_WRITE_ROW_COUNT
        assert _names(tail_page) == [
            branches.by_status[BranchStatus.NEED_REBASE],
            branches.by_status[BranchStatus.NEED_UPGRADE_REBASE],
            branches.by_status[BranchStatus.OPEN],
        ]

        past_the_end = await _run(
            db=db,
            branch_name=branches.default_branch.name,
            source=ROWS_QUERY,
            variables={"id": repository.id, "limit": 40, "offset": READ_WRITE_ROW_COUNT},
            account_session=reader_session,
        )
        assert past_the_end.errors is None
        assert past_the_end.data
        assert past_the_end.data["InfrahubRepositoryBranchStatus"]["count"] == READ_WRITE_ROW_COUNT
        assert _names(past_the_end) == []

    async def test_order_argument_overrides_the_default_order(
        self,
        db: InfrahubDatabase,
        repository_branch_status_branches: RepositoryBranchStatusBranches,
        repositories: tuple[CoreRepository, CoreReadOnlyRepository],
        reader_session: AccountSession,
        default_permission_backend: None,
    ) -> None:
        branches = repository_branch_status_branches
        repository, _ = repositories

        result = await _run(
            db=db,
            branch_name=branches.default_branch.name,
            source=ORDERED_ROWS_QUERY,
            variables={"id": repository.id, "limit": 5, "direction": "DESC"},
            account_session=reader_session,
        )

        assert result.errors is None
        assert result.data
        assert result.data["InfrahubRepositoryBranchStatus"]["count"] == READ_WRITE_ROW_COUNT
        assert _names(result) == [
            branches.legacy_non_isolated,
            branches.by_status[BranchStatus.MERGE_FAILED],
            branches.by_status[BranchStatus.MERGING],
            branches.by_status[BranchStatus.NEED_UPGRADE_REBASE],
            branches.by_status[BranchStatus.NEED_REBASE],
        ]

    async def test_an_order_argument_expressing_no_ordering_keeps_the_default_order(
        self,
        db: InfrahubDatabase,
        repository_branch_status_branches: RepositoryBranchStatusBranches,
        repositories: tuple[CoreRepository, CoreReadOnlyRepository],
        reader_session: AccountSession,
        default_permission_backend: None,
    ) -> None:
        branches = repository_branch_status_branches
        repository, _ = repositories
        variables: dict[str, Any] = {"id": repository.id, "limit": 5}

        omitted = await _run(
            db=db,
            branch_name=branches.default_branch.name,
            source=NAMES_ONLY_QUERY,
            variables=variables,
            account_session=reader_session,
        )
        empty_order = await _run(
            db=db,
            branch_name=branches.default_branch.name,
            source=EMPTY_ORDER_QUERY,
            variables=variables,
            account_session=reader_session,
        )
        empty_node_metadata = await _run(
            db=db,
            branch_name=branches.default_branch.name,
            source=EMPTY_NODE_METADATA_ORDER_QUERY,
            variables=variables,
            account_session=reader_session,
        )

        assert omitted.errors is None
        assert empty_order.errors is None
        assert empty_node_metadata.errors is None
        assert _names(omitted) == [branches.default_branch.name, *branches.five[:4]]
        assert _names(empty_order) == _names(omitted)
        assert _names(empty_node_metadata) == _names(omitted)

    async def test_contradictory_order_is_rejected(
        self,
        db: InfrahubDatabase,
        repository_branch_status_branches: RepositoryBranchStatusBranches,
        repositories: tuple[CoreRepository, CoreReadOnlyRepository],
        reader_session: AccountSession,
        default_permission_backend: None,
    ) -> None:
        branches = repository_branch_status_branches
        repository, _ = repositories

        result = await _run(
            db=db,
            branch_name=branches.default_branch.name,
            source=CONTRADICTORY_ORDER_QUERY,
            variables={"id": repository.id, "limit": 5},
            account_session=reader_session,
        )

        assert result.data is None
        assert result.errors
        assert len(result.errors) == 1
        assert result.errors[0].message == "Only one of 'created_at' or 'updated_at' can be specified for ordering."

    async def test_name_filter_exact_and_partial(
        self,
        db: InfrahubDatabase,
        repository_branch_status_branches: RepositoryBranchStatusBranches,
        repositories: tuple[CoreRepository, CoreReadOnlyRepository],
        reader_session: AccountSession,
        default_permission_backend: None,
    ) -> None:
        branches = repository_branch_status_branches
        repository, _ = repositories

        exact = await _run(
            db=db,
            branch_name=branches.default_branch.name,
            source=ROWS_QUERY,
            variables={"id": repository.id, "limit": 1000, "name": branches.five[2]},
            account_session=reader_session,
        )
        assert exact.errors is None
        assert exact.data
        assert exact.data["InfrahubRepositoryBranchStatus"]["count"] == 1
        assert _names(exact) == [branches.five[2]]

        prefix_of_several_names = await _run(
            db=db,
            branch_name=branches.default_branch.name,
            source=ROWS_QUERY,
            variables={"id": repository.id, "limit": 1000, "name": "rbs-five-0"},
            account_session=reader_session,
        )
        assert prefix_of_several_names.errors is None
        assert prefix_of_several_names.data
        assert prefix_of_several_names.data["InfrahubRepositoryBranchStatus"]["count"] == 0
        assert _names(prefix_of_several_names) == []

        partial = await _run(
            db=db,
            branch_name=branches.default_branch.name,
            source=ROWS_QUERY,
            variables={"id": repository.id, "limit": 1000, "name": "rbs-five-", "partial_match": True},
            account_session=reader_session,
        )
        assert partial.errors is None
        assert partial.data
        assert partial.data["InfrahubRepositoryBranchStatus"]["count"] == 5
        assert _names(partial) == list(branches.five)

        no_match = await _run(
            db=db,
            branch_name=branches.default_branch.name,
            source=ROWS_QUERY,
            variables={"id": repository.id, "limit": 1000, "name": "rbs-does-not-exist"},
            account_session=reader_session,
        )
        assert no_match.errors is None
        assert no_match.data
        assert no_match.data["InfrahubRepositoryBranchStatus"]["count"] == 0
        assert _names(no_match) == []

    async def test_status_filter_including_a_terminal_status(
        self,
        db: InfrahubDatabase,
        repository_branch_status_branches: RepositoryBranchStatusBranches,
        repositories: tuple[CoreRepository, CoreReadOnlyRepository],
        reader_session: AccountSession,
        default_permission_backend: None,
    ) -> None:
        branches = repository_branch_status_branches
        repository, _ = repositories

        merge_failed = await _run(
            db=db,
            branch_name=branches.default_branch.name,
            source=ROWS_QUERY,
            variables={"id": repository.id, "limit": 1000, "status": BranchStatus.MERGE_FAILED.value},
            account_session=reader_session,
        )
        assert merge_failed.errors is None
        assert merge_failed.data
        assert merge_failed.data["InfrahubRepositoryBranchStatus"]["count"] == 1
        assert _names(merge_failed) == [branches.by_status[BranchStatus.MERGE_FAILED]]

        merged = await _run(
            db=db,
            branch_name=branches.default_branch.name,
            source=ROWS_QUERY,
            variables={"id": repository.id, "limit": 1000, "status": BranchStatus.MERGED.value},
            account_session=reader_session,
        )
        assert merged.errors is None
        assert merged.data
        assert merged.data["InfrahubRepositoryBranchStatus"]["count"] == 0
        assert _names(merged) == []

    async def test_repository_resolved_by_name(
        self,
        db: InfrahubDatabase,
        repository_branch_status_branches: RepositoryBranchStatusBranches,
        repositories: tuple[CoreRepository, CoreReadOnlyRepository],
        reader_session: AccountSession,
        default_permission_backend: None,
    ) -> None:
        branches = repository_branch_status_branches
        repository, _ = repositories

        by_name = await _run(
            db=db,
            branch_name=branches.default_branch.name,
            source=ROWS_QUERY,
            variables={"id": repository.name.value, "limit": 5},
            account_session=reader_session,
        )
        by_uuid = await _run(
            db=db,
            branch_name=branches.default_branch.name,
            source=ROWS_QUERY,
            variables={"id": repository.id, "limit": 5},
            account_session=reader_session,
        )

        assert by_name.errors is None
        assert by_name.data
        assert by_name.data == by_uuid.data

    async def test_unknown_repository_is_reported_as_not_found(
        self,
        db: InfrahubDatabase,
        repository_branch_status_branches: RepositoryBranchStatusBranches,
        repositories: tuple[CoreRepository, CoreReadOnlyRepository],
        reader_session: AccountSession,
        default_permission_backend: None,
    ) -> None:
        branches = repository_branch_status_branches

        result = await _run(
            db=db,
            branch_name=branches.default_branch.name,
            source=ROWS_QUERY,
            variables={"id": "rbs-no-such-repository", "limit": 5},
            account_session=reader_session,
        )

        assert result.data is None
        assert result.errors
        assert len(result.errors) == 1
        assert result.errors[0].message == (
            "Unable to find the node rbs-no-such-repository / CoreGenericRepository in the database."
        )

    @pytest.mark.parametrize("case", INVALID_PAGING_CASES, ids=lambda case: case.name)
    async def test_invalid_paging_arguments_are_rejected(
        self,
        db: InfrahubDatabase,
        repository_branch_status_branches: RepositoryBranchStatusBranches,
        repositories: tuple[CoreRepository, CoreReadOnlyRepository],
        reader_session: AccountSession,
        default_permission_backend: None,
        case: InvalidPagingCase,
    ) -> None:
        branches = repository_branch_status_branches
        repository, _ = repositories

        result = await _run(
            db=db,
            branch_name=branches.default_branch.name,
            source=ROWS_QUERY,
            variables={"id": repository.id, **case.variables},
            account_session=reader_session,
        )

        assert result.data is None
        assert result.errors
        assert len(result.errors) == 1
        assert result.errors[0].message == case.message

    async def test_ref_is_null_on_the_read_write_kind_and_set_on_the_read_only_kind(
        self,
        db: InfrahubDatabase,
        repository_branch_status_branches: RepositoryBranchStatusBranches,
        repositories: tuple[CoreRepository, CoreReadOnlyRepository],
        reader_session: AccountSession,
        default_permission_backend: None,
    ) -> None:
        branches = repository_branch_status_branches
        repository, read_only_repository = repositories
        variables: dict[str, Any] = {"limit": 1000, "name": "rbs-five-", "partial_match": True}

        read_write = await _run(
            db=db,
            branch_name=branches.default_branch.name,
            source=REF_QUERY,
            variables={"id": repository.id, **variables},
            account_session=reader_session,
        )
        read_only = await _run(
            db=db,
            branch_name=branches.default_branch.name,
            source=REF_QUERY,
            variables={"id": read_only_repository.id, **variables},
            account_session=reader_session,
        )

        assert read_write.errors is None
        assert read_only.errors is None
        assert [node["ref"] for node in _nodes(read_write)] == [None] * 5
        assert [node["ref"]["value"] for node in _nodes(read_only)] == ["main"] * 5
        assert all(node["commit"]["value"] for node in _nodes(read_write))

    async def test_dropdown_payload_carries_the_schema_label_and_colour(
        self,
        db: InfrahubDatabase,
        repository_branch_status_branches: RepositoryBranchStatusBranches,
        repositories: tuple[CoreRepository, CoreReadOnlyRepository],
        reader_session: AccountSession,
        default_permission_backend: None,
    ) -> None:
        branches = repository_branch_status_branches
        repository, _ = repositories

        result = await _run(
            db=db,
            branch_name=branches.default_branch.name,
            source=ROWS_QUERY,
            variables={"id": repository.id, "limit": 1000, "name": branches.default_branch.name},
            account_session=reader_session,
        )

        assert result.errors is None
        node = _nodes(result)[0]
        assert node["sync_status"]["value"] in {status.value for status in RepositorySyncStatus}
        assert node["sync_status"]["label"]
        assert node["sync_status"]["color"].startswith("#")
        assert node["internal_status"]["value"] == "active"

    async def test_updated_at_is_returned_as_a_timestamp(
        self,
        db: InfrahubDatabase,
        repository_branch_status_branches: RepositoryBranchStatusBranches,
        repositories: tuple[CoreRepository, CoreReadOnlyRepository],
        reader_session: AccountSession,
        default_permission_backend: None,
    ) -> None:
        branches = repository_branch_status_branches
        repository, _ = repositories

        result = await _run(
            db=db,
            branch_name=branches.default_branch.name,
            source=UPDATED_AT_QUERY,
            variables={"id": repository.id, "limit": 5, "name": branches.default_branch.name},
            account_session=reader_session,
        )

        assert result.errors is None
        assert len(_nodes(result)) == 1
        node = _nodes(result)[0]
        assert node["commit"]["updated_at"] == EXPECTED_UPDATED_AT
        assert node["sync_status"]["updated_at"] == EXPECTED_UPDATED_AT
        assert node["internal_status"]["updated_at"] == EXPECTED_UPDATED_AT
        assert node["commit"]["value"]

    async def test_two_calls_return_identical_values(
        self,
        db: InfrahubDatabase,
        repository_branch_status_branches: RepositoryBranchStatusBranches,
        repositories: tuple[CoreRepository, CoreReadOnlyRepository],
        reader_session: AccountSession,
        default_permission_backend: None,
    ) -> None:
        branches = repository_branch_status_branches
        repository, _ = repositories
        variables: dict[str, Any] = {"id": repository.id, "limit": 20}

        first = await _run(
            db=db,
            branch_name=branches.default_branch.name,
            source=ROWS_QUERY,
            variables=variables,
            account_session=reader_session,
        )
        second = await _run(
            db=db,
            branch_name=branches.default_branch.name,
            source=ROWS_QUERY,
            variables=variables,
            account_session=reader_session,
        )

        assert first.errors is None
        assert second.errors is None
        assert first.data == second.data

    async def test_field_description_announces_the_placeholder_values(
        self,
        db: InfrahubDatabase,
        repository_branch_status_branches: RepositoryBranchStatusBranches,
        default_permission_backend: None,
    ) -> None:
        branches = repository_branch_status_branches

        gql_params = await prepare_graphql_params(db=db, branch=branches.default_branch.name)

        query_type = gql_params.schema.query_type
        assert query_type
        description = query_type.fields["InfrahubRepositoryBranchStatus"].description
        assert description
        assert "preview" in description


class TestRepositoryBranchStatusPermissions:
    @pytest.mark.parametrize("grant", PERMISSION_GRANTS, ids=lambda grant: grant.name)
    @pytest.mark.parametrize("on_default_branch", [True, False], ids=["default-branch", "user-branch"])
    async def test_view_permission_matrix(
        self,
        db: InfrahubDatabase,
        repository_branch_status_branches: RepositoryBranchStatusBranches,
        repositories: tuple[CoreRepository, CoreReadOnlyRepository],
        matrix_sessions: Mapping[str, AccountSession],
        default_permission_backend: None,
        grant: PermissionGrant,
        on_default_branch: bool,
    ) -> None:
        branches = repository_branch_status_branches
        repository, _ = repositories
        branch_name = branches.default_branch.name if on_default_branch else branches.query_branch_name

        result = await _run(
            db=db,
            branch_name=branch_name,
            source=NAMES_ONLY_QUERY,
            variables={"id": repository.id, "limit": 5},
            account_session=matrix_sessions[grant.name],
        )

        if grant.allowed:
            assert result.errors is None
            assert _names(result) == [branches.default_branch.name, *branches.five[:4]]
            return

        assert result.data is None
        assert result.errors
        assert len(result.errors) == 1
        assert result.errors[0].message == DENIAL_MESSAGE

    @pytest.mark.parametrize("case", SINGLE_KIND_CASES, ids=lambda case: case.name)
    @pytest.mark.parametrize("on_default_branch", [True, False], ids=["default-branch", "user-branch"])
    async def test_a_grant_on_one_kind_does_not_cover_the_other_kind(
        self,
        db: InfrahubDatabase,
        repository_branch_status_branches: RepositoryBranchStatusBranches,
        repositories: tuple[CoreRepository, CoreReadOnlyRepository],
        single_kind_sessions: Mapping[str, AccountSession],
        default_permission_backend: None,
        case: SingleKindCase,
        on_default_branch: bool,
    ) -> None:
        branches = repository_branch_status_branches
        repository = repositories[1] if case.query_read_only_repository else repositories[0]
        branch_name = branches.default_branch.name if on_default_branch else branches.query_branch_name

        result = await _run(
            db=db,
            branch_name=branch_name,
            source=NAMES_ONLY_QUERY,
            variables={"id": repository.id, "limit": 5},
            account_session=single_kind_sessions[case.granted_kind_name],
        )

        if case.denial_message is None:
            assert result.errors is None
            assert _names(result) == [branches.default_branch.name, *branches.five[:4]]
            return

        assert result.data is None
        assert result.errors
        assert len(result.errors) == 1
        assert result.errors[0].message == case.denial_message

    @pytest.mark.parametrize("on_default_branch", [True, False], ids=["default-branch", "user-branch"])
    async def test_denial_runs_no_database_query(
        self,
        db: InfrahubDatabase,
        repository_branch_status_branches: RepositoryBranchStatusBranches,
        repositories: tuple[CoreRepository, CoreReadOnlyRepository],
        matrix_sessions: Mapping[str, AccountSession],
        reader_session: AccountSession,
        default_permission_backend: None,
        on_default_branch: bool,
    ) -> None:
        branches = repository_branch_status_branches
        repository, _ = repositories
        branch_name = branches.default_branch.name if on_default_branch else branches.query_branch_name

        gql_params = await prepare_graphql_params(
            db=db, branch=branch_name, account_session=matrix_sessions["no-grant"]
        )
        counting_db = CountingInfrahubDatabase.from_db(db=db)
        gql_params.context.db = counting_db

        result = await graphql(
            schema=gql_params.schema,
            source=NAMES_ONLY_QUERY,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"id": repository.id, "limit": 5},
        )

        assert result.data is None
        assert result.errors
        assert result.errors[0].message == DENIAL_MESSAGE
        assert sum(counting_db.query_counts.values()) == 0

        # The same counter behind an allowed caller must move, so the zero above cannot be a
        # counter that never saw the resolver.
        allowed_params = await prepare_graphql_params(db=db, branch=branch_name, account_session=reader_session)
        allowed_params.context.db = counting_db

        allowed_result = await graphql(
            schema=allowed_params.schema,
            source=NAMES_ONLY_QUERY,
            context_value=allowed_params.context,
            root_value=None,
            variable_values={"id": repository.id, "limit": 5},
        )

        assert allowed_result.errors is None
        assert _names(allowed_result) == [branches.default_branch.name, *branches.five[:4]]
        assert sum(counting_db.query_counts.values()) > 0

    @pytest.mark.parametrize("on_default_branch", [True, False], ids=["default-branch", "user-branch"])
    async def test_anonymous_session_with_a_granted_role_returns_rows(
        self,
        db: InfrahubDatabase,
        repository_branch_status_branches: RepositoryBranchStatusBranches,
        repositories: tuple[CoreRepository, CoreReadOnlyRepository],
        default_permission_backend: None,
        anonymous_access_granted: None,
        on_default_branch: bool,
    ) -> None:
        branches = repository_branch_status_branches
        repository, _ = repositories
        branch_name = branches.default_branch.name if on_default_branch else branches.query_branch_name

        result = await _run(
            db=db,
            branch_name=branch_name,
            source=NAMES_ONLY_QUERY,
            variables={"id": repository.id, "limit": 5},
            account_session=AnonymousSession(),
        )

        assert result.errors is None
        assert _names(result) == [branches.default_branch.name, *branches.five[:4]]

    @pytest.mark.parametrize("on_default_branch", [True, False], ids=["default-branch", "user-branch"])
    async def test_anonymous_session_without_a_grant_is_denied(
        self,
        db: InfrahubDatabase,
        repository_branch_status_branches: RepositoryBranchStatusBranches,
        repositories: tuple[CoreRepository, CoreReadOnlyRepository],
        default_permission_backend: None,
        anonymous_access_without_a_role: None,
        on_default_branch: bool,
    ) -> None:
        branches = repository_branch_status_branches
        repository, _ = repositories
        branch_name = branches.default_branch.name if on_default_branch else branches.query_branch_name

        result = await _run(
            db=db,
            branch_name=branch_name,
            source=NAMES_ONLY_QUERY,
            variables={"id": repository.id, "limit": 5},
            account_session=AnonymousSession(),
        )

        assert result.data is None
        assert result.errors
        assert len(result.errors) == 1
        assert result.errors[0].message == DENIAL_MESSAGE

    @pytest.mark.parametrize("on_default_branch", [True, False], ids=["default-branch", "user-branch"])
    async def test_context_without_loaded_permissions_is_denied(
        self,
        db: InfrahubDatabase,
        repository_branch_status_branches: RepositoryBranchStatusBranches,
        repositories: tuple[CoreRepository, CoreReadOnlyRepository],
        default_permission_backend: None,
        on_default_branch: bool,
    ) -> None:
        """A request carrying no permission manager is a denial, never an initialization failure."""
        branches = repository_branch_status_branches
        repository, _ = repositories
        branch_name = branches.default_branch.name if on_default_branch else branches.query_branch_name

        result = await _run(
            db=db,
            branch_name=branch_name,
            source=NAMES_ONLY_QUERY,
            variables={"id": repository.id, "limit": 5},
        )

        assert result.data is None
        assert result.errors
        assert len(result.errors) == 1
        assert result.errors[0].message == "The requested operation was not authorized"


FILTERED_ROWS_QUERY = """
query(
    $id: String!
    $limit: Int
    $name: String
    $partial_match: Boolean
    $status: BranchStatus
    $sync_status: String
    $internal_status: String
    $own_values_only: Boolean
) {
  InfrahubRepositoryBranchStatus(
    id: $id
    limit: $limit
    name__value: $name
    partial_match: $partial_match
    status__value: $status
    sync_status__value: $sync_status
    internal_status__value: $internal_status
    own_values_only: $own_values_only
  ) {
    edges {
      node { name commit { value } }
    }
  }
}
"""


@dataclass(frozen=True)
class DocumentShape:
    """One supported document shape, used to prove none of them reaches the message bus."""

    name: str
    """Identifier of the shape, also used as the pytest id."""

    source: str
    """GraphQL document."""

    variables: Mapping[str, Any]
    """Query variables, excluding the repository id."""


DOCUMENT_SHAPES = (
    DocumentShape(name="count-and-values", source=ROWS_QUERY, variables={"limit": 5}),
    DocumentShape(name="no-count", source=NAMES_ONLY_QUERY, variables={"limit": 5}),
    DocumentShape(name="ref", source=REF_QUERY, variables={"limit": 5}),
    DocumentShape(name="order", source=ORDERED_ROWS_QUERY, variables={"limit": 5, "direction": "ASC"}),
    DocumentShape(
        name="name-filter",
        source=FILTERED_ROWS_QUERY,
        variables={"limit": 5, "name": "rbs-five-", "partial_match": True},
    ),
    DocumentShape(
        name="status-filter", source=FILTERED_ROWS_QUERY, variables={"limit": 5, "status": BranchStatus.OPEN.value}
    ),
    DocumentShape(
        name="sync-status-filter",
        source=FILTERED_ROWS_QUERY,
        variables={"limit": 5, "sync_status": RepositorySyncStatus.IN_SYNC.value},
    ),
    DocumentShape(
        name="internal-status-filter",
        source=FILTERED_ROWS_QUERY,
        variables={"limit": 5, "internal_status": RepositoryInternalStatus.ACTIVE.value},
    ),
    DocumentShape(name="own-values-only", source=FILTERED_ROWS_QUERY, variables={"limit": 5, "own_values_only": True}),
)


class TestRepositoryBranchStatusSendsNoMessage:
    @pytest.mark.parametrize("shape", DOCUMENT_SHAPES, ids=lambda shape: shape.name)
    @pytest.mark.parametrize("read_only", [False, True], ids=["read-write-kind", "read-only-kind"])
    async def test_no_message_is_published(
        self,
        db: InfrahubDatabase,
        repository_branch_status_branches: RepositoryBranchStatusBranches,
        repositories: tuple[CoreRepository, CoreReadOnlyRepository],
        reader_session: AccountSession,
        default_permission_backend: None,
        recording_bus: RecordingBus,
        shape: DocumentShape,
        read_only: bool,
    ) -> None:
        branches = repository_branch_status_branches
        repository = repositories[1] if read_only else repositories[0]

        result = await _run(
            db=db,
            branch_name=branches.default_branch.name,
            source=shape.source,
            variables={"id": repository.id, **shape.variables},
            account_session=reader_session,
            service=recording_bus.service,
        )

        assert result.errors is None
        assert result.data
        assert recording_bus.recorder.messages == []
