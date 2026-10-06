from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from graphql import GraphQLInputObjectType, GraphQLObjectType

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.core.constants import AccountType, InfrahubKind, RepositoryDeliveryStatus
from infrahub.core.node import Node
from infrahub.events.node_action import NodeUpdatedEvent
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices
from infrahub.workers.dependencies import build_event_service
from tests.adapters.event import MemoryInfrahubEvent
from tests.helpers.dependency_override import override_dependency
from tests.helpers.graphql import graphql

from .conftest import DELIVERY_ATTRIBUTES, pending_merge

if TYPE_CHECKING:
    from fast_depends import Provider

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

    from .conftest import StoreUnderTest

REPOSITORY_UPDATE = """
mutation ($id: String!, $description: String!) {
    CoreRepositoryUpdate(data: {id: $id, description: {value: $description}}) {
        ok
    }
}
"""


@pytest.mark.parametrize(
    "input_name", ["CoreRepositoryCreateInput", "CoreRepositoryUpdateInput", "CoreRepositoryUpsertInput"]
)
async def test_the_repository_mutation_inputs_leave_out_every_delivery_attribute(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, input_name: str
) -> None:
    default_branch.update_schema_hash()
    schema = (await prepare_graphql_params(db=db, branch=default_branch)).schema
    repository_type = schema.get_type("CoreRepository")
    repository_input = schema.get_type(input_name)
    assert isinstance(repository_type, GraphQLObjectType)
    assert isinstance(repository_input, GraphQLInputObjectType)

    assert set(DELIVERY_ATTRIBUTES) <= repository_type.fields.keys()
    assert repository_input.fields.keys() & set(DELIVERY_ATTRIBUTES) == set()
    assert {"name", "location", "commit"} <= repository_input.fields.keys()


async def test_a_store_transition_emits_no_node_mutation_event_unlike_a_repository_update(
    db: InfrahubDatabase, default_branch: Branch, subject: StoreUnderTest, dependency_provider: Provider
) -> None:
    account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT, branch=default_branch)
    await account.new(db=db, name="repository-editor", account_type=AccountType.USER.value, password="Editor-123")
    await account.save(db=db)
    recorder = MemoryInfrahubEvent()

    with override_dependency(build_event_service, lambda: recorder, dependency_provider=dependency_provider):
        await subject.store.enqueue(repository_id=subject.repository_id, entry=pending_merge("e1"), widen=False)
        events_of_the_transition = list(recorder.events)

        default_branch.update_schema_hash()
        params = await prepare_graphql_params(
            db=db,
            branch=default_branch,
            service=await InfrahubServices.new(event=recorder),
            account_session=AccountSession(authenticated=True, auth_type=AuthType.API, account_id=account.id),
        )
        result = await graphql(
            schema=params.schema,
            source=REPOSITORY_UPDATE,
            context_value=params.context,
            root_value=None,
            variable_values={"id": subject.repository_id, "description": "Edited by a user"},
        )
        background_tasks = params.context.background
        assert background_tasks is not None
        await background_tasks()

    assert (await subject.read()).status == RepositoryDeliveryStatus.PENDING
    assert events_of_the_transition == []
    assert result.errors is None
    assert [type(event) for event in recorder.events] == [NodeUpdatedEvent]
    assert [event.node_id for event in recorder.events if isinstance(event, NodeUpdatedEvent)] == [
        subject.repository_id
    ]
