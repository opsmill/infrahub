from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
from prefect.client.orchestration import PrefectClient, get_client

from infrahub.core.branch import Branch
from infrahub.events.branch_action import BranchDeletedEvent, BranchRebasedEvent
from infrahub.events.models import EventMeta
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.events import dummy_event_meta
from tests.helpers.graphql import graphql
from tests.helpers.task_manager_seed import seed_infrahub_event

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from infrahub.auth.session import AccountSession
    from infrahub.database import InfrahubDatabase

QUERY_EVENT_IDS = """
query($ids: [String!], $parent__ids: [String!], $branch: [String!], $since: DateTime) {
  InfrahubEvent(ids: $ids, parent__ids: $parent__ids, branches: $branch, since: $since) {
    edges {
      node {
        id
      }
    }
  }
}
"""

# Older than the 180 days that a query with no start reads on a test server with a 7-day event retention.
OLDER_THAN_DEFAULT_RANGE = timedelta(days=200)

_TEST_ID = uuid.uuid4().hex[:8]


@pytest.fixture(scope="module")
async def prefect_client(prefect_test_fixture: None) -> AsyncGenerator[PrefectClient, None]:
    async with get_client(sync_client=False) as client:
        yield client


async def _event_ids(
    db: InfrahubDatabase, branch: Branch, account_session: AccountSession, variables: dict[str, Any]
) -> list[str]:
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch, account_session=account_session)
    result = await graphql(
        schema=gql_params.schema,
        source=QUERY_EVENT_IDS,
        context_value=gql_params.context,
        root_value=None,
        variable_values=variables,
    )
    assert result.errors is None
    assert result.data
    return [edge["node"]["id"] for edge in result.data["InfrahubEvent"]["edges"]]


def _rebased(branch: Branch, meta: EventMeta | None = None) -> BranchRebasedEvent:
    return BranchRebasedEvent(
        branch_name=branch.name, branch_id=str(branch.get_uuid()), meta=meta or dummy_event_meta(branch=branch)
    )


async def test_an_event_older_than_the_default_range_is_found_by_its_id_and_by_its_parent(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    prefect_client: PrefectClient,
    session_admin: AccountSession,
) -> None:
    """A query by event ID or by parent ID with no start returns an event however old it is."""
    occurred = datetime.now(UTC) - OLDER_THAN_DEFAULT_RANGE
    branch = Branch(uuid=uuid.uuid4(), name=f"old-{_TEST_ID}")
    parent = _rebased(branch=branch)
    child = _rebased(branch=branch, meta=EventMeta.from_parent(parent))
    await seed_infrahub_event(event=parent, occurred=occurred)
    await seed_infrahub_event(event=child, occurred=occurred)

    by_id = await _event_ids(
        db=db, branch=default_branch, account_session=session_admin, variables={"ids": [parent.get_id()]}
    )
    by_parent = await _event_ids(
        db=db, branch=default_branch, account_session=session_admin, variables={"parent__ids": [parent.get_id()]}
    )

    assert by_id == [parent.get_id()]
    assert by_parent == [child.get_id()]


async def test_a_branch_name_resolves_through_a_deletion_older_than_the_default_range(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    prefect_client: PrefectClient,
    session_admin: AccountSession,
) -> None:
    """A name no current branch has resolves through its deletion however old it is, when the range starts before it."""
    now = datetime.now(UTC)
    deleted_branch = Branch(uuid=uuid.uuid4(), name=f"deleted-long-ago-{_TEST_ID}")
    rebased = _rebased(branch=deleted_branch)
    deleted = BranchDeletedEvent(
        branch_name=deleted_branch.name,
        branch_id=str(deleted_branch.get_uuid()),
        sync_with_git=False,
        meta=dummy_event_meta(branch=default_branch),
    )
    await seed_infrahub_event(event=rebased, occurred=now - OLDER_THAN_DEFAULT_RANGE - timedelta(days=10))
    await seed_infrahub_event(event=deleted, occurred=now - OLDER_THAN_DEFAULT_RANGE)

    event_ids = await _event_ids(
        db=db,
        branch=default_branch,
        account_session=session_admin,
        variables={"branch": [deleted_branch.name], "since": (now - timedelta(days=300)).isoformat()},
    )

    assert event_ids == [rebased.get_id()]
