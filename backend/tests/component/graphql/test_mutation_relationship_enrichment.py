from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.account import ObjectPermission
from infrahub.core.changelog.models import NodeChangelog
from infrahub.core.constants import PermissionAction, PermissionDecision, RelationshipCardinality
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.node import (
    NodeListGetAttributeQuery,
    NodeListGetInfoQuery,
    NodeListGetRelationshipsQuery,
    NodeListGetStoredLabelsQuery,
)
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.events.node_action import NodeMutatedEvent
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.graphql.mutations.relationship import _enrich_source_changelog
from infrahub.services import InfrahubServices
from tests.adapters.event import MemoryInfrahubEvent
from tests.helpers.db_query_counter import CountingInfrahubDatabase
from tests.helpers.graphql import graphql
from tests.helpers.permissions import define_permissions

if TYPE_CHECKING:
    from infrahub.auth.session import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


def _read_counts(counting_db: CountingInfrahubDatabase) -> dict[str, int]:
    """Count the label reads by kind: stored labels, node info, attributes and relationships."""
    return {
        query.name: counting_db.count_for(query.name)
        for query in (
            NodeListGetStoredLabelsQuery,
            NodeListGetInfoQuery,
            NodeListGetAttributeQuery,
            NodeListGetRelationshipsQuery,
        )
    }


async def _create_owned_dog(db: InfrahubDatabase, branch: Branch, schema: SchemaBranch) -> Node:
    owner = await Node.init(db=db, schema=schema.get_node(name="TestPerson"), branch=branch)
    await owner.new(db=db, name="Jack")
    await owner.save(db=db)
    dog = await Node.init(db=db, schema=schema.get_node(name="TestDog"), branch=branch)
    await dog.new(db=db, name="Rocky", breed="Labrador", owner=owner)
    await dog.save(db=db)
    return dog


@pytest.fixture
async def shirt_color_schema(db: InfrahubDatabase, default_branch: Branch, node_group_schema: None) -> SchemaBranch:
    """A shirt whose display label reads an optional cardinality-one relationship."""
    schema = SchemaRoot(
        nodes=[
            NodeSchema(
                name="Color",
                namespace="Test",
                display_label="name__value",
                human_friendly_id=["name__value"],
                attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
            ),
            NodeSchema(
                name="Shirt",
                namespace="Test",
                display_label="{{ name__value }} {{ color__name__value }}",
                human_friendly_id=["name__value"],
                attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
                relationships=[
                    RelationshipSchema(
                        name="color", peer="TestColor", cardinality=RelationshipCardinality.ONE, optional=True
                    )
                ],
            ),
        ]
    )
    return registry.schema.register_schema(schema=schema, branch=default_branch.name)


async def test_relationship_add_reports_the_display_label_computed_from_the_new_peer(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    shirt_color_schema: SchemaBranch,
    session_first_account: AccountSession,
    first_account: Node,
) -> None:
    """The node event of a RelationshipAdd carries the display label as the added peer makes it."""
    await define_permissions(
        account=first_account,
        db=db,
        object_permissions=[
            ObjectPermission(
                namespace="Test",
                name=name,
                action=PermissionAction.UPDATE.value,
                decision=PermissionDecision.ALLOW_ALL.value,
            )
            for name in ("Shirt", "Color")
        ],
    )
    red = await Node.init(db=db, schema="TestColor", branch=default_branch)
    await red.new(db=db, name="red")
    await red.save(db=db)
    shirt = await Node.init(db=db, schema="TestShirt", branch=default_branch)
    await shirt.new(db=db, name="polo")
    await shirt.save(db=db)

    memory_event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=memory_event)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=default_branch, service=service, account_session=session_first_account
    )
    result = await graphql(
        schema=gql_params.schema,
        source="""
        mutation ($id: String!, $color: String!) {
            RelationshipAdd(data: {id: $id, name: "color", nodes: [{id: $color}]}) { ok }
        }
        """,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": shirt.id, "color": red.id},
    )
    assert result.errors is None
    assert gql_params.context.background
    await gql_params.context.background()

    shirt_events = [
        event
        for event in memory_event.events
        if isinstance(event, NodeMutatedEvent) and event.changelog.node_id == shirt.id
    ]
    assert len(shirt_events) == 1
    assert shirt_events[0].changelog.display_label == "polo red"
    assert shirt_events[0].changelog.hfid == ["polo"]


async def test_has_label_depending_on_relationship_follows_the_label_definitions(
    db: InfrahubDatabase, default_branch: Branch, animal_person_schema: SchemaBranch
) -> None:
    """The HFID of a dog reads its owner, so only that relationship feeds a label."""
    dog = await _create_owned_dog(db, default_branch, animal_person_schema)

    assert dog.has_label_depending_on_relationship(name="owner")
    assert not dog.has_label_depending_on_relationship(name="best_friend")
    # A saved node holds both labels, so neither needs a read.
    assert not dog.display_label_needs_read()
    assert not dog.hfid_needs_read()


async def test_enrich_source_changelog_computes_labels_from_the_reloaded_node_when_the_relationship_feeds_them(
    db: InfrahubDatabase, default_branch: Branch, animal_person_schema: SchemaBranch
) -> None:
    """A relationship the HFID reads has the labels computed from the node and its peer as reloaded."""
    dog = await _create_owned_dog(db, default_branch, animal_person_schema)
    current_hfid = await dog.get_hfid(db=db)
    current_label = await dog.get_display_label(db=db)
    assert current_hfid == ["Jack", "Rocky"]

    counting_db = CountingInfrahubDatabase.from_db(db=db)
    changelog = NodeChangelog(node_id=dog.id, node_kind="TestDog", display_label="stale", hfid=["stale"])
    await _enrich_source_changelog(
        node_changelog=changelog, source=dog, relationship_name="owner", db=counting_db, branch=default_branch
    )

    assert changelog.hfid == current_hfid
    assert changelog.display_label == current_label
    assert _read_counts(counting_db) == {
        NodeListGetStoredLabelsQuery.name: 0,
        NodeListGetInfoQuery.name: 2,
        NodeListGetAttributeQuery.name: 2,
        NodeListGetRelationshipsQuery.name: 0,
    }


async def test_enrich_source_changelog_uses_the_loaded_node_when_the_relationship_feeds_no_label(
    db: InfrahubDatabase, default_branch: Branch, animal_person_schema: SchemaBranch
) -> None:
    """A relationship neither label reads fills the HFID from the node in hand, without a read."""
    dog = await _create_owned_dog(db, default_branch, animal_person_schema)
    counting_db = CountingInfrahubDatabase.from_db(db=db)

    changelog = NodeChangelog(node_id=dog.id, node_kind="TestDog", display_label="kept", hfid=None)
    await _enrich_source_changelog(
        node_changelog=changelog, source=dog, relationship_name="best_friend", db=counting_db, branch=default_branch
    )

    assert changelog.hfid == await dog.get_hfid(db=db)
    assert changelog.display_label == "kept"
    assert _read_counts(counting_db) == {
        NodeListGetStoredLabelsQuery.name: 0,
        NodeListGetInfoQuery.name: 0,
        NodeListGetAttributeQuery.name: 0,
        NodeListGetRelationshipsQuery.name: 0,
    }


async def test_enrich_source_changelog_leaves_changelog_when_node_cannot_be_read(
    db: InfrahubDatabase, default_branch: Branch, animal_person_schema: SchemaBranch
) -> None:
    """Enrichment is best-effort: an unreadable node leaves the changelog untouched, never raising."""
    owner = await Node.init(db=db, schema=animal_person_schema.get_node(name="TestPerson"), branch=default_branch)
    await owner.new(db=db, name="Jack")
    await owner.save(db=db)
    unsaved_dog = await Node.init(db=db, schema=animal_person_schema.get_node(name="TestDog"), branch=default_branch)
    await unsaved_dog.new(db=db, name="Ghost", breed="Labrador", owner=owner)

    counting_db = CountingInfrahubDatabase.from_db(db=db)
    changelog = NodeChangelog(node_id=unsaved_dog.id, node_kind="TestDog", display_label="kept", hfid=["kept"])
    await _enrich_source_changelog(
        node_changelog=changelog, source=unsaved_dog, relationship_name="owner", db=counting_db, branch=default_branch
    )

    assert changelog.hfid == ["kept"]
    assert changelog.display_label == "kept"
    assert _read_counts(counting_db) == {
        NodeListGetStoredLabelsQuery.name: 0,
        NodeListGetInfoQuery.name: 1,
        NodeListGetAttributeQuery.name: 1,
        NodeListGetRelationshipsQuery.name: 0,
    }


async def test_enrich_source_changelog_rereads_labels_on_a_profiles_mutation(
    db: InfrahubDatabase, default_branch: Branch, animal_person_schema: SchemaBranch
) -> None:
    """A profile change can rewrite the attributes the labels read, so both labels are re-read."""
    dog = await _create_owned_dog(db, default_branch, animal_person_schema)

    counting_db = CountingInfrahubDatabase.from_db(db=db)
    changelog = NodeChangelog(node_id=dog.id, node_kind="TestDog", display_label="stale", hfid=["stale"])
    await _enrich_source_changelog(
        node_changelog=changelog, source=dog, relationship_name="profiles", db=counting_db, branch=default_branch
    )

    assert changelog.hfid == await dog.get_hfid(db=db)
    assert changelog.display_label == await dog.get_display_label(db=db)
    assert _read_counts(counting_db) == {
        NodeListGetStoredLabelsQuery.name: 1,
        NodeListGetInfoQuery.name: 0,
        NodeListGetAttributeQuery.name: 0,
        NodeListGetRelationshipsQuery.name: 0,
    }


async def test_enrich_source_changelog_reads_through_the_loader_when_the_hfid_is_not_materialized(
    db: InfrahubDatabase, default_branch: Branch, animal_person_schema: SchemaBranch
) -> None:
    """A node loaded without its stored HFID takes the guarded loader path, not the read-free one."""
    dog = await _create_owned_dog(db, default_branch, animal_person_schema)
    partial = await NodeManager.get_one(db=db, id=dog.id, branch=default_branch, fields={"name": None})
    assert partial is not None
    assert partial.hfid_needs_read()

    counting_db = CountingInfrahubDatabase.from_db(db=db)
    changelog = NodeChangelog(node_id=dog.id, node_kind="TestDog", display_label="stale", hfid=None)
    await _enrich_source_changelog(
        node_changelog=changelog, source=partial, relationship_name="best_friend", db=counting_db, branch=default_branch
    )

    assert changelog.hfid == await dog.get_hfid(db=db)
    assert changelog.display_label == await dog.get_display_label(db=db)
    assert _read_counts(counting_db) == {
        NodeListGetStoredLabelsQuery.name: 1,
        NodeListGetInfoQuery.name: 0,
        NodeListGetAttributeQuery.name: 0,
        NodeListGetRelationshipsQuery.name: 0,
    }
