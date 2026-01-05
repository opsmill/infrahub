from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.auth import AccountSession
from infrahub.core.account import GlobalPermission
from infrahub.core.branch import Branch
from infrahub.core.constants import GlobalPermissions, PermissionDecision
from infrahub.database import InfrahubDatabase
from infrahub.events.node_action import NodeMutatedEvent
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices
from tests.adapters.event import MemoryInfrahubEvent
from tests.helpers.graphql import graphql
from tests.helpers.permissions import define_permissions

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase


async def test_add_context_invalid_account(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    car_person_schema: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    await define_permissions(
        account=first_account,
        db=db,
        global_permissions=[
            GlobalPermission(
                action=GlobalPermissions.OVERRIDE_CONTEXT.value,
                decision=PermissionDecision.ALLOW_ALL.value,
            ),
        ],
    )

    query = """
    mutation {
        TestPersonCreate(data: {name: { value: "John"}, height: {value: 182}}, context: { account: { id: "very-invalid" }}) {
            ok
            object {
                id
            }
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch, account_session=session_first_account)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert result.errors
    assert result.errors[0].message == "Unable to set context for account that doesn't exist"


async def test_add_context_valid_account(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    car_person_schema: None,
    enable_broker_config: None,
    session_first_account: AccountSession,
    first_account: Node,
    second_account: Node,
) -> None:
    await define_permissions(
        account=first_account,
        db=db,
        global_permissions=[
            GlobalPermission(
                action=GlobalPermissions.OVERRIDE_CONTEXT.value,
                decision=PermissionDecision.ALLOW_ALL.value,
            ),
        ],
    )

    query = """
    mutation {
        TestPersonCreate(data: {name: { value: "John"}, height: {value: 182}}, context: { account: { id: "%s" }}) {
            ok
            object {
                id
            }
        }
    }
    """ % (second_account.id)

    memory_event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=memory_event)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=default_branch, service=service, account_session=session_first_account
    )
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert gql_params.context.background
    await gql_params.context.background()

    assert len(memory_event.events) == 1
    node_event = memory_event.events[0]
    assert isinstance(node_event, NodeMutatedEvent)
    assert node_event.meta.account_id == second_account.id


async def test_add_context_missing_permissions(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    car_person_schema: None,
    session_second_account: AccountSession,
    first_account: Node,
    second_account: Node,
) -> None:
    query = """
    mutation {
        TestPersonCreate(data: {name: { value: "John"}, height: {value: 182}}, context: { account: { id: "%s" }}) {
            ok
            object {
                id
            }
        }
    }
    """ % (first_account.id)

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db,
        branch=default_branch,
        account_session=session_second_account,
    )
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert result.errors
    assert "You do not have the following permission: global:override_context:allow_default" in str(result.errors)
