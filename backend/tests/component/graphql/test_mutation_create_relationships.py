from infrahub.core import registry
from infrahub.core.branch.models import Branch
from infrahub.core.constants import InfrahubKind, MetadataOptions, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.definitions.core.group import core_group, core_standard_group
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql


async def test_create_object_with_single_relationship(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)

    query = """
    mutation {
        TestCarCreate(
            data: {
                name: { value: "Accord" }
                nbr_seats: { value: 5 }
                is_electric: { value: false }
                owner: { id: "John" }
            }
        ) {
            ok
            object {
                id
            }
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert result.data["TestCarCreate"]["ok"] is True
    assert len(result.data["TestCarCreate"]["object"]["id"]) == 36  # length of an UUID


async def test_create_object_with_invalid_single_relationship_fails(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_schema: None
) -> None:
    query = """
    mutation {
        LocationSiteCreate(
            data: {
                name: { value: "NewSite" },
                parent: { hfid: ["pretend region"] }
            }
        ) {
            ok
            object {
                id
            }
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert result.errors
    assert len(result.errors) == 1
    gql_error = result.errors[0]
    assert "Unable to find the node pretend region / LocationRegion in the database." in gql_error.message


async def test_create_object_with_single_relationship_flag_property(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)

    query = """
    mutation {
        TestCarCreate(data: {
            name: { value: "Accord" },
            nbr_seats: { value: 5 },
            is_electric: { value: false },
            owner: { id: "John", _relation__is_protected: true }
        }) {
            ok
            object {
                id
            }
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert result.data["TestCarCreate"]["ok"] is True
    assert len(result.data["TestCarCreate"]["object"]["id"]) == 36

    car = await NodeManager.get_one(db=db, id=result.data["TestCarCreate"]["object"]["id"])
    rm = await car.owner.get(db=db)
    assert rm.is_protected is True


async def test_create_object_with_single_relationship_node_property(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
    first_account: Node,
    second_account: Node,
) -> None:
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)

    query = (
        """
    mutation {
        TestCarCreate(
            data: {
                name: { value: "Accord" }
                nbr_seats: { value: 5 }
                is_electric: { value: false }
                owner: { id: "John", _relation__owner: "%s" }
            }
        ) {
            ok
            object {
                id
            }
        }
    }
    """
        % first_account.id
    )
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert result.data["TestCarCreate"]["ok"] is True
    assert len(result.data["TestCarCreate"]["object"]["id"]) == 36

    car = await NodeManager.get_one(db=db, id=result.data["TestCarCreate"]["object"]["id"])
    rm = await car.owner.get(db=db)
    owner = await rm.get_owner(db=db)
    assert isinstance(owner, Node)
    assert owner.id == first_account.id


async def test_create_object_with_multiple_relationships(
    db: InfrahubDatabase, default_branch: Branch, fruit_tag_schema: SchemaRoot
) -> None:
    t1 = await Node.init(db=db, schema=InfrahubKind.TAG)
    await t1.new(db=db, name="tag1")
    await t1.save(db=db)
    t2 = await Node.init(db=db, schema=InfrahubKind.TAG)
    await t2.new(db=db, name="tag2")
    await t2.save(db=db)
    t3 = await Node.init(db=db, schema=InfrahubKind.TAG)
    await t3.new(db=db, name="tag3")
    await t3.save(db=db)

    query = """
    mutation {
        GardenFruitCreate(
            data: {
                name: { value: "apple" }
                tags: [{ id: "tag1" }, { id: "tag2" }, { id: "tag3" }]
            }
        ) {
            ok
            object {
                id
            }
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert result.data["GardenFruitCreate"]["ok"] is True
    assert len(result.data["GardenFruitCreate"]["object"]["id"]) == 36  # length of an UUID

    fruit = await NodeManager.get_one(db=db, id=result.data["GardenFruitCreate"]["object"]["id"])
    assert len(await fruit.tags.get(db=db)) == 3


async def test_create_object_with_multiple_relationships_with_node_property(
    db: InfrahubDatabase,
    default_branch: Branch,
    fruit_tag_schema: SchemaRoot,
    first_account: Node,
    second_account: Node,
) -> None:
    t1 = await Node.init(db=db, schema=InfrahubKind.TAG)
    await t1.new(db=db, name="tag1")
    await t1.save(db=db)
    t2 = await Node.init(db=db, schema=InfrahubKind.TAG)
    await t2.new(db=db, name="tag2")
    await t2.save(db=db)
    t3 = await Node.init(db=db, schema=InfrahubKind.TAG)
    await t3.new(db=db, name="tag3")
    await t3.save(db=db)

    query = """
    mutation {
        GardenFruitCreate(
            data: {
                name: { value: "apple" }
                tags: [
                    { id: "tag1", _relation__source: "%s" }
                    { id: "tag2", _relation__owner: "%s" }
                    { id: "tag3", _relation__source: "%s", _relation__owner: "%s" }
                ]
            }
        ) {
            ok
            object {
                id
            }
        }
    }
    """ % (
        first_account.id,
        second_account.id,
        first_account.id,
        second_account.id,
    )
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert result.data["GardenFruitCreate"]["ok"] is True
    assert len(result.data["GardenFruitCreate"]["object"]["id"]) == 36  # length of an UUID

    fruit = await NodeManager.get_one(
        db=db, id=result.data["GardenFruitCreate"]["object"]["id"], include_metadata=MetadataOptions.LINKED_NODES
    )
    tags = {tag.peer_id: tag for tag in await fruit.tags.get(db=db)}
    assert len(tags) == 3

    t1_source = await tags[t1.id].get_source(db=db)
    t1_owner = await tags[t1.id].get_owner(db=db)
    t2_source = await tags[t2.id].get_source(db=db)
    t2_owner = await tags[t2.id].get_owner(db=db)
    t3_source = await tags[t3.id].get_source(db=db)
    t3_owner = await tags[t3.id].get_owner(db=db)

    assert isinstance(t1_source, Node)
    assert t1_source.id == first_account.id
    assert t1_owner is None
    assert t2_source is None
    assert isinstance(t2_owner, Node)
    assert t3_owner.id == second_account.id
    assert isinstance(t3_source, Node)
    assert t3_source.id == first_account.id
    assert isinstance(t3_owner, Node)
    assert t3_owner.id == second_account.id


async def test_create_object_with_multiple_relationships_flag_property(
    db: InfrahubDatabase, default_branch: Branch, fruit_tag_schema: SchemaRoot
) -> None:
    t1 = await Node.init(db=db, schema=InfrahubKind.TAG)
    await t1.new(db=db, name="tag1")
    await t1.save(db=db)
    t2 = await Node.init(db=db, schema=InfrahubKind.TAG)
    await t2.new(db=db, name="tag2")
    await t2.save(db=db)
    t3 = await Node.init(db=db, schema=InfrahubKind.TAG)
    await t3.new(db=db, name="tag3")
    await t3.save(db=db)

    query = """
    mutation {
        GardenFruitCreate(
            data: {
                name: { value: "apple" }
                tags: [
                    { id: "tag1", _relation__is_protected: true }
                    { id: "tag2", _relation__is_protected: true }
                    { id: "tag3", _relation__is_protected: true }
                ]
            }
        ) {
            ok
            object {
                id
            }
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert result.data["GardenFruitCreate"]["ok"] is True
    assert len(result.data["GardenFruitCreate"]["object"]["id"]) == 36  # length of an UUID

    fruit = await NodeManager.get_one(db=db, id=result.data["GardenFruitCreate"]["object"]["id"])
    rels = await fruit.tags.get(db=db)
    assert len(rels) == 3
    assert rels[0].is_protected is True
    assert rels[1].is_protected is True
    assert rels[2].is_protected is True


async def test_create_relationship_for_node_with_migrated_kind(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_internal_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
    person_alfred_main: Node,
) -> None:
    schema = SchemaRoot(generics=[core_group], nodes=[core_standard_group])
    registry.schema.register_schema(schema=schema, branch=default_branch.name)
    default_branch.update_schema_hash()

    branch = await create_branch(db=db, branch_name="migrated-branch")
    schema = registry.schema.get_schema_branch(name=branch.name)
    person_schema = schema.get(name="TestPerson")
    person_schema.name = "GreatPerson"
    new_person_kind = "TestGreatPerson"
    assert person_schema.kind == new_person_kind
    registry.schema.set(name=new_person_kind, schema=person_schema, branch=branch.name)
    migration = NodeKindUpdateMigration(
        previous_node_schema=schema.get(name="TestPerson"),
        new_node_schema=person_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=new_person_kind, field_name="name"),
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=branch)
    assert not execution_result.errors
    core_node_schema = schema.get_generic(name="CoreNode")
    core_node_schema.used_by.append(new_person_kind)
    schema.set(name="CoreNode", schema=core_node_schema)
    await registry.schema.load_schema_to_db(db=db, schema=schema, branch=branch)

    # create group on main
    group_create_query = """
    mutation ($id: String!, $name: String!) {
        CoreStandardGroupCreate(data: {
            name: { value: $name},
            group_type: { value: "internal" },
            members: { id: $id }
        }) {
            ok
            object {
                id
            }
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=group_create_query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": person_alfred_main.id, "name": "main-group"},
    )
    assert not result.errors
    assert result.data
    main_group_id = result.data["CoreStandardGroupCreate"]["object"]["id"]

    # create group on branch
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=group_create_query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": person_alfred_main.id, "name": "branch-group"},
    )
    assert not result.errors
    assert result.data
    branch_group_id = result.data["CoreStandardGroupCreate"]["object"]["id"]

    # check relationship count on main
    group_members_query = """
    query getRelationshipCount_CoreStandardGroup_members ($ids: [ID!]!) {
        CoreStandardGroup(
            ids: $ids
        ) {
            edges {
                node {
                    members {
                        count
                    }
                }
            }
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=group_members_query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"ids": [main_group_id]},
    )
    assert not result.errors
    assert result.data
    assert result.data["CoreStandardGroup"]["edges"][0]["node"]["members"]["count"] == 1

    # check relationship count on branch
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=group_members_query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"ids": [branch_group_id]},
    )
    assert not result.errors
    assert result.data
    assert result.data["CoreStandardGroup"]["edges"][0]["node"]["members"]["count"] == 1

    # check person-side relationship on main
    person_main = await NodeManager.get_one(db=db, id=person_alfred_main.id, branch=default_branch)
    groups = await person_main.member_of_groups.get(db=db)
    assert len(groups) == 1
    assert groups[0].peer_id == main_group_id
    main_person_schema = registry.schema.get(name="TestPerson", branch=default_branch, duplicate=False)
    members_rel_schema = main_person_schema.get_relationship("member_of_groups")
    peer_count = await NodeManager.count_peers(
        db=db,
        ids=[person_alfred_main.id],
        source_kind="TestPerson",
        schema=members_rel_schema,
        filters={},
        branch=default_branch,
    )
    assert peer_count == 1

    # check group-side relationship on main
    group_main = await NodeManager.get_one(db=db, id=main_group_id, branch=default_branch)
    members = await group_main.members.get(db=db)
    assert len(members) == 1
    assert members[0].peer_id == person_alfred_main.id
    main_group_schema = registry.schema.get(name="CoreStandardGroup", branch=default_branch, duplicate=False)
    members_rel_schema = main_group_schema.get_relationship("members")
    peer_count = await NodeManager.count_peers(
        db=db,
        ids=[main_group_id],
        source_kind="CoreStandardGroup",
        schema=members_rel_schema,
        filters={},
        branch=default_branch,
    )
    assert peer_count == 1

    # check person-side relationship on branch
    alfred_branch = await NodeManager.get_one(db=db, id=person_alfred_main.id, branch=branch)
    groups = await alfred_branch.member_of_groups.get(db=db)
    assert len(groups) == 1
    assert groups[0].peer_id == branch_group_id
    branch_person_schema = registry.schema.get(name="TestGreatPerson", branch=branch, duplicate=False)
    members_rel_schema = branch_person_schema.get_relationship("member_of_groups")
    peer_count = await NodeManager.count_peers(
        db=db,
        ids=[person_alfred_main.id],
        source_kind="TestGreatPerson",
        schema=members_rel_schema,
        filters={},
        branch=branch,
    )
    assert peer_count == 1

    # check group-side relationship on branch
    group_branch = await NodeManager.get_one(db=db, id=branch_group_id, branch=branch)
    members = await group_branch.members.get(db=db)
    assert len(members) == 1
    assert members[0].peer_id == person_alfred_main.id
    branch_group_schema = registry.schema.get(name="CoreStandardGroup", branch=branch, duplicate=False)
    members_rel_schema = branch_group_schema.get_relationship("members")
    peer_count = await NodeManager.count_peers(
        db=db,
        ids=[branch_group_id],
        source_kind="CoreStandardGroup",
        schema=members_rel_schema,
        filters={},
        branch=branch,
    )
    assert peer_count == 1


async def test_relationship_with_hfid(
    db: InfrahubDatabase, default_branch: Branch, animal_person_schema: SchemaRoot
) -> None:
    person_schema = animal_person_schema.get(name="TestPerson")

    person1 = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await person1.new(db=db, name="Jack")
    await person1.save(db=db)

    query = """
    mutation {
        TestDogCreate(data: {
            name: { value: "Rocky" },
            breed: { value: "Labrador" },
            color: { value: "black" },
            owner: { hfid: ["Jack"] },
        }) {
            ok
            object {
                id
            }
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert result.errors is None
    assert result.data
    assert result.data["TestDogCreate"]["ok"] is True
    assert result.data["TestDogCreate"]["object"]["id"]


async def test_incorrect_peer_type_prevented(
    db: InfrahubDatabase, default_branch: Branch, animal_person_schema: SchemaRoot
) -> None:
    person_schema = animal_person_schema.get(name="TestPerson")
    dog_schema = animal_person_schema.get(name="TestDog")

    person1 = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await person1.new(db=db, name="Jack")
    await person1.save(db=db)

    person2 = await Node.init(db=db, schema=person_schema, branch=default_branch)
    await person2.new(db=db, name="Jill")
    await person2.save(db=db)

    dog1 = await Node.init(db=db, schema=dog_schema, branch=default_branch)
    await dog1.new(db=db, name="Rocky", breed="Labrador", owner=person1)
    await dog1.save(db=db)

    dog2 = await Node.init(db=db, schema=dog_schema, branch=default_branch)
    await dog2.new(db=db, name="Hank", breed="Chow", owner=person2)
    await dog2.save(db=db)

    query = """
    mutation {
        TestPersonCreate(data: {name: { value: "Herb"}, height: {value: 182}, animals: [{id: "%(animal_id)s"}]}) {
            ok
            object {
                id
            }
        }
    }
    """ % {"animal_id": person2.id}
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert result.errors is not None
    assert len(result.errors) == 1
    assert (
        result.errors[0].message
        == f"""TestPerson - {person2.id} cannot be added to relationship, must be of type: ['TestCat', 'TestDog'] at animals"""
    )

    query = """
    mutation {
        TestDogCreate(data: {
            name: { value: "Rocky" },
            breed: { value: "Labrador" },
            color: { value: "black" },
            owner: { id: "%(owner_id)s" },
        }) {
            ok
            object {
                id
            }
        }
    }
    """ % {"owner_id": dog2.id}
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert result.errors is not None
    assert len(result.errors) == 1
    assert (
        result.errors[0].message
        == f"""TestDog - {dog2.id} cannot be added to relationship, must be of type: ['TestPerson'] at owner"""
    )
