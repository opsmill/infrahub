from typing import Any

import pytest

from infrahub import config
from infrahub.core import registry
from infrahub.core.branch.models import Branch
from infrahub.core.constants import InfrahubKind, MetadataOptions, RelationshipKind, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.definitions.core.group import core_group, core_standard_group
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.constants import TestKind
from tests.helpers.graphql import graphql
from tests.helpers.schema import CAR_SCHEMA, DEVICE_SCHEMA


async def test_create_simple_object(db: InfrahubDatabase, default_branch: Branch, car_person_schema: None) -> None:
    query = """
    mutation {
        TestPersonCreate(data: {name: { value: "John"}, height: {value: 182}}) {
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
    assert result.data["TestPersonCreate"]["ok"] is True

    person_id = result.data["TestPersonCreate"]["object"]["id"]
    assert len(person_id) == 36  # length of an UUID

    person = await NodeManager.get_one(db=db, id=person_id)
    assert person.name.is_default is False
    assert person.height.is_default is False


async def test_create_simple_object_with_ok_return(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: None
) -> None:
    query = """
    mutation {
        TestPersonCreate(data: {name: { value: "John"}, height: {value: 182}}) {
            ok
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
    assert result.data["TestPersonCreate"]["ok"] is True


async def test_create_with_id(db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch) -> None:
    uuid1 = "79c83773-6b23-4537-a3ce-b214b625ff1d"
    query = (
        """
    mutation {
        TestPersonCreate(data: {id: "%s", name: { value: "John"}, height: {value: 182}}) {
            ok
            object {
                id
            }
        }
    }
    """
        % uuid1
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
    assert result.data["TestPersonCreate"]["ok"] is True
    assert result.data["TestPersonCreate"]["object"]["id"] == uuid1

    query = """
    mutation {
        TestPersonCreate(data: {id: "not-valid", name: { value: "John"}, height: {value: 182}}) {
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
    assert "not-valid is not a valid UUID" in result.errors[0].message


async def test_create_check_unique(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)

    query = """
    mutation {
        TestPersonCreate(data: {name: { value: "John"}, height: {value: 182}}) {
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
    assert "Violates uniqueness constraint" in result.errors[0].message


async def test_create_check_unique_across_branch(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)

    query = """
    mutation {
        TestPersonCreate(data: {name: { value: "John"}, height: {value: 182}}) {
            ok
            object {
                id
            }
        }
    }
    """

    branch1 = await create_branch(branch_name="branch1", db=db)

    branch1.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch1)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert len(result.errors) == 1
    assert "Violates uniqueness constraint" in result.errors[0].message


async def test_create_check_unique_in_branch(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    branch1 = await create_branch(branch_name="branch1", db=db)

    p1 = await Node.init(db=db, schema="TestPerson", branch=branch1)
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)

    query = """
    mutation {
        TestPersonCreate(data: {name: { value: "John"}, height: {value: 182}}) {
            ok
            object {
                id
            }
        }
    }
    """
    branch1.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch1)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert len(result.errors) == 1
    assert "Violates uniqueness constraint" in result.errors[0].message


async def test_attr_optional_uniqueness_constraint_create(
    db: InfrahubDatabase, default_branch: Branch, optional_attr_uniqueness_constraint_schema: NodeSchema
) -> None:
    query = """
    mutation {
        TestAttrOptionalUniquenessSchemaCreate(
            data: {
                description: { value: "the name is null" }
            }
        ){
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
    assert result.errors[0].message == "Violates uniqueness constraint 'name-description'"


async def test_all_attributes(
    db: InfrahubDatabase, default_branch: Branch, all_attribute_types_schema: NodeSchema
) -> None:
    query = """
    mutation {
        TestAllAttributeTypesCreate(
            data: {
                name: { value: "obj1" }
                mystring: { value: "abc" }
                mybool: { value: false }
                myint: { value: 123 }
                mylist: { value: [ "1", 2, false ] }
                ipaddress: { value: "10.3.4.254/24" }
                prefix: { value: "10.3.4.0/24" }
            }
        ){
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
    assert result.data["TestAllAttributeTypesCreate"]["ok"] is True
    assert len(result.data["TestAllAttributeTypesCreate"]["object"]["id"]) == 36  # length of an UUID

    objs = await NodeManager.query(db=db, schema="TestAllAttributeTypes")
    obj1 = objs[0]

    assert obj1.mystring.value == "abc"
    assert obj1.mystring.is_default is False
    assert obj1.mybool.value is False
    assert obj1.mybool.is_default is False
    assert obj1.myint.value == 123
    assert obj1.myint.is_default is False
    assert obj1.mylist.value == ["1", 2, False]
    assert obj1.mylist.is_default is False
    assert obj1.ipaddress.value == "10.3.4.254/24"
    assert obj1.ipaddress.is_default is False
    assert obj1.prefix.value == "10.3.4.0/24"
    assert obj1.prefix.is_default is False


async def test_all_attributes_default_value(
    db: InfrahubDatabase, default_branch: Branch, all_attribute_default_types_schema: NodeSchema
) -> None:
    query = """
    mutation {
        TestAllAttributeTypesCreate(
            data: {
                name: { value: "obj1" }
                mystring: { value: "abc" }
                mybool: { value: false }
                myint: { value: 123 }
                mylist: { value: [ "1", 2, false ] }
            }
        ){
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
    assert result.data["TestAllAttributeTypesCreate"]["ok"] is True
    obj_id = result.data["TestAllAttributeTypesCreate"]["object"]["id"]
    assert len(obj_id) == 36  # length of an UUID

    obj1 = await NodeManager.get_one(db=db, id=obj_id)

    assert obj1.mystring.value == "abc"
    assert obj1.mystring.is_default is False
    assert obj1.mybool.value is False
    assert obj1.mybool.is_default is False
    assert obj1.myint.value == 123
    assert obj1.myint.is_default is False
    assert obj1.mylist.value == ["1", 2, False]
    assert obj1.mylist.is_default is False

    assert obj1.mystring_default.value == "a string"
    assert obj1.mystring_default.is_default is True
    assert obj1.mybool_default.value is False
    assert obj1.mybool_default.is_default is True
    assert obj1.myint_default.value == 10
    assert obj1.myint_default.is_default is True
    assert obj1.mylist_default.value == [10, 11, 12]
    assert obj1.mylist_default.is_default is True

    assert obj1.mystring_none.value is None
    assert obj1.mystring_none.is_default is True
    assert obj1.mybool_none.value is None
    assert obj1.mybool_none.is_default is True
    assert obj1.myint_none.value is None
    assert obj1.myint_none.is_default is True
    assert obj1.mylist_none.value is None
    assert obj1.mylist_none.is_default is True


async def test_create_object_with_flag_property(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    query = """
    mutation {
        TestPersonCreate(
            data: {
                name: { value: "John", is_protected: true }
                height: { value: 182 }
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
    assert result.data["TestPersonCreate"]["ok"] is True
    assert len(result.data["TestPersonCreate"]["object"]["id"]) == 36  # length of an UUID

    # Query the newly created Node to ensure everything is as expected
    query = """
        query {
            TestPerson {
                edges {
                    node {
                        id
                        name {
                            value
                            is_protected
                        }
                    }
                }
            }
        }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result1 = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data
    assert result1.data["TestPerson"]["edges"][0]["node"]["name"]["is_protected"] is True


async def test_create_object_with_node_property(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
    first_account: Node,
    second_account: Node,
) -> None:
    query = """
    mutation {
        TestPersonCreate(
            data: {
                name: { value: "John", source: "%s" }
                height: { value: 182, owner: "%s" }
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
    assert result.data["TestPersonCreate"]["ok"] is True
    assert len(result.data["TestPersonCreate"]["object"]["id"]) == 36  # length of an UUID

    # Query the newly created Node to ensure everything is as expected
    query = """
        query {
            TestPerson {
                edges {
                    node {
                        id
                        name {
                            value
                            source {
                                id
                                display_label
                            }
                        }
                        height {
                            id
                            owner {
                                id
                                display_label
                            }
                        }
                    }
                }
            }
        }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result1 = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result1.errors is None
    assert result1.data
    assert result1.data["TestPerson"]["edges"][0]["node"]["name"]["source"]["id"] == first_account.id
    assert (
        result1.data["TestPerson"]["edges"][0]["node"]["name"]["source"]["display_label"]
        == await first_account.get_display_label()
    )
    assert result1.data["TestPerson"]["edges"][0]["node"]["height"]["owner"]["id"] == second_account.id
    assert (
        result1.data["TestPerson"]["edges"][0]["node"]["height"]["owner"]["display_label"]
        == await second_account.get_display_label()
    )


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


async def test_create_person_not_valid(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    query = """
    mutation {
        TestPersonCreate(data: {
            name: { value: "John"},
            height: {value: "182"}
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

    assert result.errors
    assert len(result.errors) == 1
    assert result.errors[0].message == "Expected value of type 'BigInt', found \"182\"."


async def test_create_with_attribute_not_valid(
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
            color: { value: "#44444444" },
            is_electric: { value: true },
            owner: { id: "John" },
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

    assert result.errors
    assert len(result.errors) == 1
    assert "#44444444 must have a maximum length of 7 at color" in result.errors[0].message


async def test_create_with_uniqueness_constraint_violation(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    car_schema = schema_branch.get("TestCar", duplicate=True)
    car_schema.uniqueness_constraints = [["owner", "color"]]
    schema_branch.set(name="TestCar", schema=car_schema)

    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="Bruce Wayne", height=180)
    await p1.save(db=db)
    c1 = await Node.init(db=db, schema="TestCar")
    await c1.new(db=db, name="Batmobile", is_electric=False, nbr_seats=3, color="#123456", owner=p1)
    await c1.save(db=db)

    query = """
    mutation {
        TestCarCreate(data: {
            name: { value: "Batcycle" },
            nbr_seats: { value: 1 },
            color: { value: "#123456" },
            is_electric: { value: true },
            owner: { id: "Bruce Wayne" },
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
    assert result.errors
    assert len(result.errors) == 1
    assert "Violates uniqueness constraint 'owner-color'" in result.errors[0].message


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


async def test_create_valid_datetime_success(
    db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema
) -> None:
    query = """
    mutation {
        TestCriticalityCreate(data: {name: { value: "HIGH"}, level: {value: 1}, time: {value: "2021-01-01T00:00:00Z"}}) {
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
    assert result.data["TestCriticalityCreate"]["ok"] is True
    crit = await NodeManager.get_one(db=db, id=result.data["TestCriticalityCreate"]["object"]["id"])
    assert crit.time.value == "2021-01-01T00:00:00Z"
    assert crit.time.is_default is False
    assert crit.name.value == "HIGH"
    assert crit.level.value == 1


async def test_create_valid_datetime_failure(
    db: InfrahubDatabase, default_branch: Branch, criticality_schema: NodeSchema
) -> None:
    query = """
    mutation {
        TestCriticalityCreate(data: {name: { value: "HIGH"}, level: {value: 1}, time: {value: "10:1010"}}) {
            ok
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
    assert result.data
    assert result.errors
    assert result.errors[0].args[0] == "10:1010 is not a valid DateTime at time"
    assert result.data["TestCriticalityCreate"] is None


async def test_create_with_object_template(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, branch: Branch
) -> None:
    registry.schema.register_schema(schema=DEVICE_SCHEMA, branch=branch.name)
    branch.update_schema_hash()

    query = """
    mutation NewDevice($device_name: String!, $template_id: String!) {
      TestingDeviceCreate(data: {
        object_template: {id: $template_id}
        name: {value: $device_name}
      }) {
        ok
        object {
          id
        }
      }
    }
    """
    gql_params = await prepare_graphql_params(db=db, branch=branch)

    # Random non-existing ID for template
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"device_name": "th2.par.asbr01", "template_id": "b1dd214b-befd-47ef-8af3-675fd28b1ea3"},
    )
    assert "Unable to find the object template in the database" in result.errors[0].message

    device_template: Node = await Node.init(schema=f"Template{TestKind.DEVICE}", db=db, branch=branch)
    await device_template.new(
        db=db, template_name="MX204 Router", manufacturer="Juniper", height=1, weight=0, airflow="Front to rear"
    )
    await device_template.save(db=db)

    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"device_name": "th2.par.asbr01", "template_id": device_template.id},
    )
    assert not result.errors

    device = await NodeManager.get_one(
        db=db,
        kind=TestKind.DEVICE,
        branch=branch,
        id=result.data[f"{TestKind.DEVICE}Create"]["object"]["id"],
        include_metadata=MetadataOptions.SOURCE,
    )
    assert device
    assert device.name.value == "th2.par.asbr01"
    # Validate object is linked to object template
    device_template_node = await device.object_template.get_peer(db=db)
    assert device_template_node.id == device_template.id
    # No interfaces as there are none on the object template
    device_interfaces = await device.interfaces.get_peers(db=db)
    assert not device_interfaces
    # verify attributes and metadata
    assert device.manufacturer.value == "Juniper"
    assert device.manufacturer.is_default is False
    assert device.manufacturer.source_id == device_template.id
    assert device.height.value == 1
    assert device.height.is_default is False
    assert device.height.source_id == device_template.id
    assert device.weight.value == 0
    assert device.weight.is_default is False
    assert device.weight.source_id == device_template.id
    assert device.airflow.value.value == "Front to rear"
    assert device.airflow.is_default is False
    assert device.airflow.source_id == device_template.id
    assert device.part_number.value is None
    assert device.part_number.is_default is True
    assert device.part_number.source_id is None

    # Create interfaces on object template
    if_names = ["et-0/0/0", "et-0/0/1", "et-0/0/2", "et-0/0/3"]
    interface_templates_by_name: dict[str, Node] = {}
    for if_name in if_names:
        interface_template: Node = await Node.init(
            schema=f"Template{TestKind.PHYSICAL_INTERFACE}", db=db, branch=branch
        )
        await interface_template.new(
            db=db, template_name=f"MX204 {if_name}", device=device_template, name=if_name, phys_type="QSFP28 (100GE)"
        )
        await interface_template.save(db=db)
        interface_templates_by_name[if_name] = interface_template

    await device_template.interfaces.update(db=db, data=list(interface_templates_by_name.values()))
    await device_template.save(db=db)

    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"device_name": "th2.par.asbr02", "template_id": device_template.id},
    )
    assert not result.errors
    assert result.data

    device = await NodeManager.get_one(
        db=db, kind=TestKind.DEVICE, branch=branch, id=result.data[f"{TestKind.DEVICE}Create"]["object"]["id"]
    )
    assert device
    assert device.name.value == "th2.par.asbr02"
    # Validate object is linked to object template
    device_template_node = await device.object_template.get_peer(db=db)
    assert device_template_node.id == device_template.id
    # Validate that interfaces relationship has been populated according to object template
    interfaces = await NodeManager.query(
        db=db, branch=branch, schema=TestKind.PHYSICAL_INTERFACE, include_metadata=MetadataOptions.SOURCE
    )
    assert len(interfaces) == len(if_names)
    device_interfaces = await device.interfaces.get_peers(db=db)
    assert len(device_interfaces) == len(if_names)
    assert sorted([interface.name.value for interface in device_interfaces.values()]) == if_names
    # verify attributes and metadata on interfaces
    for interface in interfaces:
        assert interface.name.value in ["et-0/0/0", "et-0/0/1", "et-0/0/2", "et-0/0/3"]
        template_obj = interface_templates_by_name[interface.name.value]
        assert interface.name.is_default is False
        assert interface.name.source_id == template_obj.id
        assert interface.phys_type.value.value == "QSFP28 (100GE)"
        assert interface.phys_type.is_default is False
        assert interface.phys_type.source_id == template_obj.id
        assert interface.enabled.value is True
        assert interface.enabled.is_default is True
        assert interface.enabled.source_id is None

    # Add a SFP to each interface of the object template
    template_interfaces = await device_template.interfaces.get_peers(db=db)
    sfp_templates_by_interface_name: dict[str, Node] = {}
    for interface in template_interfaces.values():
        sfp_template: Node = await Node.init(schema=f"Template{TestKind.SFP}", db=db, branch=branch)
        await sfp_template.new(
            db=db,
            template_name=f"QSFP {interface.name.value}",
            interface=interface,
            phys_type="QSFP28 (100GE)",
            serial_number=f"QSFP-{interface.name.value}",
        )
        await sfp_template.save(db=db)
        sfp_templates_by_interface_name[interface.name.value] = sfp_template

    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"device_name": "th2.par.asbr03", "template_id": device_template.id},
    )
    assert not result.errors

    assert result.data
    device = await NodeManager.get_one(
        db=db, kind=TestKind.DEVICE, branch=branch, id=result.data[f"{TestKind.DEVICE}Create"]["object"]["id"]
    )
    assert device
    assert device.name.value == "th2.par.asbr03"
    # Validate object is linked to object template
    device_template_node = await device.object_template.get_peer(db=db)
    assert device_template_node.id == device_template.id
    # Validate that interfaces relationship has been populated according to object template
    device_interfaces = await device.interfaces.get_peers(db=db)
    assert len(device_interfaces) == len(if_names)
    assert sorted([interface.name.value for interface in device_interfaces.values()]) == if_names
    # Validate that one SFP is attached to each interface
    device_sfps = [await interface.sfp.get_peer(db=db) for interface in device_interfaces.values()]
    assert len(device_sfps) == len(if_names)
    sfp_interfaces = [await sfp.interface.get_peer(db=db) for sfp in device_sfps]
    assert sorted([interface.name.value for interface in sfp_interfaces]) == if_names
    # verify attributes and metadata on SFPs
    for sfp in device_sfps:
        interface_name = sfp.serial_number.value.split("-", 1)[1]
        template_obj = sfp_templates_by_interface_name[interface_name]
        assert sfp.phys_type.value.value == "QSFP28 (100GE)"
        assert sfp.phys_type.is_default is False
        assert sfp.phys_type.source_id == template_obj.id
        assert sfp.serial_number.value == f"QSFP-{interface_name}"
        assert sfp.serial_number.is_default is False
        assert sfp.serial_number.source_id == template_obj.id
        assert sfp.part_number.value is None
        assert sfp.part_number.is_default is True
        assert sfp.part_number.source_id is None


async def test_create_with_object_template_and_real_object(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, branch: Branch
) -> None:
    """
    Test that relationships on sub-templates will correctly link the created sub-object to an existing object on non-component relationships
    """
    updated_car_schema = CAR_SCHEMA.duplicate()
    manufacturer_schema = updated_car_schema.get(name=TestKind.MANUFACTURER)
    manufacturer_schema.generate_template = True
    cars_rel = manufacturer_schema.get_relationship(name="cars")
    cars_rel.kind = RelationshipKind.COMPONENT
    person_schema = updated_car_schema.get(name=TestKind.PERSON)
    person_schema.generate_template = True
    car_schema = updated_car_schema.get(name=TestKind.CAR)
    car_schema.generate_template = True
    manufacturer_rel = car_schema.get_relationship(name="manufacturer")
    manufacturer_rel.kind = RelationshipKind.PARENT
    registry.schema.register_schema(schema=updated_car_schema, branch=branch.name)

    manufacturer_object = await Node.init(schema=TestKind.MANUFACTURER, db=db, branch=branch)
    await manufacturer_object.new(db=db, name="Hark Motors")
    await manufacturer_object.save(db=db)

    person_object = await Node.init(schema=TestKind.PERSON, db=db, branch=branch)
    await person_object.new(db=db, name="John", height=180)
    await person_object.save(db=db)

    car_object = await Node.init(schema=TestKind.CAR, db=db, branch=branch)
    await car_object.new(db=db, name="Accord", manufacturer=manufacturer_object, owner=person_object, color="blurple")
    await car_object.save(db=db)

    manufacturer_template: Node = await Node.init(schema=f"Template{TestKind.MANUFACTURER}", db=db, branch=branch)
    await manufacturer_template.new(db=db, template_name="m_template", customers=[person_object])
    await manufacturer_template.save(db=db)

    car_template_with_person_object = await Node.init(schema=f"Template{TestKind.CAR}", db=db, branch=branch)
    await car_template_with_person_object.new(
        db=db,
        template_name="c_template",
        name="Civic",
        color="blurple",
        manufacturer=manufacturer_template,
        owner=person_object,
    )
    await car_template_with_person_object.save(db=db)

    create_manufacturer_with_template_query = """
    mutation CreateManufacturerWithTemplate($manufacturer_name: String!, $template_id: String!) {
      TestingManufacturerCreate(data: {
        name: {value: $manufacturer_name}
        object_template: {id: $template_id}
      }) {
        ok
        object {
          id
        }
      }
    }
    """
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=create_manufacturer_with_template_query,
        context_value=gql_params.context,
        variable_values={"manufacturer_name": "Fresh Motors", "template_id": manufacturer_template.id},
    )
    assert not result.errors
    new_manufacturer = await NodeManager.get_one(
        db=db,
        kind=TestKind.MANUFACTURER,
        branch=branch,
        id=result.data[f"{TestKind.MANUFACTURER}Create"]["object"]["id"],
    )
    assert new_manufacturer
    assert new_manufacturer.name.value == "Fresh Motors"
    customers_peers = await new_manufacturer.customers.get_peers(db=db)
    assert len(customers_peers) == 1
    customers_by_name = {person.name.value: person for person in customers_peers.values()}
    # check non-template person
    non_template_person = customers_by_name["John"]
    assert non_template_person.id == person_object.id

    cars_peers = await new_manufacturer.cars.get_peers(db=db)
    assert len(cars_peers) == 1
    cars_by_name = {car.name.value: car for car in cars_peers.values()}
    # check car template with person object
    car_template_with_person_object = cars_by_name["Civic"]
    assert car_template_with_person_object.color.value == "blurple"
    car_manufacturer = await car_template_with_person_object.manufacturer.get_peer(db=db)
    assert car_manufacturer.id == new_manufacturer.id
    car_owner = await car_template_with_person_object.owner.get_peer(db=db)
    assert car_owner.id == person_object.id


async def test_create_without_object_template(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, branch: Branch
) -> None:
    registry.schema.register_schema(schema=DEVICE_SCHEMA, branch=branch.name)
    branch.update_schema_hash()

    query = """
    mutation NewDevice($device_name: String!, $manufacturer: String!) {
      TestingDeviceCreate(data: {
        name: {value: $device_name}
        manufacturer: {value: $manufacturer}
        height: {value: 1}
        weight: {value: 6}
        airflow: {value: "Front to rear"}
      }) {
        ok
        object {
          id
        }
      }
    }
    """
    gql_params = await prepare_graphql_params(db=db, branch=branch)

    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"device_name": "th2.par.asbr01", "manufacturer": "Juniper"},
    )
    assert not result.errors

    device = await NodeManager.get_one(
        db=db, kind=TestKind.DEVICE, branch=branch, id=result.data[f"{TestKind.DEVICE}Create"]["object"]["id"]
    )
    assert device
    assert device.name.value == "th2.par.asbr01"
    # Validate object not is linked to object template
    device_template_node = await device.object_template.get_peer(db=db)
    assert not device_template_node


async def test_create_sub_object_template_by_hfid(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, branch: Branch
) -> None:
    registry.schema.register_schema(schema=DEVICE_SCHEMA, branch=branch.name)
    branch.update_schema_hash()

    device_template = await Node.init(db=db, schema=f"Template{TestKind.DEVICE}", branch=branch)
    await device_template.new(
        db=db, template_name="MX204 Router", manufacturer="Juniper", height=1, weight=6, airflow="Front to rear"
    )
    await device_template.save(db=db)
    device_template_hfid = await device_template.get_hfid(db=db)

    template = await registry.manager.get_one_by_hfid(
        db=db, branch=branch, kind=f"Template{TestKind.INTERFACE_HOLDER}", hfid=device_template_hfid
    )
    assert device_template.id == template.id

    query = """
    mutation CreateTemplateInterfaceWithHFID($template_name: String!, $device_template_hfid: [String!], $name: String!, $phys_type: String!) {
      TemplateTestingPhysicalInterfaceCreate(
        data:{
          template_name: {value: $template_name}
          device: {hfid: $device_template_hfid}
          name: {value: $name}
          phys_type: {value: $phys_type}
        }
      ) {
        ok
        object {
          id
        }
      }
    }
    """

    gql_params = await prepare_graphql_params(db=db, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "template_name": "MX204 et-0/0/0",
            "device_template_hfid": device_template_hfid,
            "name": "et-0/0/0",
            "phys_type": "QSFP28 (100GE)",
        },
    )
    assert not result.errors

    node_id = result.data["TemplateTestingPhysicalInterfaceCreate"]["object"]["id"]
    assert node_id

    interface_template = await registry.manager.get_one(db=db, branch=branch, id=node_id)
    assert interface_template
    assert (await interface_template.device.get_peer(db=db)).id == device_template.id


# These tests have been moved at the end of the file to avoid colliding with other and breaking them


@pytest.mark.parametrize(
    "graphql_enums_on,enum_value,response_value", [(True, "MANUAL", "MANUAL"), (False, '"manual"', "manual")]
)
async def test_create_simple_object_with_enum(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_john_main: Node,
    car_person_schema: SchemaBranch,
    graphql_enums_on: bool,
    enum_value: str,
    response_value: str,
    reset_graphql_schema_between_tests: Any,
) -> None:
    config.SETTINGS.experimental_features.graphql_enums = graphql_enums_on
    query = """
    mutation {
        TestCarCreate(data: {
                name: { value: "JetTricycle"},
                nbr_seats: { value: 1 },
                is_electric: { value: false },
                transmission: { value: %s },
                owner: { id: "John" }
            }) {
            ok
            object {
                id
                transmission {
                    value
                }
            }
        }
    }
    """ % (enum_value)
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
    assert result.data["TestCarCreate"]["object"]["transmission"]["value"] == response_value

    car_id = result.data["TestCarCreate"]["object"]["id"]
    database_car = await NodeManager.get_one(db=db, id=car_id)
    assert database_car.transmission.value.value == "manual"


async def test_create_enum_when_enums_off_fails(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_john_main: Node,
    car_person_schema: SchemaBranch,
) -> None:
    config.SETTINGS.experimental_features.graphql_enums = False
    query = """
    mutation {
        TestCarCreate(data: {
                name: { value: "JetTricycle"},
                nbr_seats: { value: 1 },
                is_electric: { value: false },
                transmission: { value: MANUAL },
                owner: { id: "John" }
            }) {
            ok
            object {
                id
                transmission {
                    value
                }
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
    assert "String cannot represent a non string value" in result.errors[0].message


async def test_create_string_when_enums_on_fails(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_john_main: Node,
    car_person_schema: SchemaBranch,
    reset_graphql_schema_between_tests: Any,
) -> None:
    config.SETTINGS.experimental_features.graphql_enums = True
    query = """
    mutation {
        TestCarCreate(data: {
                name: { value: "JetTricycle"},
                nbr_seats: { value: 1 },
                is_electric: { value: false },
                transmission: { value: "manual" },
                owner: { id: "John" }
            }) {
            ok
            object {
                id
                transmission {
                    value
                }
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
    assert "'TestCarTransmissionValue' cannot represent non-enum value" in result.errors[0].message
