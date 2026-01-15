from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.branch.models import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreStandardWebhook
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def test_create_webhook_invalid_node(
    db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
) -> None:
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_WEBHOOK,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"name": "invalid-hook", "node_kind": "InvalidNodeKind"},
    )
    assert result.errors
    assert "Unable to find the schema 'InvalidNodeKind' in the registry" in str(result.errors)


async def test_create_webhook_invalid_node_event(
    db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
) -> None:
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_WEBHOOK,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"name": "invalid-hook", "node_kind": "BuiltinTag", "event_type": "infrahub.branch.created"},
    )
    assert result.errors
    assert "Defining a node_kind is not valid for infrahub.branch.created events" in str(result.errors)


async def test_create_webhook_with_node_kind_and_valid_node_event(
    db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
) -> None:
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_WEBHOOK,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "name": "valid-node-created-event",
            "node_kind": "BuiltinTag",
            "event_type": "infrahub.node.created",
        },
    )
    assert not result.errors
    assert result.data
    webhook_id = result.data["CoreStandardWebhookCreate"]["object"]["id"]
    webhook = await NodeManager.get_one_by_id_or_default_filter(db=db, id=webhook_id, kind=CoreStandardWebhook)
    assert webhook.name.value == "valid-node-created-event"
    assert webhook.node_kind.value == "BuiltinTag"
    assert webhook.event_type.value.value == "infrahub.node.created"


async def test_update_webhook_with_optional_node_kind(
    db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
) -> None:
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_WEBHOOK,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"name": "builtin-tag-update-1", "node_kind": "BuiltinTag", "event_type": "all"},
    )
    assert not result.errors
    assert result.data
    webhook_id = result.data["CoreStandardWebhookCreate"]["object"]["id"]
    webhook = await NodeManager.get_one_by_id_or_default_filter(db=db, id=webhook_id, kind=CoreStandardWebhook)
    assert webhook.name.value == "builtin-tag-update-1"
    assert webhook.node_kind.value == "BuiltinTag"

    result = await graphql(
        schema=gql_params.schema,
        source=UPDATE_WEBHOOK,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "id": webhook_id,
            "node_kind": None,
        },
    )
    assert not result.errors
    assert result.data
    updated_webhook = await NodeManager.get_one_by_id_or_default_filter(db=db, id=webhook_id, kind=CoreStandardWebhook)
    assert updated_webhook.node_kind.value is None


async def test_create_webhook_with_node_kind_and_all_events(
    db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
) -> None:
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_WEBHOOK,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"name": "valid-node-all-events", "node_kind": "BuiltinTag", "event_type": "all"},
    )
    assert not result.errors
    assert result.data
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_WEBHOOK,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "name": "valid-node-all-events-by-default",
            "node_kind": "BuiltinTag",
        },
    )
    assert not result.errors
    assert result.data
    webhook_id = result.data["CoreStandardWebhookCreate"]["object"]["id"]
    webhook = await NodeManager.get_one_by_id_or_default_filter(db=db, id=webhook_id, kind=CoreStandardWebhook)
    assert webhook.name.value == "valid-node-all-events-by-default"
    assert webhook.node_kind.value == "BuiltinTag"
    assert webhook.event_type.value.value == "all"


async def test_update_to_invalid_states(
    db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
) -> None:
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_WEBHOOK,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"name": "builtin-tag-update-1", "node_kind": "BuiltinTag", "event_type": "all"},
    )
    assert not result.errors
    assert result.data
    webhook_id = result.data["CoreStandardWebhookCreate"]["object"]["id"]

    result = await graphql(
        schema=gql_params.schema,
        source=UPDATE_WEBHOOK,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "id": webhook_id,
            "node_kind": "InvalidNodeKind",
        },
    )
    assert result.errors
    assert "Unable to find the schema 'InvalidNodeKind' in the registry" in str(result.errors)

    result = await graphql(
        schema=gql_params.schema,
        source=UPDATE_WEBHOOK,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "id": webhook_id,
            "event_type": "infrahub.branch.merged",
        },
    )
    assert result.errors
    assert "Defining a node_kind is not valid for infrahub.branch.merged events" in str(result.errors)


async def test_update_to_valid_states(
    db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
) -> None:
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_WEBHOOK,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"name": "repository-update-1", "node_kind": "CoreRepository"},
    )
    assert not result.errors
    assert result.data
    webhook_id = result.data["CoreStandardWebhookCreate"]["object"]["id"]
    webhook = await NodeManager.get_one_by_id_or_default_filter(db=db, id=webhook_id, kind=CoreStandardWebhook)
    assert webhook.name.value == "repository-update-1"
    assert webhook.node_kind.value == "CoreRepository"
    assert webhook.event_type.value.value == "all"

    result = await graphql(
        schema=gql_params.schema,
        source=UPDATE_WEBHOOK,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "id": webhook_id,
            "node_kind": "BuiltinTag",
        },
    )
    assert not result.errors
    assert result.data
    updated_webhook = await NodeManager.get_one_by_id_or_default_filter(db=db, id=webhook_id, kind=CoreStandardWebhook)
    assert updated_webhook.name.value == "repository-update-1"
    assert updated_webhook.node_kind.value == "BuiltinTag"
    assert updated_webhook.event_type.value.value == "all"


async def test_update_description_only(
    db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
) -> None:
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_WEBHOOK,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"name": "tag-update-2", "node_kind": "BuiltinTag", "event_type": "infrahub.node.created"},
    )
    assert not result.errors
    assert result.data
    webhook_id = result.data["CoreStandardWebhookCreate"]["object"]["id"]
    webhook = await NodeManager.get_one_by_id_or_default_filter(db=db, id=webhook_id, kind=CoreStandardWebhook)
    assert webhook.name.value == "tag-update-2"
    assert webhook.node_kind.value == "BuiltinTag"
    assert webhook.description.value is None
    assert webhook.event_type.value.value == "infrahub.node.created"

    result = await graphql(
        schema=gql_params.schema,
        source=UPDATE_WEBHOOK,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "id": webhook_id,
            "description": "Sent when tags are created",
        },
    )
    assert not result.errors
    assert result.data

    updated_webhook = await NodeManager.get_one_by_id_or_default_filter(db=db, id=webhook_id, kind=CoreStandardWebhook)
    assert updated_webhook.name.value == "tag-update-2"
    assert updated_webhook.node_kind.value == "BuiltinTag"
    assert updated_webhook.description.value == "Sent when tags are created"
    assert updated_webhook.event_type.value.value == "infrahub.node.created"


async def test_upsert_webhook(db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch) -> None:
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=UPSERT_WEBHOOK,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "name": "my-upserted-webhook",
            "description": "I was created",
            "url": "http://localhost:8200/webhook",
            "shared_key": "very-secret",
        },
    )
    assert not result.errors
    assert result.data

    result = await graphql(
        schema=gql_params.schema,
        source=UPSERT_WEBHOOK,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "name": "my-upserted-webhook",
            "description": "I was updated",
            "url": "http://localhost:8200/webhook",
            "shared_key": "very-secret",
        },
    )
    assert not result.errors
    assert result.data
    webhook_id = result.data["CoreStandardWebhookUpsert"]["object"]["id"]
    webhook = await NodeManager.get_one_by_id_or_default_filter(db=db, id=webhook_id, kind=CoreStandardWebhook)
    assert webhook.name.value == "my-upserted-webhook"
    assert webhook.description.value == "I was updated"


CREATE_WEBHOOK = """
mutation CreateWebhook(
    $event_type: String
    $node_kind: String
    $name: String!
) {
    CoreStandardWebhookCreate(
        data: {
            event_type: {value: $event_type},
            node_kind: {value: $node_kind},
            url: {value: "https://webhook.example.com/infrahub"},
            name: {value: $name},
            shared_key: {value: "very-secret"}
        }
    ) {
        object {
            id
        }
    }
}
"""

UPDATE_WEBHOOK = """
mutation UpdateWebhook(
    $event_type: String
    $node_kind: String
    $description: String
    $id: String!
) {
  CoreStandardWebhookUpdate(
    data: {
        id: $id,
        event_type: {value: $event_type},
        node_kind: {value: $node_kind},
        description: {value: $description}
  }
  ) {
    object {
      id
    }
  }
}
"""

UPSERT_WEBHOOK = """
mutation UpsertWebhook(
    $shared_key: String
    $description: String
    $name: String!
    $url: String

)   {
    CoreStandardWebhookUpsert(
        data: {
            shared_key: {
                value: $shared_key
            }
            description: {
                value: $description
            }
            name: {
                value: $name
            }
            url: {
                value: $url
            }
        }
    ){
        ok
        object {
            id
            name {
                value
            }
            description {
                value
            }
        }
    }
}
"""
