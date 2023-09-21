import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema, SchemaRoot
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import count_relationships, get_paths_between_nodes
from infrahub.exceptions import ValidationError


async def test_node_init(session, default_branch: Branch, criticality_schema: NodeSchema, first_account: Node):
    obj = await Node.init(session=session, schema=criticality_schema)
    await obj.new(session=session, name="low", level=4)

    assert obj.name.value == "low"
    assert obj.label.value == "Low"
    assert obj.level.value == 4
    assert obj.description.value is None
    assert obj.color.value == "#444444"
    assert obj.is_true.value is True
    assert obj.is_false.value is False

    obj = await Node.init(session=session, schema=criticality_schema)
    await obj.new(
        session=session,
        name="medium",
        label="MED",
        level=3,
        description="My desc",
        is_true=False,
        is_false=True,
        color="#333333",
    )

    assert obj.name.value == "medium"
    assert obj.label.value == "MED"
    assert obj.level.value == 3
    assert obj.description.value == "My desc"
    assert obj.color.value == "#333333"
    assert obj.is_true.value is False
    assert obj.is_false.value is True

    obj = await Node.init(session=session, schema=criticality_schema)
    await obj.new(session=session, name="medium_high", level=3, description="My desc", _source=first_account)

    assert obj.name.value == "medium_high"
    assert obj.label.value == "Medium High"
    assert obj.level.value == 3
    assert obj.description.value == "My desc"
    assert obj._source == first_account


async def test_node_init_schema_name(session, default_branch: Branch, criticality_schema):
    registry.set_schema(name="TestCriticality", schema=criticality_schema)
    obj = await Node.init(session=session, schema="TestCriticality")
    await obj.new(session=session, name="low", level=4)

    assert obj.name.value == "low"
    assert obj.level.value == 4
    assert obj.description.value is None
    assert obj.color.value == "#444444"


async def test_node_init_mandatory_missing(session, default_branch: Branch, criticality_schema):
    obj = await Node.init(session=session, schema=criticality_schema)

    with pytest.raises(ValidationError) as exc:
        await obj.new(session=session, level=4)

    assert "mandatory" in str(exc.value)


async def test_node_init_mandatory_field_null(session, default_branch: Branch, criticality_schema):
    obj = await Node.init(session=session, schema=criticality_schema)

    with pytest.raises(ValidationError) as direct_exc:
        await obj.new(session=session, name=None, level=4)

    with pytest.raises(ValidationError) as dict_exc:
        await obj.new(session=session, name={"value": None}, level=4)

    assert "A value must be provided for name at name" in str(direct_exc.value)
    assert "A value must be provided for name at name" in str(dict_exc.value)


async def test_node_init_invalid_attribute(session, default_branch: Branch, criticality_schema):
    obj = await Node.init(session=session, schema=criticality_schema)

    with pytest.raises(ValidationError) as exc:
        await obj.new(session=session, name="low", level=4, notvalid=False)

    assert "not a valid input" in str(exc.value)


async def test_node_init_invalid_value(session, default_branch: Branch, criticality_schema):
    obj = await Node.init(session=session, schema=criticality_schema)
    with pytest.raises(ValidationError) as exc:
        await obj.new(session=session, name="low", level="notanint")

    assert "not of type Number" in str(exc.value)

    obj = await Node.init(session=session, schema=criticality_schema)
    with pytest.raises(ValidationError) as exc:
        await obj.new(session=session, name=False, level=3)

    assert "not of type Text" in str(exc.value)


async def test_node_default_value(session, default_branch: Branch):
    SCHEMA = {
        "name": "OneOfEachKind",
        "namespace": "Test",
        "default_filter": "name__value",
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
            {"name": "myint", "kind": "Number"},
            {"name": "myint_default", "kind": "Number", "default_value": 10},
            {"name": "mystr", "kind": "Text"},
            {"name": "mystr_default", "kind": "Text", "default_value": "test"},
            {"name": "mybool", "kind": "Boolean"},
            {"name": "mybool_default", "kind": "Boolean", "default_value": True},
            {"name": "mybool_default_false", "kind": "Boolean", "default_value": False},
        ],
    }

    node_schema = NodeSchema(**SCHEMA)
    registry.set_schema(name=node_schema.kind, schema=node_schema)

    obj = await Node.init(session=session, schema=node_schema)
    await obj.new(session=session, name="test01", myint=100, mybool=False, mystr="test02")

    assert obj.name.value == "test01"
    assert obj.myint.value == 100
    assert obj.myint_default.value == 10
    assert obj.mystr.value == "test02"
    assert obj.mystr_default.value == "test"
    assert obj.mybool.value is False
    assert obj.mybool_default.value is True
    assert obj.mybool_default_false.value is False


async def test_render_display_label(session, default_branch: Branch, car_person_schema):
    schema_01 = {
        "name": "Display",
        "namespace": "Test",
        "display_labels": ["firstname__value"],
        "attributes": [
            {"name": "firstname", "kind": "Text"},
            {"name": "lastname", "kind": "Text"},
            {"name": "age", "kind": "Number"},
        ],
    }

    node_schema = NodeSchema(**schema_01)
    registry.schema.set(name=node_schema.kind, schema=node_schema)

    obj = await Node.init(session=session, schema=node_schema)
    await obj.new(session=session, firstname="John", lastname="Doe", age=99)
    assert await obj.render_display_label(session=session) == "John"

    # Display Labels with 2 attributes
    schema_01["display_labels"] = ["firstname__value", "age__value"]
    node_schema = NodeSchema(**schema_01)
    registry.schema.set(name=node_schema.kind, schema=node_schema)

    obj = await Node.init(session=session, schema=node_schema)
    await obj.new(session=session, firstname="John", lastname="Doe", age=99)
    assert await obj.render_display_label(session=session) == "John 99"

    # Empty Display Label
    schema_01["display_labels"] = []
    node_schema = NodeSchema(**schema_01)
    registry.schema.set(name=node_schema.kind, schema=node_schema)

    obj = await Node.init(session=session, schema=node_schema)
    await obj.new(session=session, firstname="John", lastname="Doe", age=99)
    assert await obj.render_display_label(session=session) == "TestDisplay(ID: None)"


async def test_node_init_with_single_relationship(session, default_branch: Branch, car_person_schema):
    car = registry.get_schema(name="TestCar")
    person = registry.get_schema(name="TestPerson")

    p1 = await Node.init(session=session, schema=person)
    await p1.new(session=session, name="John", height=180)

    assert p1.name.value == "John"
    assert p1.height.value == 180
    assert list(await p1.cars.get(session=session)) == []

    await p1.save(session=session)

    c1 = await Node.init(session=session, schema=car)
    await c1.new(session=session, name="volt", nbr_seats=4, is_electric=True, owner=p1)

    assert c1.name.value == "volt"
    assert c1.nbr_seats.value == 4
    assert c1.is_electric.value is True
    assert await c1.owner.get_peer(session=session) == p1

    c2 = await Node.init(session=session, schema=car)
    await c2.new(session=session, name="volt", nbr_seats=4, is_electric=True, owner=p1.id)

    assert c2.name.value == "volt"
    assert c2.nbr_seats.value == 4
    assert c2.is_electric.value is True
    c2_peer = await c2.owner.get_peer(session=session)
    assert c2_peer.id == p1.id


async def test_to_graphql(session, default_branch: Branch, car_person_schema):
    car = registry.get_schema(name="TestCar")
    person = registry.get_schema(name="TestPerson")

    p1 = await Node.init(session=session, schema=person)
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)

    c1 = await Node.init(session=session, schema=car)
    await c1.new(session=session, name="volt", nbr_seats=4, is_electric=True, owner=p1)
    await c1.save(session=session)

    expected_data = {
        "id": c1.id,
        "nbr_seats": {
            "id": c1.nbr_seats.id,
            "value": 4,
        },
        "type": "TestCar",
    }
    assert await c1.to_graphql(session=session, fields={"nbr_seats": {"value": None}}) == expected_data

    expected_data = {
        "id": c1.id,
        "display_label": "volt #444444",
        "name": {
            "id": c1.name.id,
            "is_protected": False,
        },
        "type": "TestCar",
    }

    assert (
        await c1.to_graphql(session=session, fields={"display_label": None, "name": {"is_protected": None}})
        == expected_data
    )


async def test_to_graphql_no_fields(session, default_branch: Branch, car_person_schema):
    car = registry.get_schema(name="TestCar")
    person = registry.get_schema(name="TestPerson")

    p1 = await Node.init(session=session, schema=person)
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)

    c1 = await Node.init(session=session, schema=car)
    await c1.new(session=session, name="volt", nbr_seats=4, is_electric=True, owner=p1)
    await c1.save(session=session)

    expected_data = {
        "__typename": "TestCar",
        "color": {
            "__typename": "Text",
            "id": c1.color.id,
            "is_protected": False,
            "is_visible": True,
            "owner": None,
            "source": None,
            "value": "#444444",
        },
        "display_label": "volt #444444",
        "id": c1.id,
        "is_electric": {
            "__typename": "Boolean",
            "id": c1.is_electric.id,
            "is_protected": False,
            "is_visible": True,
            "owner": None,
            "source": None,
            "value": True,
        },
        "name": {
            "__typename": "Text",
            "id": c1.name.id,
            "is_protected": False,
            "is_visible": True,
            "owner": None,
            "source": None,
            "value": "volt",
        },
        "nbr_seats": {
            "__typename": "Number",
            "id": c1.nbr_seats.id,
            "is_protected": False,
            "is_visible": True,
            "owner": None,
            "source": None,
            "value": 4,
        },
        "type": "TestCar",
    }
    assert await c1.to_graphql(session=session) == expected_data


# --------------------------------------------------------------------------
# Create
# --------------------------------------------------------------------------


async def test_node_create_local_attrs(session, default_branch: Branch, criticality_schema):
    obj = await Node.init(session=session, schema=criticality_schema)
    await obj.new(session=session, name="low", level=4)
    await obj.save(session=session)

    assert obj.id
    assert obj.db_id
    assert obj.name.value == "low"
    assert obj.name.id
    assert obj.level.value == 4
    assert obj.level.id
    assert obj.description.value is None
    assert obj.description.id
    assert obj.color.value == "#444444"
    assert obj.color.id
    assert obj.is_true.value is True
    assert obj.is_false.value is False
    assert obj.json_default.value == {"value": "bob"}
    assert obj.json_no_default.value is None

    obj = await Node.init(session=session, schema=criticality_schema)
    await obj.new(
        session=session, name="medium", level=3, description="My desc", is_true=False, is_false=True, color="#333333"
    )
    await obj.save(session=session)

    assert obj.id
    assert obj.db_id
    assert obj.name.value == "medium"
    assert obj.name.id
    assert obj.level.value == 3
    assert obj.level.id
    assert obj.description.value == "My desc"
    assert obj.description.id
    assert obj.color.value == "#333333"
    assert obj.color.id
    assert obj.is_true.value is False
    assert obj.is_false.value is True


async def test_node_create_attribute_with_source(session, default_branch: Branch, criticality_schema, first_account):
    obj = await Node.init(session=session, schema=criticality_schema)
    await obj.new(session=session, name="low", level=4, _source=first_account)
    await obj.save(session=session)

    assert obj.id
    assert obj.db_id
    assert obj._source == first_account
    assert obj.name.value == "low"
    assert obj.name.id
    assert obj.name.source_id == first_account.id
    assert obj.level.value == 4
    assert obj.level.id
    assert obj.level.source_id == first_account.id
    assert obj.description.value is None
    assert obj.description.id
    assert obj.description.source_id == first_account.id
    assert obj.color.value == "#444444"
    assert obj.color.id
    assert obj.color.source_id == first_account.id


async def test_node_create_attribute_with_different_sources(
    session, default_branch: Branch, criticality_schema, first_account, second_account
):
    obj = await Node.init(session=session, schema=criticality_schema)
    await obj.new(session=session, name={"value": "low", "source": second_account.id}, level=4, _source=first_account)
    await obj.save(session=session)

    assert obj.id
    assert obj.db_id
    assert obj._source == first_account
    assert obj.name.value == "low"
    assert obj.name.id
    assert obj.name.source_id == second_account.id
    assert obj.level.value == 4
    assert obj.level.id
    assert obj.level.source_id == first_account.id
    assert obj.description.value is None
    assert obj.description.id
    assert obj.description.source_id == first_account.id
    assert obj.color.value == "#444444"
    assert obj.color.id
    assert obj.color.source_id == first_account.id


async def test_node_create_attribute_with_owner(session, default_branch: Branch, criticality_schema, first_account):
    obj = await Node.init(session=session, schema=criticality_schema)
    await obj.new(session=session, name="low", level=4, _owner=first_account)
    await obj.save(session=session)

    assert obj.id
    assert obj.db_id
    assert obj._owner == first_account
    assert obj.name.value == "low"
    assert obj.name.id
    assert obj.name.owner_id == first_account.id
    assert obj.level.value == 4
    assert obj.level.id
    assert obj.level.owner_id == first_account.id
    assert obj.description.value is None
    assert obj.description.id
    assert obj.description.owner_id == first_account.id
    assert obj.color.value == "#444444"
    assert obj.color.id
    assert obj.color.owner_id == first_account.id


async def test_node_create_attribute_with_different_owner(
    session, default_branch: Branch, criticality_schema, first_account, second_account
):
    obj = await Node.init(session=session, schema=criticality_schema)
    await obj.new(session=session, name={"value": "low", "owner": second_account.id}, level=4, _owner=first_account)
    await obj.save(session=session)

    assert obj.id
    assert obj.db_id
    assert obj._owner == first_account
    assert obj.name.value == "low"
    assert obj.name.id
    assert obj.name.owner_id == second_account.id
    assert obj.level.value == 4
    assert obj.level.id
    assert obj.level.owner_id == first_account.id
    assert obj.description.value is None
    assert obj.description.id
    assert obj.description.owner_id == first_account.id
    assert obj.color.value == "#444444"
    assert obj.color.id
    assert obj.color.owner_id == first_account.id


async def test_node_create_with_single_relationship(session, default_branch: Branch, car_person_schema):
    car = registry.get_schema(name="TestCar")
    person = registry.get_schema(name="TestPerson")

    p1 = await Node.init(session=session, schema=person)
    await p1.new(session=session, name="John", height=180)

    assert p1.name.value == "John"
    assert p1.height.value == 180
    assert list(await p1.cars.get(session=session)) == []

    await p1.save(session=session)

    # Pass entire object for owner
    c1 = await Node.init(session=session, schema=car)
    await c1.new(session=session, name="volt", nbr_seats=4, is_electric=True, owner=p1)
    await c1.save(session=session)

    assert c1.name.value == "volt"
    assert c1.nbr_seats.value == 4
    assert c1.is_electric.value is True
    c1_owner = await c1.owner.get_peer(session=session)
    assert c1_owner == p1

    paths = await get_paths_between_nodes(
        session=session, source_id=c1.db_id, destination_id=p1.db_id, max_length=2, relationships=["IS_RELATED"]
    )
    assert len(paths) == 1

    # Pass ID of an object for owner
    c2 = await Node.init(session=session, schema=car)
    await c2.new(session=session, name="accord", nbr_seats=5, is_electric=False, owner=p1.id)
    await c2.save(session=session)

    assert c2.name.value == "accord"
    assert c2.nbr_seats.value == 5
    assert c2.is_electric.value is False
    c2_owner = await c2.owner.get_peer(session=session)
    assert c2_owner.id == p1.id

    paths = await get_paths_between_nodes(
        session=session, source_id=c2.db_id, destination_id=p1.db_id, max_length=2, relationships=["IS_RELATED"]
    )
    assert len(paths) == 1

    # Define metadata along object ID for owner
    c3 = await Node.init(session=session, schema=car)
    await c3.new(
        session=session,
        name="smart",
        nbr_seats=2,
        is_electric=True,
        owner={"id": p1.id, "_relation__is_protected": True, "_relation__is_visible": False},
    )
    await c3.save(session=session)

    assert c3.name.value == "smart"
    assert c3.nbr_seats.value == 2
    assert c3.is_electric.value is True
    c3_owner = await c3.owner.get_peer(session=session)
    assert c3_owner.id == p1.id
    rel = await c3.owner.get(session=session)
    assert rel.is_protected is True
    assert rel.is_visible is False
    paths = await get_paths_between_nodes(
        session=session, source_id=c3.db_id, destination_id=p1.db_id, max_length=2, relationships=["IS_RELATED"]
    )
    assert len(paths) == 1


async def test_node_create_with_multiple_relationship(session, default_branch: Branch, fruit_tag_schema):
    fruit = registry.get_schema(name="GardenFruit")
    tag = registry.get_schema(name="BuiltinTag")

    t1 = await Node.init(session=session, schema=tag)
    await t1.new(session=session, name="tag1")
    await t1.save(session=session)

    t2 = await Node.init(session=session, schema=tag)
    await t2.new(session=session, name="tag2")
    await t2.save(session=session)

    t3 = await Node.init(session=session, schema=tag)
    await t3.new(session=session, name="tag3")
    await t3.save(session=session)

    f1 = await Node.init(session=session, schema=fruit)
    await f1.new(session=session, name="apple", tags=[t1, t2, t3])
    await f1.save(session=session)
    assert f1.name.value == "apple"
    assert len(list(await f1.tags.get(session=session))) == 3

    # We should have 2 paths between f1 and t1, t2 & t3
    # First for the relationship, second via the branch
    paths = await get_paths_between_nodes(session=session, source_id=f1.db_id, destination_id=t1.db_id, max_length=2)
    assert len(paths) == 2
    paths = await get_paths_between_nodes(session=session, source_id=f1.db_id, destination_id=t2.db_id, max_length=2)
    assert len(paths) == 2
    paths = await get_paths_between_nodes(session=session, source_id=f1.db_id, destination_id=t3.db_id, max_length=2)
    assert len(paths) == 2


# --------------------------------------------------------------------------
# Update
# --------------------------------------------------------------------------


async def test_node_update_local_attrs(session, default_branch: Branch, criticality_schema):
    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(session=session, name="low", level=4)
    await obj1.save(session=session)

    obj2 = await NodeManager.get_one(session=session, id=obj1.id)
    obj2.name.value = "high"
    obj2.level.value = 1
    obj2.is_true.value = False
    obj2.is_false.value = True
    obj2.mylist.value = ["one", "two"]
    await obj2.save(session=session)

    nbr_rels = await count_relationships(session=session)

    obj3 = await NodeManager.get_one(session=session, id=obj1.id)
    assert obj3.name.value == "high"
    assert obj3.level.value == 1
    assert obj3.is_true.value is False
    assert obj3.is_false.value is True
    assert obj3.mylist.value == ["one", "two"]

    # Validate that saving the object a second time doesn't do anything
    await obj2.save(session=session)
    assert await count_relationships(session=session) == nbr_rels


async def test_node_update_local_attrs_with_flags(session, default_branch: Branch, criticality_schema):
    fields_to_query = {"name": True, "level": True}
    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(session=session, name="low", level=4)
    await obj1.save(session=session)

    obj2 = await NodeManager.get_one(id=obj1.id, fields=fields_to_query, session=session)
    obj2.name.is_protected = True
    obj2.level.is_visible = False
    await obj2.save(session=session)

    obj3 = await NodeManager.get_one(id=obj1.id, fields=fields_to_query, session=session)
    assert obj3.name.is_protected is True
    assert obj3.level.is_visible is False


async def test_node_update_local_attrs_with_source(
    session, default_branch: Branch, criticality_schema, first_account, second_account
):
    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(session=session, name="low", level=4, _source=first_account)
    await obj1.save(session=session)

    obj2 = await NodeManager.get_one(id=obj1.id, include_source=True, session=session)
    obj2.name.source = second_account
    await obj2.save(session=session)

    obj3 = await NodeManager.get_one(id=obj1.id, include_source=True, session=session)
    assert obj3.name.source_id == second_account.id


async def test_update_related_node(db, session, default_branch, data_schema):
    """
    This test has been written to troubleshoot a specific issue
    where a relationship between 2 nodes was being deleted when one of the node was getting updated.
    """
    # ----------------------------------------------------------------
    # Define specific schema
    # ----------------------------------------------------------------
    SCHEMA = {
        "nodes": [
            {
                "name": "Tag",
                "namespace": "Builtin",
                "default_filter": "name__value",
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
                "relationships": [
                    {"name": "person", "peer": "TestPerson", "cardinality": "one"},
                ],
            },
            {
                "name": "Person",
                "namespace": "Test",
                "default_filter": "name__value",
                "branch": BranchSupportType.AWARE.value,
                "attributes": [
                    {"name": "firstname", "kind": "Text"},
                    {"name": "lastname", "kind": "Text"},
                ],
                "relationships": [
                    {"name": "tags", "peer": "BuiltinTag", "cardinality": "many"},
                ],
            },
        ]
    }

    schema = SchemaRoot(**SCHEMA)
    registry.schema.register_schema(schema=schema)

    # ----------------------------------------------------------------
    # Create objects
    # ----------------------------------------------------------------
    p1 = await Node.init(session=session, schema="TestPerson")
    await p1.new(session=session, firstname="John", lastname="Doe")
    await p1.save(session=session)

    t1 = await Node.init(session=session, schema="BuiltinTag")
    await t1.new(session=session, name="Blue", description="The Blue tag", person=p1)
    await t1.save(session=session)
    t2 = await Node.init(session=session, schema="BuiltinTag")
    await t2.new(session=session, name="Red", description="The Red tag", person=p1)
    await t2.save(session=session)
    t3 = await Node.init(session=session, schema="BuiltinTag")
    await t3.new(session=session, name="Black", description="The Black tag", person=p1)
    await t3.save(session=session)

    # ----------------------------------------------------------------
    # Query all tags attached to person
    # ----------------------------------------------------------------
    p11 = await NodeManager.get_one(session=session, id=p1.id)
    tags = await p11.tags.get(session=session)
    assert len(tags) == 3

    # ----------------------------------------------------------------
    # Update the description of Tag1 in the main branch
    # ----------------------------------------------------------------
    new_description = "New description in main"
    t11 = await NodeManager.get_one(session=session, id=t1.id)
    t11.description.value = new_description
    await t11.save(session=session)

    # ----------------------------------------------------------------
    # Re-query the tag via the related objects to validate that everything is still connected
    # ----------------------------------------------------------------
    p12 = await NodeManager.get_one(session=session, id=p1.id)
    tags = await p12.tags.get(session=session)
    assert len(tags) == 3


# --------------------------------------------------------------------------
# Delete
# --------------------------------------------------------------------------


async def test_node_delete_local_attrs(session, default_branch: Branch, criticality_schema):
    obj2 = await Node.init(session=session, schema=criticality_schema)
    await obj2.new(session=session, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(session=session)

    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(session=session, name="low", level=4)
    await obj1.save(session=session)

    time1 = Timestamp()

    obj22 = await NodeManager.get_one(id=obj2.id, at=time1, session=session)
    assert obj22

    await obj22.delete(session=session)

    assert await NodeManager.get_one(id=obj1.id, session=session)
    assert not await NodeManager.get_one(id=obj2.id, session=session)


async def test_node_delete_query_past(session, default_branch: Branch, criticality_schema):
    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(session=session, name="low", level=4)
    await obj1.save(session=session)

    obj2 = await Node.init(session=session, schema=criticality_schema)
    await obj2.new(session=session, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(session=session)

    time1 = Timestamp()

    obj22 = await NodeManager.get_one(id=obj2.id, session=session)
    assert obj22

    await obj22.delete(session=session)

    assert await NodeManager.get_one(id=obj1.id, session=session)
    assert not await NodeManager.get_one(id=obj2.id, session=session)
    assert await NodeManager.get_one(id=obj2.id, at=time1, session=session)


async def test_node_delete_local_attrs_in_branch(session, default_branch: Branch, criticality_schema):
    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(session=session, name="low", level=4)
    await obj1.save(session=session)

    obj2 = await Node.init(session=session, schema=criticality_schema)
    await obj2.new(session=session, name="medium", level=3, description="My desc", color="#333333")
    await obj2.save(session=session)

    branch1 = Branch(name="branch1", status="OPEN")
    await branch1.save(session=session)

    obj21 = await NodeManager.get_one(id=obj2.id, branch=branch1, session=session)
    assert obj21

    await obj21.delete(session=session)

    assert await NodeManager.get_one(id=obj1.id, session=session)
    assert await NodeManager.get_one(id=obj2.id, session=session)
    assert not await NodeManager.get_one(id=obj2.id, branch=branch1, session=session)

    resp = await NodeManager.query(session=session, schema=criticality_schema)
    assert len(resp) == 2

    resp = await NodeManager.query(session=session, schema=criticality_schema, branch=branch1)
    assert len(resp) == 1


async def test_node_delete_with_relationship_bidir(session, default_branch: Branch, car_person_schema):
    p1 = await Node.init(session=session, schema="TestPerson")
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)

    c1 = await Node.init(session=session, schema="TestCar")
    await c1.new(session=session, name="volt", nbr_seats=4, is_electric=True, owner=p1)
    await c1.save(session=session)

    c2 = await Node.init(session=session, schema="TestCar")
    await c2.new(session=session, name="accord", nbr_seats=5, is_electric=False, owner=p1.id)
    await c2.save(session=session)

    time1 = Timestamp()

    await c1.delete(session=session)

    resp = await NodeManager.query(schema="TestCar", session=session)
    assert len(resp) == 1
    resp = await NodeManager.query(schema="TestCar", at=time1, session=session)
    assert len(resp) == 2

    p11 = await NodeManager.get_one(id=p1.id, session=session)
    assert len(list(await p11.cars.get(session=session))) == 1

    p12 = await NodeManager.get_one(id=p1.id, at=time1, session=session)
    assert len(list(await p12.cars.get(session=session))) == 2


# --------------------------------------------------------------------------
# With Branch
# --------------------------------------------------------------------------


async def test_node_create_in_branch(session, default_branch: Branch, criticality_schema):
    branch1 = await create_branch(branch_name="branch1", session=session)

    obj = await Node.init(session=session, schema=criticality_schema, branch=branch1)
    await obj.new(session=session, name="low", level=4)
    await obj.save(session=session)

    assert await NodeManager.get_one(id=obj.id, branch=default_branch, session=session) is None
    obj2 = await NodeManager.get_one(id=obj.id, branch=branch1, session=session)
    assert obj2.id == obj.id


async def test_node_update_in_branch(session, default_branch: Branch, criticality_schema):
    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(session=session, name="low", level=4)
    await obj1.save(session=session)

    branch1 = await create_branch(branch_name="branch1", session=session)

    obj2 = await NodeManager.get_one(id=obj1.id, branch=branch1, session=session)
    obj2.name.value = "High"
    obj2.level.value = 5
    await obj2.save(session=session)

    obj11 = await NodeManager.get_one(id=obj1.id, session=session)
    assert obj11.name.value == "low"
    assert obj11.level.value == 4

    obj21 = await NodeManager.get_one(id=obj1.id, branch=branch1, session=session)
    assert obj21.name.value == "High"
    assert obj21.level.value == 5


# --------------------------------------------------------------------------
# With Global Branch
# --------------------------------------------------------------------------


async def test_node_create_in_branch_global(session, default_branch: Branch, fruit_tag_schema_global):
    branch1 = await create_branch(branch_name="branch1", session=session)

    obj = await Node.init(session=session, schema="GardenFruit", branch=branch1)
    await obj.new(session=session, name="apple")
    await obj.save(session=session)

    obj21 = await NodeManager.get_one(id=obj.id, branch=default_branch, session=session)
    assert obj21.id == obj.id

    obj22 = await NodeManager.get_one(id=obj.id, branch=branch1, session=session)
    assert obj22.id == obj.id


async def test_node_update_in_branch_global(session, default_branch: Branch, fruit_tag_schema_global):
    obj1 = await Node.init(session=session, schema="GardenFruit")
    await obj1.new(session=session, name="RedApple")
    await obj1.save(session=session)

    branch1 = await create_branch(branch_name="branch1", session=session)

    obj2 = await NodeManager.get_one(id=obj1.id, branch=branch1, session=session)
    obj2.name.value = "Green Apple"
    obj2.description.value = "A Green Apple"
    await obj2.save(session=session)

    obj11 = await NodeManager.get_one(id=obj1.id, session=session)
    assert obj11.name.value == "Green Apple"
    assert obj11.description.value == "A Green Apple"

    obj21 = await NodeManager.get_one(id=obj1.id, branch=branch1, session=session)
    assert obj21.name.value == "Green Apple"
    assert obj21.description.value == "A Green Apple"


async def test_node_update_attribute_hybrid_in_branch_global(session, default_branch: Branch, fruit_tag_schema_global):
    red = await Node.init(session=session, schema="BuiltinTag")
    await red.new(session=session, name="red")
    await red.save(session=session)

    f1 = await Node.init(session=session, schema="GardenFruit")
    await f1.new(session=session, name="apple", tags=[red])
    await f1.save(session=session)

    f2 = await Node.init(session=session, schema="GardenFruit")
    await f2.new(session=session, name="pineapple")
    await f2.save(session=session)

    branch1 = await create_branch(branch_name="branch1", session=session)

    blue = await Node.init(session=session, schema="BuiltinTag", branch=branch1)
    await blue.new(session=session, name="blue")
    await blue.save(session=session)

    # Update attribute that don't have the same branch awareness as their parent node
    red_branch = await NodeManager.get_one(id=red.id, branch=branch1, session=session)
    red_branch.color.value = "#555555"
    await red_branch.save(session=session)

    f2_main = await NodeManager.get_one(id=f1.id, session=session)
    f2_main.branch_aware_attr.value = "New value in main after the creation of the branch"
    await f2_main.save(session=session)

    f2_branch = await NodeManager.get_one(id=f2.id, branch=branch1, session=session)
    assert f2_branch.branch_aware_attr.value is None

    red_main = await NodeManager.get_one(id=red.id, session=session)
    assert red_main.color.value == "#555555"


async def test_node_relationship_in_branch_global(session, default_branch: Branch, fruit_tag_schema_global):
    red = await Node.init(session=session, schema="BuiltinTag")
    await red.new(session=session, name="red")
    await red.save(session=session)

    f1 = await Node.init(session=session, schema="GardenFruit")
    await f1.new(session=session, name="apple", tags=[red])
    await f1.save(session=session)

    f2 = await Node.init(session=session, schema="GardenFruit")
    await f2.new(session=session, name="pineapple")
    await f2.save(session=session)

    branch1 = await create_branch(branch_name="branch1", session=session)

    blue = await Node.init(session=session, schema="BuiltinTag", branch=branch1)
    await blue.new(session=session, name="blue")
    await blue.save(session=session)

    # Add relationships to F2 in the branch
    f2_branch = await NodeManager.get_one(id=f2.id, branch=branch1, session=session)
    await f2_branch.tags.update(session=session, data=[red, blue])
    await f2_branch.related_fruits.update(session=session, data=[f1])
    await f2_branch.save(session=session)

    # Validate that the new relationships are visible from the other node only in the branch
    # Because BuiltinTag is branch aware
    red_main = await NodeManager.get_one(id=red.id, session=session)
    rels = await red_main.related_fruits.get(session=session)
    assert len(rels) == 1

    red_branch = await NodeManager.get_one(id=red.id, branch=branch1, session=session)
    rels = await red_branch.related_fruits.get(session=session)
    assert len(rels) == 2

    # Validate that the new relationships are:
    # - visible from the only in the branch for BuiltinTag
    # - Visible on all branches for GardenFruit
    f2_main = await NodeManager.get_one(id=f2.id, session=session)
    assert len(await f2_main.tags.get(session=session)) == 0
    assert len(await f2_main.related_fruits.get(session=session)) == 1

    f2_branch = await NodeManager.get_one(id=f2.id, branch=branch1, session=session)
    await f2_branch.related_fruits.update(session=session, data=[])
    await f2_branch.save(session=session)

    f2_main = await NodeManager.get_one(id=f2.id, session=session)
    assert len(await f2_main.related_fruits.get(session=session)) == 0


async def test_node_delete_in_branch_global(session, default_branch: Branch, fruit_tag_schema_global):
    red = await Node.init(session=session, schema="BuiltinTag")
    await red.new(session=session, name="red")
    await red.save(session=session)

    f1 = await Node.init(session=session, schema="GardenFruit")
    await f1.new(session=session, name="apple", tags=[red])
    await f1.save(session=session)

    f2 = await Node.init(session=session, schema="GardenFruit")
    await f2.new(session=session, name="pineapple", tags=[red])
    await f2.save(session=session)

    branch1 = await create_branch(branch_name="branch1", session=session)

    f1_branch = await NodeManager.get_one(id=f1.id, branch=branch1, session=session)
    await f1_branch.delete(session=session)

    resp = await NodeManager.query(session=session, schema="GardenFruit")
    assert len(resp) == 1

    resp = await NodeManager.query(session=session, schema="GardenFruit", branch=branch1)
    assert len(resp) == 1

    red_main = await NodeManager.get_one(id=red.id, branch=branch1, session=session)
    assert len(await red_main.related_fruits.get(session=session)) == 1

    red_branch = await NodeManager.get_one(id=red.id, branch=branch1, session=session)
    assert len(await red_branch.related_fruits.get(session=session)) == 1


# --------------------------------------------------------------------------
# With Interface
# --------------------------------------------------------------------------


async def test_node_relationship_interface(session, default_branch: Branch, vehicule_person_schema):
    d1 = await Node.init(session=session, schema="TestCar")
    await d1.new(session=session, name="Porsche 911", nbr_doors=2)
    await d1.save(session=session)

    b1 = await Node.init(session=session, schema="TestBoat")
    await b1.new(session=session, name="Laser", has_sails=True)
    await b1.save(session=session)

    p1 = await Node.init(session=session, schema="TestPerson")
    await p1.new(session=session, name="John Doe", vehicules=[d1, b1])
    await p1.save(session=session)

    obj1 = await NodeManager.get_one(id=p1.id, branch=default_branch, session=session)
    vehicules = await obj1.vehicules.get(session=session)
    assert len(vehicules) == 2


# --------------------------------------------------------------------------
# With Union
# --------------------------------------------------------------------------


async def test_union(
    session, default_branch: Branch, generic_vehicule_schema, car_schema, truck_schema, motorcycle_schema
):
    SCHEMA = {
        "name": "Person",
        "namespace": "Test",
        "default_filter": "name__value",
        "branch": BranchSupportType.AWARE.value,
        "attributes": [
            {"name": "name", "kind": "Text", "unique": True},
        ],
        "relationships": [
            {"name": "road_vehicules", "peer": "OnRoad", "cardinality": "many", "identifier": "person__vehicule"}
        ],
    }

    node = NodeSchema(**SCHEMA)
    registry.schema.set(name=node.kind, schema=node, branch=default_branch.name)
    registry.schema.process_schema_branch(name=default_branch.name)

    d1 = await Node.init(session=session, schema="TestCar")
    await d1.new(session=session, name="Porsche 911", nbr_doors=2)
    await d1.save(session=session)

    t1 = await Node.init(session=session, schema="TestTruck")
    await t1.new(session=session, name="Silverado", nbr_axles=4)
    await t1.save(session=session)

    m1 = await Node.init(session=session, schema="TestMotorcycle")
    await m1.new(session=session, name="Monster", nbr_seats=1)
    await m1.save(session=session)

    p1 = await Node.init(session=session, schema="TestPerson")
    await p1.new(session=session, name="John Doe", road_vehicules=[d1, t1, m1])
    await p1.save(session=session)

    obj1 = await NodeManager.get_one(id=p1.id, branch=default_branch, session=session)
    peers = [await peer_rel.get_peer(session=session) for peer_rel in await obj1.road_vehicules.get(session=session)]
    assert len(peers) == 3

    kinds = sorted([peer.get_kind() for peer in peers])
    assert kinds == ["TestCar", "TestMotorcycle", "TestTruck"]


# --------------------------------------------------------------------------
# Serialize
# --------------------------------------------------------------------------


async def test_node_serialize_prefix(session, default_branch: Branch, prefix_schema):
    prefix = registry.get_schema(name="TestPrefix")

    p1 = await Node.init(session=session, schema=prefix)
    await p1.new(session=session, prefix="192.0.2.1", name="prefix1")
    await p1.save(session=session)

    retrieve_p1 = await NodeManager.get_one(id=p1.id, session=session)
    assert retrieve_p1.prefix.value == "192.0.2.1/32"

    p2 = await Node.init(session=session, schema=prefix)
    await p2.new(session=session, prefix="192.0.2.1/255.255.255.255", name="prefix2")
    await p2.save(session=session)

    retrieve_p2 = await NodeManager.get_one(id=p1.id, session=session)
    assert retrieve_p2.prefix.value == "192.0.2.1/32"

    p3 = await Node.init(session=session, schema=prefix)
    await p3.new(session=session, prefix="2001:db8::/128", name="prefix3")
    await p3.save(session=session)

    retrieve_p3 = await NodeManager.get_one(id=p3.id, session=session)
    assert retrieve_p3.prefix.value == "2001:db8::/128"


async def test_node_serialize_address(session, default_branch: Branch, prefix_schema):
    ip = registry.get_schema(name="TestIp")

    i1 = await Node.init(session=session, schema=ip)
    await i1.new(session=session, address="192.0.2.1", name="ip1")
    await i1.save(session=session)

    retrieve_i1 = await NodeManager.get_one(id=i1.id, session=session)
    assert retrieve_i1.address.value == "192.0.2.1/32"

    i2 = await Node.init(session=session, schema=ip)
    await i2.new(session=session, address="2001:db8::", name="ip2")
    await i2.save(session=session)

    retrieve_i2 = await NodeManager.get_one(id=i2.id, session=session)
    assert retrieve_i2.address.value == "2001:db8::/128"
