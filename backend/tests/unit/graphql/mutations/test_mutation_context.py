from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase
from infrahub.events.node_action import NodeMutatedEvent
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices
from tests.adapters.event import MemoryInfrahubEvent
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase


async def test_add_context_invalid_account(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: None,
    first_account: Node,
):
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
    gql_params = await prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
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
    car_person_schema: None,
    enable_broker_config: None,
    session_first_account: AccountSession,
    first_account: Node,
    second_account: Node,
):
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
    gql_params = await prepare_graphql_params(
        db=db, include_subscription=False, branch=default_branch, service=service, account_session=session_first_account
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
