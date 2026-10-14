from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.auth.session import AccountSession
from infrahub.core.account import GlobalPermission, ObjectPermission
from infrahub.core.branch import Branch
from infrahub.core.constants import GlobalPermissions, InfrahubKind, PermissionAction, PermissionDecision
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from tests.helpers.number_pool import add_pool_range, create_range_only_pool
from tests.helpers.permissions import define_permissions
from tests.helpers.schema import TICKET, load_schema

from .helpers import CREATE_NUMBER_POOL_WITH_BOUNDS, execute, range_details, ticket_pool_input

UPDATE_NUMBER_POOL = """
mutation UpdateNumberPool($data: CoreNumberPoolUpdateInput!) {
  CoreNumberPoolUpdate(data: $data) {
    ok
  }
}
"""

RANGE_ACTIONS = (PermissionAction.CREATE, PermissionAction.UPDATE, PermissionAction.DELETE)


def _range_denied_message(action: PermissionAction) -> str:
    return f"You do not have the following permission: object:Core:NumberPoolRange:{action.value}:allow_default"


@dataclass
class RangePermissionCase:
    name: str
    stored_ranges: list[tuple[int, int]]
    declared_ranges: list[dict[str, int]]
    denied_action: PermissionAction
    expected_ranges: list[tuple[int, int, int | None]]


RANGE_PERMISSION_CASES: list[RangePermissionCase] = [
    RangePermissionCase(
        name="create",
        stored_ranges=[(1, 10)],
        declared_ranges=[{"start": 1, "end": 10}, {"start": 20, "end": 30}],
        denied_action=PermissionAction.CREATE,
        expected_ranges=[(1, 10, None), (20, 30, None)],
    ),
    RangePermissionCase(
        name="update",
        stored_ranges=[(1, 10)],
        declared_ranges=[{"start": 1, "end": 10, "allocation_weight": 5}],
        denied_action=PermissionAction.UPDATE,
        expected_ranges=[(1, 10, 5)],
    ),
    RangePermissionCase(
        name="delete",
        stored_ranges=[(1, 10), (20, 30)],
        declared_ranges=[{"start": 1, "end": 10}],
        denied_action=PermissionAction.DELETE,
        expected_ranges=[(1, 10, None)],
    ),
]


async def _grant(account: Node, db: InfrahubDatabase, range_actions: tuple[PermissionAction, ...]) -> None:
    """Let the account write number pools and apply only the given actions to their ranges."""
    await define_permissions(
        account=account,
        db=db,
        global_permissions=[
            GlobalPermission(
                action=GlobalPermissions.EDIT_DEFAULT_BRANCH.value, decision=PermissionDecision.ALLOW_ALL.value
            )
        ],
        object_permissions=[
            ObjectPermission(
                namespace="Core",
                name="NumberPool",
                action=PermissionAction.ANY.value,
                decision=PermissionDecision.ALLOW_ALL.value,
            ),
            *[
                ObjectPermission(
                    namespace="Core",
                    name="NumberPoolRange",
                    action=action.value,
                    decision=PermissionDecision.ALLOW_ALL.value,
                )
                for action in range_actions
            ],
        ],
    )


async def _execute_as(
    db: InfrahubDatabase, branch: Branch, session: AccountSession, source: str, variables: dict[str, Any]
) -> list[str]:
    result = await execute(db=db, branch=branch, source=source, variables=variables, account_session=session)
    return [error.message for error in result.errors or []]


@pytest.fixture
async def ticket_schema(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    default_branch.update_schema_hash()


@pytest.mark.parametrize("case", RANGE_PERMISSION_CASES, ids=lambda case: case.name)
async def test_pool_update_needs_the_range_permission_for_each_range_write(
    db: InfrahubDatabase,
    default_branch: Branch,
    ticket_schema: None,
    default_permission_backend: None,
    first_account: Node,
    session_first_account: AccountSession,
    case: RangePermissionCase,
) -> None:
    pool = await create_range_only_pool(db=db)
    for start, end in case.stored_ranges:
        await add_pool_range(db=db, pool=pool, start=start, end=end)
    ranges_before = await range_details(db=db, pool_id=pool.get_id())
    await _grant(
        account=first_account,
        db=db,
        range_actions=tuple(action for action in RANGE_ACTIONS if action != case.denied_action),
    )

    errors = await _execute_as(
        db=db,
        branch=default_branch,
        session=session_first_account,
        source=UPDATE_NUMBER_POOL,
        variables={"data": {"id": pool.get_id(), "ranges": case.declared_ranges}},
    )

    assert errors == [_range_denied_message(action=case.denied_action)]
    assert await range_details(db=db, pool_id=pool.get_id()) == ranges_before

    await define_permissions(
        account=first_account,
        db=db,
        object_permissions=[
            ObjectPermission(
                namespace="Core",
                name="NumberPoolRange",
                action=case.denied_action.value,
                decision=PermissionDecision.ALLOW_ALL.value,
            )
        ],
        role_name="range-writer",
        group_name="range-writers",
    )
    errors = await _execute_as(
        db=db,
        branch=default_branch,
        session=session_first_account,
        source=UPDATE_NUMBER_POOL,
        variables={"data": {"id": pool.get_id(), "ranges": case.declared_ranges}},
    )

    assert errors == []
    assert [item[1:] for item in await range_details(db=db, pool_id=pool.get_id())] == case.expected_ranges


async def test_pool_update_with_every_range_permission_writes_the_ranges(
    db: InfrahubDatabase,
    default_branch: Branch,
    ticket_schema: None,
    default_permission_backend: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    pool = await create_range_only_pool(db=db)
    await add_pool_range(db=db, pool=pool, start=1, end=10)
    await add_pool_range(db=db, pool=pool, start=20, end=30)
    await _grant(account=first_account, db=db, range_actions=RANGE_ACTIONS)

    errors = await _execute_as(
        db=db,
        branch=default_branch,
        session=session_first_account,
        source=UPDATE_NUMBER_POOL,
        variables={"data": {"id": pool.get_id(), "ranges": [{"start": 1, "end": 15}, {"start": 40, "end": 50}]}},
    )

    assert errors == []
    assert [item[1:] for item in await range_details(db=db, pool_id=pool.get_id())] == [
        (1, 15, None),
        (40, 50, None),
    ]


async def test_pool_creation_with_ranges_needs_the_range_create_permission(
    db: InfrahubDatabase,
    default_branch: Branch,
    ticket_schema: None,
    default_permission_backend: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    await _grant(account=first_account, db=db, range_actions=(PermissionAction.UPDATE, PermissionAction.DELETE))

    errors = await _execute_as(
        db=db,
        branch=default_branch,
        session=session_first_account,
        source=CREATE_NUMBER_POOL_WITH_BOUNDS,
        variables={"data": ticket_pool_input(name="denied-ranges-pool", bounds={"ranges": [{"start": 1, "end": 9}]})},
    )

    assert errors == [_range_denied_message(action=PermissionAction.CREATE)]
    assert await NodeManager.count(db=db, schema=InfrahubKind.NUMBERPOOL, branch=default_branch) == 0
