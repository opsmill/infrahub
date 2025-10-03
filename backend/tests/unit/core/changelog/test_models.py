from infrahub.core.changelog.models import (
    AttributeChangelog,
    NodeChangelog,
    PropertyChangelog,
    RelationshipCardinalityManyChangelog,
    RelationshipCardinalityOneChangelog,
    RelationshipChangelogGetter,
    RelationshipPeerChangelog,
)
from infrahub.core.constants import DiffAction
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase


async def test_node_changelog_creation(db: InfrahubDatabase, default_branch, animal_person_schema):
    person_schema = animal_person_schema.get(name="TestPerson")
    dog_schema = animal_person_schema.get(name="TestDog")

    person1 = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await person1.new(db=db, name={"value": "Jack", "is_protected": True})
    await person1.save(db=db)

    dog1 = await Node.init(db=db, schema=dog_schema, branch=default_branch)
    await dog1.new(db=db, name={"value": "Rocky", "owner": person1.id}, breed="Labrador", owner=person1)
    await dog1.save(db=db)

    assert person1.node_changelog == NodeChangelog(
        node_id=person1.id,
        node_kind="TestPerson",
        display_label="Jack",
        attributes={
            "human_friendly_id": AttributeChangelog(
                name="human_friendly_id",
                value=["Jack"],
                value_previous=None,
                properties={
                    "is_protected": PropertyChangelog(
                        name="is_protected",
                        value=False,
                        value_previous=None,
                    ),
                    "is_visible": PropertyChangelog(
                        name="is_visible",
                        value=True,
                        value_previous=None,
                    ),
                },
                kind="List",
            ),
            "name": AttributeChangelog(
                name="name",
                value="Jack",
                value_previous=None,
                properties={
                    "is_protected": PropertyChangelog(
                        name="is_protected",
                        value=True,
                        value_previous=None,
                    ),
                    "is_visible": PropertyChangelog(
                        name="is_visible",
                        value=True,
                        value_previous=None,
                    ),
                },
                kind="Text",
            ),
            "display_label": AttributeChangelog(
                name="display_label",
                value="Jack",
                value_previous=None,
                properties={
                    "is_protected": PropertyChangelog(
                        name="is_protected",
                        value=False,
                        value_previous=None,
                    ),
                    "is_visible": PropertyChangelog(
                        name="is_visible",
                        value=True,
                        value_previous=None,
                    ),
                },
                kind="Text",
            ),
            "height": AttributeChangelog(
                name="height",
                value=None,
                value_previous=None,
                properties={
                    "is_protected": PropertyChangelog(
                        name="is_protected",
                        value=False,
                        value_previous=None,
                    ),
                    "is_visible": PropertyChangelog(
                        name="is_visible",
                        value=True,
                        value_previous=None,
                    ),
                },
                kind="Number",
            ),
        },
        relationships={},
    )
    owner: dict[str, RelationshipCardinalityManyChangelog | RelationshipCardinalityOneChangelog] = {
        "owner": RelationshipCardinalityOneChangelog(
            name="owner",
            peer_id_previous=None,
            peer_kind_previous=None,
            peer_id=person1.id,
            peer_kind="TestPerson",
            properties={
                "is_protected": PropertyChangelog(name="is_protected", value=False, value_previous=None),
                "is_visible": PropertyChangelog(name="is_visible", value=True, value_previous=None),
            },
        )
    }
    assert dog1.node_changelog == NodeChangelog(
        node_id=dog1.id,
        node_kind="TestDog",
        display_label="Rocky Labrador",
        attributes={
            "human_friendly_id": AttributeChangelog(
                name="human_friendly_id",
                value=["Jack", "Rocky"],
                value_previous=None,
                properties={
                    "is_protected": PropertyChangelog(name="is_protected", value=False, value_previous=None),
                    "is_visible": PropertyChangelog(name="is_visible", value=True, value_previous=None),
                },
                kind="List",
            ),
            "breed": AttributeChangelog(
                name="breed",
                value="Labrador",
                value_previous=None,
                properties={
                    "is_protected": PropertyChangelog(name="is_protected", value=False, value_previous=None),
                    "is_visible": PropertyChangelog(name="is_visible", value=True, value_previous=None),
                },
                kind="Text",
            ),
            "color": AttributeChangelog(
                name="color",
                value="#444444",
                value_previous=None,
                properties={
                    "is_protected": PropertyChangelog(name="is_protected", value=False, value_previous=None),
                    "is_visible": PropertyChangelog(name="is_visible", value=True, value_previous=None),
                },
                kind="Color",
            ),
            "name": AttributeChangelog(
                name="name",
                value="Rocky",
                value_previous=None,
                properties={
                    "owner": PropertyChangelog(name="owner", value=person1.id, value_previous=None),
                    "is_protected": PropertyChangelog(name="is_protected", value=False, value_previous=None),
                    "is_visible": PropertyChangelog(name="is_visible", value=True, value_previous=None),
                },
                kind="Text",
            ),
            "display_label": AttributeChangelog(
                name="display_label",
                value="Rocky Labrador",
                value_previous=None,
                properties={
                    "is_protected": PropertyChangelog(name="is_protected", value=False, value_previous=None),
                    "is_visible": PropertyChangelog(name="is_visible", value=True, value_previous=None),
                },
                kind="Text",
            ),
            "weight": AttributeChangelog(
                name="weight",
                value=None,
                value_previous=None,
                properties={
                    "is_protected": PropertyChangelog(name="is_protected", value=False, value_previous=None),
                    "is_visible": PropertyChangelog(name="is_visible", value=True, value_previous=None),
                },
                kind="Number",
            ),
        },
        relationships=owner,
    )
    assert not dog1.node_changelog.parent

    relationship_changelogs = RelationshipChangelogGetter(db=db, branch=default_branch)
    secondary_changelogs = await relationship_changelogs.get_changelogs(primary_changelog=dog1.node_changelog)
    assert len(secondary_changelogs) == 1

    second = secondary_changelogs[0]
    assert second.node_id == person1.id
    assert second.node_kind == person1.get_kind()
    assert list(second.relationships.keys()) == ["animals"]
    assert second.relationships["animals"] == RelationshipCardinalityManyChangelog(
        name="animals",
        peers=[
            RelationshipPeerChangelog(
                peer_id=dog1.id,
                peer_kind=dog1.get_kind(),
                peer_status=DiffAction.ADDED,
                properties={},
            )
        ],
    )


async def test_node_changelog_update_with_cardinality_one_relationship(
    db: InfrahubDatabase, default_branch, animal_person_schema
):
    person_schema = animal_person_schema.get(name="TestPerson")
    dog_schema = animal_person_schema.get(name="TestDog")

    person1 = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await person1.new(db=db, name="Jack")
    await person1.save(db=db)
    person2 = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await person2.new(db=db, name="Jill")
    await person2.save(db=db)

    dog1 = await Node.init(db=db, schema=dog_schema, branch=default_branch)
    await dog1.new(db=db, name={"value": "Rocky", "owner": person1.id}, breed="Labrador", owner=person1)
    await dog1.save(db=db)

    dog1_update = await NodeManager.get_one(id=dog1.id, db=db)
    dog1_update.name.is_protected = True
    dog1_update.color.value = "Brown"
    await dog1_update.owner.update(data=person2, db=db)

    await dog1_update.save(db=db)
    assert dog1_update.node_changelog == NodeChangelog(
        node_id=dog1.id,
        node_kind="TestDog",
        display_label="Rocky Labrador",
        attributes={
            "color": AttributeChangelog(
                name="color", value="Brown", value_previous="#444444", properties={}, kind="Color"
            ),
            "name": AttributeChangelog(
                name="name",
                value="Rocky",
                value_previous="Rocky",
                properties={"is_protected": PropertyChangelog(name="is_protected", value=True, value_previous=False)},
                kind="Text",
            ),
            "human_friendly_id": AttributeChangelog(
                name="human_friendly_id",
                value='["Jill","Rocky"]',
                value_previous='["Jack","Rocky"]',
                properties={},
                kind="List",
            ),
        },
        relationships={
            "owner": RelationshipCardinalityOneChangelog(
                name="owner",
                peer_id_previous=person1.id,
                peer_kind_previous="TestPerson",
                peer_id=person2.id,
                peer_kind="TestPerson",
                properties={},
            )
        },
    )
    assert not dog1_update.node_changelog.parent

    relationship_changelogs = RelationshipChangelogGetter(db=db, branch=default_branch)
    secondary_changelogs = await relationship_changelogs.get_changelogs(primary_changelog=dog1_update.node_changelog)
    assert len(secondary_changelogs) == 2

    person1_secondary = [changelog for changelog in secondary_changelogs if changelog.node_id == person1.id][0]
    person2_secondary = [changelog for changelog in secondary_changelogs if changelog.node_id == person2.id][0]

    assert isinstance(person1_secondary.relationships["animals"], RelationshipCardinalityManyChangelog)
    assert len(person1_secondary.relationships["animals"].peers) == 1
    assert person1_secondary.relationships["animals"].peers[0].peer_status == DiffAction.REMOVED
    assert isinstance(person2_secondary.relationships["animals"], RelationshipCardinalityManyChangelog)
    assert len(person2_secondary.relationships["animals"].peers) == 1
    assert person2_secondary.relationships["animals"].peers[0].peer_status == DiffAction.ADDED


async def test_node_changelog_update_with_cardinality_many_relationship(
    db: InfrahubDatabase, default_branch, animal_person_schema, standard_group_schema
):
    person_schema = animal_person_schema.get(name="TestPerson")

    person1 = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await person1.new(db=db, name="Jack")
    await person1.save(db=db)
    person2 = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await person2.new(db=db, name="Jill")
    await person2.save(db=db)

    group1 = await Node.init(db=db, schema="CoreStandardGroup", branch=default_branch)
    await group1.new(
        db=db,
        name="People",
        members=[person1, {"id": person2.id, "_relation__is_protected": True, "_relation__is_visible": True}],
    )
    await group1.save(db=db)
    assert isinstance(group1.node_changelog.relationships["members"], RelationshipCardinalityManyChangelog)
    assert (
        RelationshipPeerChangelog(
            peer_id=person1.id,
            peer_kind="TestPerson",
            peer_status=DiffAction.ADDED,
            properties={
                "is_protected": PropertyChangelog(name="is_protected", value=False, value_previous=None),
                "is_visible": PropertyChangelog(name="is_visible", value=False, value_previous=None),
            },
        )
        in group1.node_changelog.relationships["members"].peers
    )
    assert (
        RelationshipPeerChangelog(
            peer_id=person2.id,
            peer_kind="TestPerson",
            peer_status=DiffAction.ADDED,
            properties={
                "is_protected": PropertyChangelog(name="is_protected", value=True, value_previous=None),
                "is_visible": PropertyChangelog(name="is_visible", value=True, value_previous=None),
            },
        )
        in group1.node_changelog.relationships["members"].peers
    )
    assert not group1.node_changelog.parent


async def test_node_changelog_delete_with_cardinality_one_relationship(
    db: InfrahubDatabase, default_branch, animal_person_schema
):
    person_schema = animal_person_schema.get(name="TestPerson")
    dog_schema = animal_person_schema.get(name="TestDog")

    person1 = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await person1.new(db=db, name="Jack")
    await person1.save(db=db)

    dog1 = await Node.init(db=db, schema=dog_schema, branch=default_branch)
    await dog1.new(db=db, name={"value": "Rocky", "owner": person1.id}, breed="Labrador", owner=person1)
    await dog1.save(db=db)

    dog1_update = await NodeManager.get_one(id=dog1.id, db=db)
    await dog1_update.delete(db=db)
    assert dog1_update.node_changelog.attributes["breed"].value_update_status == DiffAction.REMOVED
    assert list(dog1_update.node_changelog.relationships.keys()) == ["owner"]
    assert dog1_update.node_changelog.relationships["owner"].peer_status == DiffAction.REMOVED
    assert not dog1_update.node_changelog.parent


async def test_node_changelog_delete_with_cardinality_many_relationship(
    db: InfrahubDatabase, default_branch, animal_person_schema
):
    person_schema = animal_person_schema.get(name="TestPerson")
    dog_schema = animal_person_schema.get(name="TestDog")

    person1 = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await person1.new(db=db, name="Jack")
    await person1.save(db=db)

    dog1 = await Node.init(db=db, schema=dog_schema, branch=default_branch)
    await dog1.new(db=db, name={"value": "Rocky", "owner": person1.id}, breed="Labrador", owner=person1)
    await dog1.save(db=db)

    dog2 = await Node.init(db=db, schema=dog_schema, branch=default_branch)
    await dog2.new(db=db, name={"value": "Lassie", "owner": person1.id}, breed="Collie", owner=person1)
    await dog2.save(db=db)
    assert not dog2.node_changelog.parent

    person1_update = await NodeManager.get_one(id=person1.id, db=db)
    await person1_update.delete(db=db)

    animals = person1_update.node_changelog.relationships["animals"].peers
    assert RelationshipPeerChangelog(peer_id=dog1.id, peer_kind="TestDog", peer_status=DiffAction.REMOVED) in animals
    assert RelationshipPeerChangelog(peer_id=dog2.id, peer_kind="TestDog", peer_status=DiffAction.REMOVED) in animals

    relationship_changelogs = RelationshipChangelogGetter(db=db, branch=default_branch)
    secondary_changelogs = await relationship_changelogs.get_changelogs(primary_changelog=person1_update.node_changelog)

    assert len(secondary_changelogs) == 2
    for changelog in secondary_changelogs:
        assert isinstance(changelog.relationships["owner"], RelationshipCardinalityOneChangelog)
        assert changelog.relationships["owner"].peer_kind_previous == "TestPerson"
        assert changelog.relationships["owner"].peer_status == DiffAction.REMOVED


async def test_node_changelog_parent(db: InfrahubDatabase, default_branch, car_person_schema: None) -> None:
    """Validate that parents are registrered in the node_changelog for parent/component relationships."""
    person1 = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person1.new(db=db, name="Jack")
    await person1.save(db=db)

    person2 = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person2.new(db=db, name="Jill")
    await person2.save(db=db)

    # Person 1 should be identified as the parent on creation
    car1 = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car1.new(db=db, name="Volvo", owner=person1)
    await car1.save(db=db)
    assert car1.node_changelog.parent
    assert car1.node_changelog.parent.node_id == person1.id
    assert car1.node_changelog.parent.node_kind == "TestPerson"

    # Person 1 should be identified as the parent on update even though the relationship wasn't modified
    car1_update1 = await NodeManager.get_one(id=car1.id, db=db)
    car1_update1.color.value = "Blue"
    await car1_update1.save(db=db)
    assert sorted(car1_update1.node_changelog.attributes.keys()) == ["color", "display_label"]
    assert not car1_update1.node_changelog.relationships
    assert car1_update1.node_changelog.parent
    assert car1_update1.node_changelog.parent.node_id == person1.id
    assert car1_update1.node_changelog.parent.node_kind == "TestPerson"

    # Person 1 should be identified as the parent on update even though the relationship wasn't modified and the .save()
    # method was called with a fields filter
    car1_update2 = await NodeManager.get_one(id=car1.id, db=db)
    car1_update2.nbr_seats.value = 5
    await car1_update2.save(db=db, fields=["nbr_seats"])
    assert sorted(car1_update2.node_changelog.attributes.keys()) == ["nbr_seats"]
    assert not car1_update2.node_changelog.relationships
    assert car1_update2.node_changelog.parent
    assert car1_update2.node_changelog.parent.node_id == person1.id
    assert car1_update2.node_changelog.parent.node_kind == "TestPerson"

    # Person 2 should be identified as the parent on update even after the owner is changed
    # method was called with a fields filter
    car1_update3 = await NodeManager.get_one(id=car1.id, db=db)
    await car1_update3.owner.update(data=person2, db=db)
    await car1_update3.save(db=db, fields=["owner"])
    assert not car1_update3.node_changelog.attributes
    assert sorted(car1_update3.node_changelog.relationships.keys()) == ["owner"]
    assert car1_update3.node_changelog.parent
    assert car1_update3.node_changelog.parent.node_id == person2.id
    assert car1_update3.node_changelog.parent.node_kind == "TestPerson"

    # Person 2 is still identified as the owner when the node is deleted
    car1_delete1 = await NodeManager.get_one(id=car1.id, db=db)
    await car1_delete1.delete(db=db)
    assert car1_delete1.node_changelog.parent.node_id == person2.id
    assert car1_delete1.node_changelog.parent.node_kind == "TestPerson"
