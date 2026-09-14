from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.changelog.models import NodeChangelog
from infrahub.core.node import Node
from infrahub.core.query.node import NodeListGetAttributeQuery
from infrahub.graphql.mutations.relationship import _enrich_source_changelog
from tests.helpers.db_query_counter import CountingInfrahubDatabase

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


async def _create_owned_dog(db: InfrahubDatabase, branch: Branch, schema: SchemaBranch) -> Node:
    owner = await Node.init(db=db, schema=schema.get_node(name="TestPerson"), branch=branch)
    await owner.new(db=db, name="Jack")
    await owner.save(db=db)
    dog = await Node.init(db=db, schema=schema.get_node(name="TestDog"), branch=branch)
    await dog.new(db=db, name="Rocky", breed="Labrador", owner=owner)
    await dog.save(db=db)
    return dog


async def test_has_label_depending_on_relationship_follows_the_templates(
    db: InfrahubDatabase, default_branch: Branch, animal_person_schema: SchemaBranch
) -> None:
    """The HFID of a dog reads its owner, so only that relationship feeds a label."""
    dog = await _create_owned_dog(db, default_branch, animal_person_schema)

    assert dog.has_label_depending_on_relationship(name="owner")
    assert not dog.has_label_depending_on_relationship(name="best_friend")


async def test_enrich_source_changelog_rereads_labels_when_the_relationship_feeds_them(
    db: InfrahubDatabase, default_branch: Branch, animal_person_schema: SchemaBranch
) -> None:
    """A relationship the HFID template reads is re-read from the database, overwriting stale labels."""
    dog = await _create_owned_dog(db, default_branch, animal_person_schema)
    current_hfid = await dog.get_hfid(db=db)
    current_label = await dog.get_display_label(db=db)
    assert current_hfid == ["Jack", "Rocky"]

    changelog = NodeChangelog(node_id=dog.id, node_kind="TestDog", display_label="stale", hfid=["stale"])
    await _enrich_source_changelog(
        node_changelog=changelog, source=dog, relationship_name="owner", db=db, branch=default_branch
    )

    assert changelog.hfid == current_hfid
    assert changelog.display_label == current_label


async def test_enrich_source_changelog_uses_the_loaded_node_when_the_relationship_feeds_no_label(
    db: InfrahubDatabase, default_branch: Branch, animal_person_schema: SchemaBranch
) -> None:
    """A relationship outside both templates fills the HFID from the node in hand, without a read."""
    dog = await _create_owned_dog(db, default_branch, animal_person_schema)
    counting_db = CountingInfrahubDatabase.from_db(db=db)

    changelog = NodeChangelog(node_id=dog.id, node_kind="TestDog", display_label="kept", hfid=None)
    await _enrich_source_changelog(
        node_changelog=changelog, source=dog, relationship_name="best_friend", db=counting_db, branch=default_branch
    )

    assert changelog.hfid == await dog.get_hfid(db=db)
    assert changelog.display_label == "kept"
    assert counting_db.count_for(NodeListGetAttributeQuery.name) == 0


async def test_enrich_source_changelog_leaves_changelog_when_node_cannot_be_read(
    db: InfrahubDatabase, default_branch: Branch, animal_person_schema: SchemaBranch
) -> None:
    """Enrichment is best-effort: an unreadable node leaves the changelog untouched, never raising."""
    owner = await Node.init(db=db, schema=animal_person_schema.get_node(name="TestPerson"), branch=default_branch)
    await owner.new(db=db, name="Jack")
    await owner.save(db=db)
    unsaved_dog = await Node.init(db=db, schema=animal_person_schema.get_node(name="TestDog"), branch=default_branch)
    await unsaved_dog.new(db=db, name="Ghost", breed="Labrador", owner=owner)

    changelog = NodeChangelog(node_id=unsaved_dog.id, node_kind="TestDog", display_label="kept", hfid=["kept"])
    await _enrich_source_changelog(
        node_changelog=changelog, source=unsaved_dog, relationship_name="owner", db=db, branch=default_branch
    )

    assert changelog.hfid == ["kept"]
    assert changelog.display_label == "kept"
