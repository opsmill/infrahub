import pytest
from graphql import graphql

from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.graphql import generate_graphql_schema


async def test_update_simple_object(db, session, default_branch, car_person_schema):

    obj = await Node.init(session=session, schema="Person")
    await obj.new(session=session, name="John", height=180)
    await obj.save(session=session)

    query = (
        """
    mutation {
        person_update(data: {id: "%s", name: { value: "Jim"}}) {
            ok
            object {
                id
                name {
                    value
                }
            }
        }
    }
    """
        % obj.id
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_update"]["ok"] is True

    obj1 = await NodeManager.get_one(session=session, id=obj.id)
    assert obj1.name.value == "Jim"
    assert obj1.height.value == 180


async def test_update_object_with_flag_property(db, session, default_branch, car_person_schema):

    obj = await Node.init(session=session, schema="Person")
    await obj.new(session=session, name="John", height=180)
    await obj.save(session=session)

    query = (
        """
    mutation {
        person_update(data: {id: "%s", name: { is_protected: true }, height: { is_visible: false}}) {
            ok
            object {
                id
                name {
                    is_protected
                }
                height {
                    is_visible
                }
            }
        }
    }
    """
        % obj.id
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_update"]["ok"] is True

    obj1 = await NodeManager.get_one(session=session, id=obj.id)
    assert obj1.name.is_protected is True
    assert obj1.height.value == 180
    assert obj1.height.is_visible is False


async def test_update_object_with_node_property(
    db, session, default_branch, car_person_schema, first_account, second_account
):

    obj = await Node.init(session=session, schema="Person")
    await obj.new(session=session, name="John", height=180, _source=first_account)
    await obj.save(session=session)

    query = """
    mutation {
        person_update(data: {id: "%s", name: { source: "%s" } }) {
            ok
            object {
                id
            }
        }
    }
    """ % (
        obj.id,
        second_account.id,
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_update"]["ok"] is True

    obj1 = await NodeManager.get_one(session=session, id=obj.id, include_source=True)
    assert obj1.name.source_id == second_account.id
    assert obj1.height.source_id == first_account.id


async def test_update_invalid_object(db, session, default_branch, car_person_schema):

    query = """
    mutation {
        person_update(data: {id: "XXXXXX", name: { value: "Jim"}}) {
            ok
            object {
                id
                name {
                    value
                }
            }
        }
    }
    """

    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert len(result.errors) == 1
    assert "Unable to find the node in the database." in result.errors[0].message


async def test_update_invalid_input(db, session, default_branch, car_person_schema):

    obj = await Node.init(session=session, schema="Person")
    await obj.new(session=session, name="John", height=180)
    await obj.save(session=session)

    query = (
        """
    mutation {
        person_update(data: {id: "%s", name: { value: False }}) {
            ok
            object {
                id
                name {
                    value
                }
            }
        }
    }
    """
        % obj.id
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert len(result.errors) == 1
    assert "String cannot represent a non string value" in result.errors[0].message


async def test_update_single_relationship(db, session, default_branch, car_person_schema):

    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)

    p2 = await Node.init(session=session, schema="Person")
    await p2.new(session=session, name="Jim", height=170)
    await p2.save(session=session)

    c1 = await Node.init(session=session, schema="Car")
    await c1.new(session=session, name="accord", nbr_seats=5, is_electric=False, owner=p1.id)
    await c1.save(session=session)

    query = """
    mutation {
        car_update(data: {id: "%s", owner: { id: "%s" }}) {
            ok
            object {
                id
                owner {
                    name {
                        value
                    }
                }
            }
        }
    }
    """ % (
        c1.id,
        p2.id,
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["car_update"]["ok"] is True
    assert result.data["car_update"]["object"]["owner"]["name"]["value"] == "Jim"

    car = await NodeManager.get_one(session=session, id=c1.id)
    car_peer = await car.owner.get_peer(session=session)
    assert car_peer.id == p2.id


async def test_update_new_single_relationship_flag_property(db, session, default_branch, car_person_schema):

    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)

    p2 = await Node.init(session=session, schema="Person")
    await p2.new(session=session, name="Jim", height=170)
    await p2.save(session=session)

    c1 = await Node.init(session=session, schema="Car")
    await c1.new(session=session, name="accord", nbr_seats=5, is_electric=False, owner=p1.id)
    await c1.save(session=session)

    query = """
    mutation {
        car_update(data: {id: "%s", owner: { id: "%s", _relation__is_protected: true }}) {
            ok
            object {
                id
                owner {
                    name {
                        value
                    }
                }
            }
        }
    }
    """ % (
        c1.id,
        p2.id,
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["car_update"]["ok"] is True
    assert result.data["car_update"]["object"]["owner"]["name"]["value"] == "Jim"

    car = await NodeManager.get_one(session=session, id=c1.id)
    car_peer = await car.owner.get_peer(session=session)
    assert car_peer.id == p2.id
    assert car.owner.get().is_protected is True


async def test_update_existing_single_relationship_flag_property(db, session, default_branch, car_person_schema):

    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)

    c1 = await Node.init(session=session, schema="Car")
    await c1.new(session=session, name="accord", nbr_seats=5, is_electric=False, owner=p1.id)
    await c1.save(session=session)

    query = """
    mutation {
        car_update(data: {id: "%s", owner: { id: "%s", _relation__is_protected: true }}) {
            ok
            object {
                id
                owner {
                    name {
                        value
                    }
                }
            }
        }
    }
    """ % (
        c1.id,
        p1.id,
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["car_update"]["ok"] is True
    assert result.data["car_update"]["object"]["owner"]["name"]["value"] == "John"

    car = await NodeManager.get_one(session=session, id=c1.id)
    car_peer = await car.owner.get_peer(session=session)
    assert car_peer.id == p1.id
    assert car.owner.get().is_protected is True


async def test_update_relationship_many(db, session, default_branch, person_tag_schema):

    t1 = await Node.init(session=session, schema="Tag")
    await t1.new(session=session, name="Blue", description="The Blue tag")
    await t1.save(session=session)
    t2 = await Node.init(session=session, schema="Tag")
    await t2.new(session=session, name="Red", description="The Red tag")
    await t2.save(session=session)
    t3 = await Node.init(session=session, schema="Tag")
    await t3.new(session=session, name="Black", description="The Black tag")
    await t3.save(session=session)

    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, firstname="John", lastname="Doe")
    await p1.save(session=session)

    query = """
    mutation {
        person_update(data: {id: "%s", tags: [ { id: "%s" } ] }) {
            ok
            object {
                id
                tags {
                    name {
                        value
                    }
                }
            }
        }
    }
    """ % (
        p1.id,
        t1.id,
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_update"]["ok"] is True
    assert len(result.data["person_update"]["object"]["tags"]) == 1

    p11 = await NodeManager.get_one(session=session, id=p1.id)
    assert len(list(p11.tags)) == 1

    # Replace the current value (t1) with t2 and t3
    query = """
    mutation {
        person_update(data: {id: "%s", tags: [ { id: "%s" }, { id: "%s" }] }) {
            ok
            object {
                id
                tags {
                    name {
                        value
                    }
                }
            }
        }
    }
    """ % (
        p1.id,
        t2.id,
        t3.id,
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_update"]["ok"] is True
    assert len(result.data["person_update"]["object"]["tags"]) == 2

    p12 = await NodeManager.get_one(session=session, id=p1.id)
    tags = p12.tags
    peers = [await tag.get_peer(session=session) for tag in tags]
    assert sorted([peer.name.value for peer in peers]) == ["Black", "Red"]

    # Replace the current value (t2, t3) with t1 and t3
    query = """
    mutation {
        person_update(data: {id: "%s", tags: [ { id: "%s" }, { id: "%s" }] }) {
            ok
            object {
                id
                tags {
                    name {
                        value
                    }
                }
            }
        }
    }
    """ % (
        p1.id,
        t1.id,
        t3.id,
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_update"]["ok"] is True
    assert len(result.data["person_update"]["object"]["tags"]) == 2

    p13 = await NodeManager.get_one(session=session, id=p1.id)
    tags = p13.tags
    peers = [await tag.get_peer(session=session) for tag in tags]
    assert sorted([peer.name.value for peer in peers]) == ["Black", "Blue"]


async def test_update_relationship_many2(db, session, default_branch, person_tag_schema):

    t1 = await Node.init(session=session, schema="Tag")
    await t1.new(session=session, name="Blue", description="The Blue tag")
    await t1.save(session=session)
    t2 = await Node.init(session=session, schema="Tag")
    await t2.new(session=session, name="Red", description="The Red tag")
    await t2.save(session=session)
    t3 = await Node.init(session=session, schema="Tag")
    await t3.new(session=session, name="Black", description="The Black tag")
    await t3.save(session=session)

    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, firstname="John", lastname="Doe")
    await p1.save(session=session)

    query = """
    mutation {
        person_update(data: {id: "%s", tags: [ { id: "%s" } ] }) {
            ok
            object {
                id
                tags {
                    name {
                        value
                    }
                }
            }
        }
    }
    """ % (
        p1.id,
        t1.id,
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_update"]["ok"] is True
    assert len(result.data["person_update"]["object"]["tags"]) == 1

    p11 = await NodeManager.get_one(session=session, id=p1.id)
    assert len(list(p11.tags)) == 1

    # Replace the current value (t1) with t2 and t3
    query = """
    mutation {
        person_update(data: {id: "%s", tags: [ { id: "%s" }, { id: "%s" }] }) {
            ok
            object {
                id
                tags {
                    name {
                        value
                    }
                }
            }
        }
    }
    """ % (
        p1.id,
        t2.id,
        t3.id,
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_update"]["ok"] is True
    assert len(result.data["person_update"]["object"]["tags"]) == 2

    p12 = await NodeManager.get_one(session=session, id=p1.id)
    tags = p12.tags
    peers = [await tag.get_peer(session=session) for tag in tags]
    assert sorted([peer.name.value for peer in peers]) == ["Black", "Red"]


@pytest.mark.skip(reason="Currently not working need to investigate")
async def test_update_relationship_previously_deleted(db, session, default_branch, person_tag_schema):

    t1 = await Node.init(session=session, schema="Tag")
    await t1.new(session=session, name="Blue", description="The Blue tag")
    await t1.save(session=session)
    t2 = await Node.init(session=session, schema="Tag")
    await t2.new(session=session, name="Red", description="The Red tag")
    await t2.save(session=session)
    t3 = await Node.init(session=session, schema="Tag")
    await t3.new(session=session, name="Black", description="The Black tag")
    await t3.save(session=session)

    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, firstname="John", lastname="Doe")
    await p1.save(session=session)

    query = """
    mutation {
        person_update(data: {id: "%s", tags: [ { id: "%s" } ] }) {
            ok
            object {
                id
                tags {
                    name {
                        value
                    }
                }
            }
        }
    }
    """ % (
        p1.id,
        t1.id,
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_update"]["ok"] is True
    assert len(result.data["person_update"]["object"]["tags"]) == 1

    p11 = await NodeManager.get_one(session=session, id=p1.id)
    assert len(list(p11.tags)) == 1

    # Replace the current value (t1) with t2 and t3
    query = """
    mutation {
        person_update(data: {id: "%s", tags: [ { id: "%s" }, { id: "%s" }] }) {
            ok
            object {
                id
                tags {
                    name {
                        value
                    }
                }
            }
        }
    }
    """ % (
        p1.id,
        t2.id,
        t3.id,
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_update"]["ok"] is True
    assert len(result.data["person_update"]["object"]["tags"]) == 2

    p12 = await NodeManager.get_one(session=session, id=p1.id)
    tags = p12.tags
    assert sorted([tag.peer.name.value for tag in tags]) == ["Black", "Red"]

    # Replace the current value (t2, t3) with t1 and t3
    query = """
    mutation {
        person_update(data: {id: "%s", tags: [ { id: "%s" }, { id: "%s" }] }) {
            ok
            object {
                id
                tags {
                    name {
                        value
                    }
                }
            }
        }
    }
    """ % (
        p1.id,
        t1.id,
        t3.id,
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=default_branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_update"]["ok"] is True
    assert len(result.data["person_update"]["object"]["tags"]) == 2

    p13 = await NodeManager.get_one(session=session, id=p1.id)
    tags = p13.tags
    assert sorted([tag.peer.name.value for tag in tags]) == ["Black", "Blue"]
