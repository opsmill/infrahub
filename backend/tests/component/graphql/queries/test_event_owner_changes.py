from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from tests.adapters.event import MemoryInfrahubEvent
from tests.helpers.events import send_events
from tests.helpers.graphql import graphql
from tests.helpers.ownership import add_node
from tests.helpers.schema.ownership import OWNERSHIP_SCHEMA

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient

    from infrahub.auth.session import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from infrahub.events import InfrahubEvent

SET_OWNERS = """
mutation($id: String!, $owners: [MetadataNodeInput!]) {
    TestTenantUpdate(data: {id: $id, node_metadata: {owners: $owners}}) { ok }
}
"""

QUERY_CHANGES = """
query($ids: [String!]) {
    InfrahubEvent(primary_node__ids: $ids) {
        edges {
            node {
                id
                ... on NodeMutatedEvent {
                    payload
                    attributes { action kind name value value_previous }
                }
            }
        }
    }
}
"""


async def set_owners(
    db: InfrahubDatabase, branch: Branch, session: AccountSession, node_id: str, owner_ids: list[str]
) -> list[InfrahubEvent]:
    """Change the owners of a tenant through its update mutation, and return the events that the mutation sends."""
    event_service = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=event_service, workflow=WorkflowLocalExecution())
    gql_params = await prepare_graphql_params(db=db, branch=branch, service=service, account_session=session)
    result = await graphql(
        schema=gql_params.schema,
        source=SET_OWNERS,
        context_value=gql_params.context,
        variable_values={"id": node_id, "owners": [{"id": owner_id} for owner_id in owner_ids]},
    )
    assert result.errors is None, result.errors
    assert gql_params.context.background
    await gql_params.context.background()
    return event_service.events


async def read_changes(
    db: InfrahubDatabase, branch: Branch, session: AccountSession, node_id: str
) -> dict[str, dict[str, Any]]:
    """Return the activity log entries of a node, by event ID."""
    gql_params = await prepare_graphql_params(db=db, branch=branch, account_session=session)
    result = await graphql(
        schema=gql_params.schema,
        source=QUERY_CHANGES,
        context_value=gql_params.context,
        variable_values={"ids": [node_id]},
    )
    assert result.errors is None, result.errors
    assert result.data
    return {edge["node"]["id"]: edge["node"] for edge in result.data["InfrahubEvent"]["edges"]}


async def test_activity_log_shows_the_display_labels_that_the_owners_have_when_the_log_is_read(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    session_admin: AccountSession,
    prefect_client: PrefectClient,
) -> None:
    registry.schema.register_schema(schema=OWNERSHIP_SCHEMA, branch=default_branch.name)
    default_branch.update_schema_hash()
    emea = await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="dc-emea")
    network = await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="network-emea")
    tenant = await add_node(db=db, kind="TestTenant", name="tenant-log")
    # The changelog lists the owner IDs in this order, and the log keeps it.
    first, second = sorted([emea, network], key=lambda group: group.id)

    set_events = await set_owners(
        db=db, branch=default_branch, session=session_admin, node_id=tenant.id, owner_ids=[emea.id, network.id]
    )
    removed_events = await set_owners(
        db=db, branch=default_branch, session=session_admin, node_id=tenant.id, owner_ids=[]
    )
    await send_events(client=prefect_client, events=set_events + removed_events)
    set_id, removed_id = str(set_events[0].meta.id), str(removed_events[0].meta.id)

    changes = await read_changes(db=db, branch=default_branch, session=session_admin, node_id=tenant.id)

    labels = f"{first.name.value}, {second.name.value}"
    assert {event_id: change["attributes"] for event_id, change in changes.items()} == {
        set_id: [
            {
                "action": "ADDED",
                "kind": "List",
                "name": "node_metadata__owners",
                "value": labels,
                "value_previous": None,
            }
        ],
        removed_id: [
            {
                "action": "UPDATED",
                "kind": "List",
                "name": "node_metadata__owners",
                "value": "",
                "value_previous": labels,
            }
        ],
    }
    stored = changes[set_id]["payload"]["data"]["changelog"]["attributes"]["node_metadata__owners"]
    assert (stored["value"], stored["value_previous"]) == (f'["{first.id}","{second.id}"]', None)

    group = await NodeManager.get_one(db=db, id=emea.id, raise_on_error=True)
    group.name.value = "dc-europe"
    await group.save(db=db)
    await network.delete(db=db)

    changes = await read_changes(db=db, branch=default_branch, session=session_admin, node_id=tenant.id)

    renamed = {emea.id: "dc-europe", network.id: "deleted owner"}
    labels = f"{renamed[first.id]}, {renamed[second.id]}"
    assert changes[set_id]["attributes"][0]["value"] == labels
    assert changes[removed_id]["attributes"][0]["value_previous"] == labels
    stored = changes[set_id]["payload"]["data"]["changelog"]["attributes"]["node_metadata__owners"]
    assert stored["value"] == f'["{first.id}","{second.id}"]'


async def test_activity_log_shows_the_display_labels_of_the_owners_of_an_attribute(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    session_admin: AccountSession,
    prefect_client: PrefectClient,
) -> None:
    registry.schema.register_schema(schema=OWNERSHIP_SCHEMA, branch=default_branch.name)
    default_branch.update_schema_hash()
    emea = await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="dc-emea")
    network = await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="network-emea")
    tenant = await add_node(db=db, kind="TestTenant", name="tenant-log")
    first, second = sorted([emea, network], key=lambda group: group.id)

    event_service = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=event_service, workflow=WorkflowLocalExecution())
    gql_params = await prepare_graphql_params(
        db=db, branch=default_branch, service=service, account_session=session_admin
    )
    result = await graphql(
        schema=gql_params.schema,
        source="""
        mutation($id: String!, $owners: [MetadataNodeInput!]) {
            TestTenantUpdate(data: {id: $id, name: {owners: $owners}}) { ok }
        }
        """,
        context_value=gql_params.context,
        variable_values={"id": tenant.id, "owners": [{"id": emea.id}, {"id": network.id}]},
    )
    assert result.errors is None, result.errors
    assert gql_params.context.background
    await gql_params.context.background()
    await send_events(client=prefect_client, events=event_service.events)

    changes = await read_changes(db=db, branch=default_branch, session=session_admin, node_id=tenant.id)

    change = changes[str(event_service.events[0].meta.id)]
    assert change["attributes"] == [
        {"action": "UNCHANGED", "kind": "Text", "name": "name", "value": "tenant-log", "value_previous": "tenant-log"},
        {
            "action": "ADDED",
            "kind": "List",
            "name": "name__owners",
            "value": f"{first.name.value}, {second.name.value}",
            "value_previous": None,
        },
    ]
    stored = change["payload"]["data"]["changelog"]["attributes"]["name"]["properties"]["owners"]
    assert (stored["value"], stored["value_previous"]) == (f'["{first.id}","{second.id}"]', None)
