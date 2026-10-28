from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import MetadataOptions, MutationAction
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.create import create_node
from infrahub.core.query.attribute import (
    AttributeUpdateFlagQuery,
    AttributeUpdateNodePropertyQuery,
    AttributeUpdateValueQuery,
)
from infrahub.core.query.node import NodeCreateAllQuery
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot
from infrahub.events.generator import generate_node_mutation_events
from infrahub.events.models import EventBranchContext, EventContext
from infrahub.events.node_action import NodeCreatedEvent
from tests.constants import TestKind
from tests.helpers.db_query_counter import CountingInfrahubDatabase
from tests.helpers.schema import CHILD, THING, load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


@pytest.fixture
async def schema(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[CHILD, THING]), branch_name=default_branch.name)


async def test_create_with_profiles_writes_and_records_their_values_once(
    db: InfrahubDatabase, default_branch: Branch, schema: None
) -> None:
    """The node is written once with the value and the peer its profile gives, and its created event lists them."""
    owner = await Node.init(db=db, schema=TestKind.CHILD, branch=default_branch)
    await owner.new(db=db, name="owner")
    await owner.save(db=db)
    profile = await Node.init(db=db, schema=f"Profile{TestKind.THING}", branch=default_branch)
    await profile.new(db=db, profile_name="blue-thing", profile_priority=1000, color="blue", owner=owner)
    await profile.save(db=db)
    thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=default_branch)
    counting_db = CountingInfrahubDatabase.from_db(db=db)

    thing = await create_node(
        data={"name": "ball", "profiles": [profile.id]}, db=counting_db, branch=default_branch, schema=thing_schema
    )

    assert counting_db.count_for(NodeCreateAllQuery.name) == 1
    assert [
        counting_db.count_for(query.name)
        for query in (AttributeUpdateValueQuery, AttributeUpdateFlagQuery, AttributeUpdateNodePropertyQuery)
    ] == [0, 0, 0]
    events = await generate_node_mutation_events(
        node=thing,
        deleted_nodes=[],
        db=db,
        branch=default_branch,
        context=EventContext(branch=EventBranchContext(name=default_branch.name), account_id="test-account"),
        request_id="test-request",
        action=MutationAction.CREATED,
        recorded_nodes=[],
    )
    created = [event for event in events if isinstance(event, NodeCreatedEvent)]
    assert [(event.node_id, sorted(event.fields)) for event in created] == [
        (thing.id, ["color", "description", "display_label", "human_friendly_id", "name", "owner", "profiles"])
    ]
    changelog = created[0].changelog
    assert (
        changelog.attributes["color"].value,
        changelog.attributes["color"].properties["source"].value,
        changelog.attributes["description"].value,
    ) == ("blue", profile.id, "owner's blue ball")
    assert changelog.relationships["owner"].model_dump(include={"peer_id", "peer_id_previous"}) == {
        "peer_id": owner.id,
        "peer_id_previous": None,
    }

    reloaded = await NodeManager.get_one(
        db=db, id=thing.id, branch=default_branch, include_metadata=MetadataOptions.SOURCE, raise_on_error=True
    )
    owner_relationships = await reloaded.get_relationship(name="owner").get_relationships(db=db)
    assert (
        reloaded.get_attribute(name="color").value,
        reloaded.get_attribute(name="color").source_id,
        reloaded.get_attribute(name="description").value,
        [(rel.peer_id, rel.source_id) for rel in owner_relationships],
    ) == ("blue", profile.id, "owner's blue ball", [(owner.id, profile.id)])
