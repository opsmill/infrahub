"""Changelog enrichment: every node changelog carries its own and its relationship peers' labels.

Node mutations and branch merge/rebase both feed the changelog that becomes a webhook payload.
These tests run the real save / diff-collect paths against a live database and assert the
human-friendly identifiers that land on the changelog.
"""

from typing import Any

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.changelog.diff import DiffChangelogCollector, MigrationTracker
from infrahub.core.changelog.enrichment import NodeLabelLoader, NodeLabels, node_label_loader
from infrahub.core.changelog.models import (
    RelationshipCardinalityManyChangelog,
    RelationshipCardinalityOneChangelog,
    RelationshipChangelogGetter,
)
from infrahub.core.constants import RelationshipDeleteBehavior, SchemaPathType
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.model.path import EnrichedDiffRoot
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.models import SchemaUpdateMigrationInfo
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry

# A relationship only ZzzItem declares, so pointing it at a ZzzOwner leaves that owner unchanged.
_ONE_DIRECTIONAL_SCHEMA: dict[str, Any] = {
    "nodes": [
        {
            "name": "Owner",
            "namespace": "Zzz",
            "default_filter": "name__value",
            "display_label": "name__value",
            "attributes": [{"name": "name", "kind": "Text", "unique": True}],
        },
        {
            "name": "Item",
            "namespace": "Zzz",
            "default_filter": "name__value",
            "display_label": "name__value",
            "attributes": [{"name": "name", "kind": "Text", "unique": True}],
            "relationships": [
                {
                    "name": "owner",
                    "peer": "ZzzOwner",
                    "cardinality": "one",
                    "optional": True,
                    "direction": "outbound",
                    "identifier": "zzz_item_owner_oneway",
                }
            ],
        },
    ],
}


class _RaisingLabelReader:
    """A NodeLabelReader that always fails, standing in for an unavailable label backend."""

    async def load_labels(self, node_ids: list[str]) -> dict[str, NodeLabels]:
        raise RuntimeError("label backend unavailable")

    async def load_hfids(self, node_ids: list[str]) -> dict[str, list[str] | None]:
        raise RuntimeError("label backend unavailable")


async def _create_person_and_dog(db: InfrahubDatabase, branch: Branch, schema: SchemaBranch) -> tuple[Node, Node]:
    person = await Node.init(db=db, schema=schema.get(name="TestPerson"), branch=branch)
    await person.new(db=db, name={"value": "Jack", "is_protected": True})
    await person.save(db=db)

    dog = await Node.init(db=db, schema=schema.get(name="TestDog"), branch=branch)
    await dog.new(db=db, name={"value": "Rocky", "owner": person.id}, breed="Labrador", owner=person)
    await dog.save(db=db)
    return person, dog


async def _merge_car_owned_by_person(
    db: InfrahubDatabase, default_branch: Branch, branch_name: str
) -> tuple[EnrichedDiffRoot, Branch, Node, Node]:
    owner = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await owner.new(db=db, name="John", height=180)
    await owner.save(db=db)

    branch = await create_branch(db=db, branch_name=branch_name)
    car = await Node.init(db=db, schema="TestCar", branch=branch)
    await car.new(db=db, name="Volvo", nbr_seats=5, is_electric=False, owner={"id": owner.id})
    await car.save(db=db)

    component_registry = get_component_registry()
    coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    merger = await component_registry.get_component(DiffMerger, db=db, branch=branch)
    await coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    await merger.merge_graph(at=Timestamp())
    diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch)
    diff = await diff_repository.get_one(diff_branch_name=branch.name)
    return diff, branch, owner, car


async def test_mutation_enriches_the_mutated_nodes_own_relationships(
    db: InfrahubDatabase,
    default_branch: Branch,
    animal_person_schema: SchemaBranch,
) -> None:
    person, dog = await _create_person_and_dog(db, default_branch, animal_person_schema)

    # The mutated node carries its own materialized HFID.
    assert dog.node_changelog.hfid == await dog.get_hfid(db=db)
    assert dog.node_changelog.hfid

    await RelationshipChangelogGetter(
        db=db,
        branch=default_branch,
        label_loader=node_label_loader(db=db, branch=default_branch, node_loader=NodeManager.get_many),
    ).get_changelogs(primary_changelog=dog.node_changelog)

    owner_rel = dog.node_changelog.relationships["owner"]
    assert isinstance(owner_rel, RelationshipCardinalityOneChangelog)
    assert owner_rel.peer_id == person.id
    assert owner_rel.peer_display_label == await person.get_display_label(db=db)
    assert owner_rel.peer_hfid == await person.get_hfid(db=db)


async def test_mutation_enriches_secondary_peer_changelogs(
    db: InfrahubDatabase,
    default_branch: Branch,
    animal_person_schema: SchemaBranch,
) -> None:
    person, dog = await _create_person_and_dog(db, default_branch, animal_person_schema)

    secondaries = await RelationshipChangelogGetter(
        db=db,
        branch=default_branch,
        label_loader=node_label_loader(db=db, branch=default_branch, node_loader=NodeManager.get_many),
    ).get_changelogs(primary_changelog=dog.node_changelog)
    person_secondary = next(secondary for secondary in secondaries if secondary.node_id == person.id)

    # The peer node's real label and HFID are resolved, not the placeholder.
    assert person_secondary.display_label == await person.get_display_label(db=db)
    assert person_secondary.display_label != "n/a"
    assert person_secondary.hfid == await person.get_hfid(db=db)

    # The reciprocal relationship points back to the mutated node with its label and HFID.
    animals = person_secondary.relationships["animals"]
    assert isinstance(animals, RelationshipCardinalityManyChangelog)
    assert animals.peers[0].peer_id == dog.id
    assert animals.peers[0].peer_display_label == dog.node_changelog.display_label
    assert animals.peers[0].peer_hfid == dog.node_changelog.hfid


async def test_mutation_changelog_survives_label_reader_failure(
    db: InfrahubDatabase,
    default_branch: Branch,
    animal_person_schema: SchemaBranch,
) -> None:
    person, dog = await _create_person_and_dog(db, default_branch, animal_person_schema)

    secondaries = await RelationshipChangelogGetter(
        db=db, branch=default_branch, label_loader=NodeLabelLoader(reader=_RaisingLabelReader())
    ).get_changelogs(primary_changelog=dog.node_changelog)

    # The label read failed, so the secondaries carry placeholder labels rather than the failure
    # propagating to the already-committed mutation.
    person_secondary = next(secondary for secondary in secondaries if secondary.node_id == person.id)
    assert person_secondary.display_label == "n/a"
    assert person_secondary.hfid is None


async def test_unresolvable_peer_falls_back_to_placeholder(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_accord_main: Node,
    car_prius_main: Node,
    person_john_main: Node,
) -> None:
    cars_relationship = (
        registry.schema.get_schema_branch(name=default_branch.name)
        .get(name="TestPerson", duplicate=False)
        .get_relationship("cars")
    )
    original_on_delete = cars_relationship.on_delete
    cars_relationship.on_delete = RelationshipDeleteBehavior.CASCADE

    car_ids = {car_accord_main.id, car_prius_main.id}
    try:
        deleted = await NodeManager.delete(db=db, branch=default_branch, nodes=[person_john_main])
        assert {node.id for node in deleted} == {person_john_main.id, *car_ids}

        secondaries = await RelationshipChangelogGetter(
            db=db,
            branch=default_branch,
            label_loader=node_label_loader(db=db, branch=default_branch, node_loader=NodeManager.get_many),
        ).get_changelogs(primary_changelog=person_john_main.node_changelog)
    finally:
        cars_relationship.on_delete = original_on_delete
    car_secondaries = [secondary for secondary in secondaries if secondary.node_id in car_ids]
    assert len(car_secondaries) == len(car_ids)

    # The cascaded peers are already gone when their labels are resolved.
    assert all(secondary.display_label == "n/a" for secondary in car_secondaries)
    assert all(secondary.hfid is None for secondary in car_secondaries)


async def test_merge_enriches_node_hfid_and_peer_label(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_simplified_proposed_change_schema: SchemaBranch,
    car_person_schema: None,
) -> None:
    diff, branch, owner, car = await _merge_car_owned_by_person(db, default_branch, "merge_enrich")

    changelogs = await DiffChangelogCollector(
        diff=diff,
        db=db,
        branch=branch,
        label_loader=node_label_loader(db=db, branch=branch, node_loader=NodeManager.get_many),
    ).collect_changelogs()

    car_changelog = next(changelog for _, changelog in changelogs if changelog.node_id == car.id)
    owner_rel = car_changelog.relationships["owner"]
    assert isinstance(owner_rel, RelationshipCardinalityOneChangelog)

    # The node's HFID is absent from the diff, so it is resolved with a load.
    reloaded_car = await NodeManager.get_one(db=db, id=car.id, kind="TestCar", branch=branch)
    assert car_changelog.hfid == await reloaded_car.get_hfid(db=db)
    assert car_changelog.hfid

    # The peer's display label is carried by the diff itself.
    assert owner_rel.peer_id == owner.id
    assert owner_rel.peer_display_label == await owner.get_display_label(db=db)
    assert owner_rel.peer_display_label != "n/a"
    # The peer's HFID comes from the batch: the owner is a changed node too on this merge.
    assert owner_rel.peer_hfid == await owner.get_hfid(db=db)
    assert owner_rel.peer_hfid


async def test_merge_changelog_survives_label_reader_failure(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_simplified_proposed_change_schema: SchemaBranch,
    car_person_schema: None,
) -> None:
    diff, branch, _owner, car = await _merge_car_owned_by_person(db, default_branch, "merge_label_failure")

    changelogs = await DiffChangelogCollector(
        diff=diff, db=db, branch=branch, label_loader=NodeLabelLoader(reader=_RaisingLabelReader())
    ).collect_changelogs()

    # The collection completes despite the label read failing; the HFID just degrades to None.
    car_changelog = next(changelog for _, changelog in changelogs if changelog.node_id == car.id)
    assert car_changelog.hfid is None
    assert changelogs


async def test_merge_changelog_reports_deleted_node_hfid(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_simplified_proposed_change_schema: SchemaBranch,
    car_person_schema: None,
) -> None:
    owner = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await owner.new(db=db, name="John", height=180)
    await owner.save(db=db)
    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="Volvo", nbr_seats=5, is_electric=False, owner={"id": owner.id})
    await car.save(db=db)
    expected_hfid = await car.get_hfid(db=db)
    assert expected_hfid

    branch = await create_branch(db=db, branch_name="merge_delete_hfid")
    to_delete = await NodeManager.get_one(db=db, id=car.id, kind="TestCar", branch=branch)
    await to_delete.delete(db=db)

    component_registry = get_component_registry()
    coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    merger = await component_registry.get_component(DiffMerger, db=db, branch=branch)
    await coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    await merger.merge_graph(at=Timestamp())
    diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch)
    diff = await diff_repository.get_one(diff_branch_name=branch.name)

    changelogs = await DiffChangelogCollector(
        diff=diff,
        db=db,
        branch=branch,
        label_loader=node_label_loader(db=db, branch=branch, node_loader=NodeManager.get_many),
    ).collect_changelogs()

    # The car is gone when the batch load runs, but its HFID is recovered from the diff.
    car_changelog = next(changelog for _, changelog in changelogs if changelog.node_id == car.id)
    assert car_changelog.hfid == expected_hfid


async def test_merge_fills_peer_hfid_for_a_peer_that_did_not_change(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    data_schema: None,
) -> None:
    registry.schema.register_schema(schema=SchemaRoot(**_ONE_DIRECTIONAL_SCHEMA), branch=default_branch.name)
    default_branch.update_schema_hash()
    await default_branch.save(db=db)

    owner = await Node.init(db=db, schema="ZzzOwner", branch=default_branch)
    await owner.new(db=db, name="Alice")
    await owner.save(db=db)
    owner_hfid = await owner.get_hfid(db=db)

    branch = await create_branch(db=db, branch_name="oneway_merge")
    item = await Node.init(db=db, schema="ZzzItem", branch=branch)
    await item.new(db=db, name="Gadget", owner={"id": owner.id})
    await item.save(db=db)

    component_registry = get_component_registry()
    coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    merger = await component_registry.get_component(DiffMerger, db=db, branch=branch)
    await coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    await merger.merge_graph(at=Timestamp())
    diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch)
    diff = await diff_repository.get_one(diff_branch_name=branch.name)

    changelogs = await DiffChangelogCollector(
        diff=diff,
        db=db,
        branch=branch,
        label_loader=node_label_loader(db=db, branch=branch, node_loader=NodeManager.get_many),
    ).collect_changelogs()

    # The owner has no reciprocal relationship, so it is not a changed node, yet its HFID is still
    # resolved for the item's changelog.
    assert owner.id not in {changelog.node_id for _, changelog in changelogs}
    item_changelog = next(changelog for _, changelog in changelogs if changelog.node_id == item.id)
    owner_rel = item_changelog.relationships["owner"]
    assert isinstance(owner_rel, RelationshipCardinalityOneChangelog)
    assert owner_rel.peer_id == owner.id
    assert owner_rel.peer_hfid == owner_hfid


async def test_merge_tolerates_dropped_kind_referencing_an_unchanged_peer(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    data_schema: None,
) -> None:
    registry.schema.register_schema(schema=SchemaRoot(**_ONE_DIRECTIONAL_SCHEMA), branch=default_branch.name)
    default_branch.update_schema_hash()
    await default_branch.save(db=db)

    owner = await Node.init(db=db, schema="ZzzOwner", branch=default_branch)
    await owner.new(db=db, name="Alice")
    await owner.save(db=db)

    branch = await create_branch(db=db, branch_name="oneway_drop")
    item = await Node.init(db=db, schema="ZzzItem", branch=branch)
    await item.new(db=db, name="Gadget", owner={"id": owner.id})
    await item.save(db=db)

    component_registry = get_component_registry()
    coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    merger = await component_registry.get_component(DiffMerger, db=db, branch=branch)
    await coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    await merger.merge_graph(at=Timestamp())
    diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch)
    diff = await diff_repository.get_one(diff_branch_name=branch.name)

    # A schema migration drops the item's kind; its owner is unchanged and so absent from the diff.
    default_schema_snapshot = registry.schema.get_schema_branch(name=default_branch.name).duplicate()
    registry.schema.get_schema_branch(name=branch.name).delete(name="ZzzItem")
    registry.schema.get_schema_branch(name=default_branch.name).delete(name="ZzzItem")
    try:
        changelogs = await DiffChangelogCollector(
            diff=diff,
            db=db,
            branch=branch,
            label_loader=node_label_loader(db=db, branch=branch, node_loader=NodeManager.get_many),
        ).collect_changelogs()
    finally:
        registry.schema.set_schema_branch(name=default_branch.name, schema=default_schema_snapshot)

    item_changelog = next(changelog for _, changelog in changelogs if changelog.node_id == item.id)
    owner_rel = item_changelog.relationships["owner"]
    assert isinstance(owner_rel, RelationshipCardinalityOneChangelog)
    assert owner_rel.peer_id == owner.id
    # The dropped kind cannot resolve the unchanged peer's kind, so it degrades instead of failing.
    assert owner_rel.peer_kind == "n/a"


async def test_merge_tolerates_kind_deleted_in_migration(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_simplified_proposed_change_schema: SchemaBranch,
    car_person_schema: None,
) -> None:
    diff, branch, owner, car = await _merge_car_owned_by_person(db, default_branch, "merge_kind_deleted")

    owner_hfid = await owner.get_hfid(db=db)
    # A schema migration in the merge drops the car's kind, so its schema no longer resolves on
    # either branch. Snapshot the default schema to restore it once the assertions are done.
    default_schema_snapshot = registry.schema.get_schema_branch(name=default_branch.name).duplicate()
    registry.schema.get_schema_branch(name=branch.name).delete(name="TestCar")
    registry.schema.get_schema_branch(name=default_branch.name).delete(name="TestCar")
    try:
        changelogs = await DiffChangelogCollector(
            diff=diff,
            db=db,
            branch=branch,
            label_loader=node_label_loader(db=db, branch=branch, node_loader=NodeManager.get_many),
        ).collect_changelogs()
    finally:
        registry.schema.set_schema_branch(name=default_branch.name, schema=default_schema_snapshot)

    by_id = {changelog.node_id: changelog for _, changelog in changelogs}
    # The node whose kind is gone still yields a changelog, only without its HFID.
    assert by_id[car.id].hfid is None
    # A node whose kind survives keeps its HFID: the load degrades per node, not per batch.
    assert by_id[owner.id].hfid == owner_hfid


async def test_collector_applies_a_rename_migration_to_the_changelog(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_simplified_proposed_change_schema: SchemaBranch,
    car_person_schema: None,
) -> None:
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="John", height=180)
    await person.save(db=db)

    branch = await create_branch(db=db, branch_name="rebase_rename")
    person_on_branch = await NodeManager.get_one(db=db, id=person.id, kind="TestPerson", branch=branch)
    person_on_branch.height.value = 190
    await person_on_branch.save(db=db)

    component_registry = get_component_registry()
    coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    await coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch)
    diff = await diff_repository.get_one(diff_branch_name=branch.name)

    # The migration a rebase would produce when an attribute is renamed on the destination branch.
    rename = SchemaUpdateMigrationInfo(
        migration_name="attribute.name.update",
        path=SchemaPath(
            path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", property_name="height", field_name="stature"
        ),
    )
    changelogs = await DiffChangelogCollector(
        diff=diff,
        branch=branch,
        db=db,
        label_loader=node_label_loader(db=db, branch=branch, node_loader=NodeManager.get_many),
        migration_tracker=MigrationTracker(migrations=[rename]),
    ).collect_changelogs()

    person_changelog = next(changelog for _, changelog in changelogs if changelog.node_id == person.id)
    # The rename migration remaps the attribute, so the changelog reports the new name.
    assert "stature" in person_changelog.attributes
    assert "height" not in person_changelog.attributes
