import pytest
from graphql import graphql
from neo4j import AsyncSession

from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.graphql import generate_graphql_schema


async def test_update_simple_object(db, session: AsyncSession, person_john_main: Node, branch: Branch):
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
        % person_john_main.id
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_update"]["ok"] is True

    obj1 = await NodeManager.get_one(session=session, id=person_john_main.id, branch=branch)
    assert obj1.name.value == "Jim"
    assert obj1.height.value == 180


async def test_update_check_unique(
    db, session: AsyncSession, person_john_main: Node, person_jim_main: Node, branch: Branch
):
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
        % person_john_main.id
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert len(result.errors) == 1
    assert "An object already exist" in result.errors[0].message


async def test_update_object_with_flag_property(db, session: AsyncSession, person_john_main: Node, branch: Branch):
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
        % person_john_main.id
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_update"]["ok"] is True

    obj1 = await NodeManager.get_one(session=session, id=person_john_main.id, branch=branch)
    assert obj1.name.is_protected is True
    assert obj1.height.value == 180
    assert obj1.height.is_visible is False


@pytest.fixture
async def person_john_with_source_main(
    session: AsyncSession, default_branch: Branch, car_person_schema, first_account
) -> Node:
    obj = await Node.init(session=session, schema="Person", branch=default_branch)
    await obj.new(session=session, name={"value": "John", "source": first_account}, height=180)
    await obj.save(session=session)

    return obj


async def test_update_object_with_node_property(
    db,
    session: AsyncSession,
    person_john_with_source_main: Node,
    first_account: Node,
    second_account: Node,
    branch: Branch,
):
    query = """
    mutation {
        person_update(data: {id: "%s", name: { source: "%s" }, height: { source: "%s" } }) {
            ok
            object {
                id
            }
        }
    }
    """ % (
        person_john_with_source_main.id,
        second_account.id,
        second_account.id,
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_update"]["ok"] is True

    obj1 = await NodeManager.get_one(
        session=session, id=person_john_with_source_main.id, include_source=True, branch=branch
    )
    assert obj1.name.source_id == second_account.id
    assert obj1.height.source_id == second_account.id


async def test_update_invalid_object(
    db, session: AsyncSession, default_branch: Branch, car_person_schema, branch: Branch
):
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
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert len(result.errors) == 1
    assert "Unable to find the node XXXXXX / Person in the database." in result.errors[0].message


async def test_update_invalid_input(db, session: AsyncSession, person_john_main: Node, branch: Branch):
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
        % person_john_main.id
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert len(result.errors) == 1
    assert "String cannot represent a non string value" in result.errors[0].message


async def test_update_single_relationship(
    db, session: AsyncSession, person_john_main: Node, person_jim_main: Node, car_accord_main: Node, branch: Branch
):
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
        car_accord_main.id,
        person_jim_main.id,
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["car_update"]["ok"] is True
    assert result.data["car_update"]["object"]["owner"]["name"]["value"] == "Jim"

    car = await NodeManager.get_one(session=session, id=car_accord_main.id, branch=branch)
    car_peer = await car.owner.get_peer(session=session)
    assert car_peer.id == person_jim_main.id


async def test_update_new_single_relationship_flag_property(
    db, session: AsyncSession, person_john_main: Node, person_jim_main: Node, car_accord_main: Node, branch: Branch
):
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
        car_accord_main.id,
        person_jim_main.id,
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["car_update"]["ok"] is True
    assert result.data["car_update"]["object"]["owner"]["name"]["value"] == "Jim"

    car = await NodeManager.get_one(session=session, id=car_accord_main.id, branch=branch)
    car_peer = await car.owner.get_peer(session=session)
    assert car_peer.id == person_jim_main.id
    rm = await car.owner.get(session=session)
    assert rm.is_protected is True


async def test_update_delete_optional_relationship_cardinality_one(
    db, session: AsyncSession, person_jim_main: Node, car_accord_main: Node, branch: Branch
):
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
        car_accord_main.id,
        person_jim_main.id,
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["car_update"]["ok"] is True
    assert result.data["car_update"]["object"]["owner"]["name"]["value"] == "Jim"

    car = await NodeManager.get_one(session=session, id=car_accord_main.id, branch=branch)
    car_peer = await car.owner.get_peer(session=session)
    assert car_peer.id == person_jim_main.id
    query = """
    mutation {
        car_update(data: {id: "%s", owner: null}) {
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
        car_accord_main.id,
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["car_update"]["ok"] is True
    assert result.data["car_update"]["object"]["owner"] is None
    car = await NodeManager.get_one(session=session, id=car_accord_main.id, branch=branch)
    car_peer = await car.owner.get_peer(session=session)
    assert car_peer is None


async def test_update_existing_single_relationship_flag_property(
    db, session: AsyncSession, default_branch: Branch, person_john_main: Node, car_accord_main: Node, branch: Branch
):
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
        car_accord_main.id,
        person_john_main.id,
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["car_update"]["ok"] is True
    assert result.data["car_update"]["object"]["owner"]["name"]["value"] == "John"

    car = await NodeManager.get_one(session=session, id=car_accord_main.id, branch=branch)
    car_peer = await car.owner.get_peer(session=session)
    assert car_peer.id == person_john_main.id
    rm = await car.owner.get(session=session)
    assert rm.is_protected is True


@pytest.fixture
async def car_accord_with_source_main(
    session: AsyncSession, default_branch: Branch, car_person_schema, person_john_main: Node, first_account: Node
) -> Node:
    obj = await Node.init(session=session, schema="Car", branch=default_branch)
    await obj.new(
        session=session,
        name="accord",
        nbr_seats=5,
        is_electric=False,
        owner={"id": person_john_main.id, "_relation__source": first_account.id},
    )
    await obj.save(session=session)

    return obj


async def test_update_existing_single_relationship_node_property(
    db,
    session: AsyncSession,
    person_john_main: Node,
    car_accord_with_source_main: Node,
    first_account: Node,
    second_account: Node,
    branch: Branch,
):
    query = """
    mutation {
        car_update(data: {id: "%s", owner: { id: "%s", _relation__source: "%s" }}) {
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
        car_accord_with_source_main.id,
        person_john_main.id,
        second_account.id,
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["car_update"]["ok"] is True
    assert result.data["car_update"]["object"]["owner"]["name"]["value"] == "John"

    car = await NodeManager.get_one(session=session, id=car_accord_with_source_main.id, branch=branch)
    car_peer = await car.owner.get_peer(session=session)
    assert car_peer.id == person_john_main.id
    rm = await car.owner.get(session=session)
    source = await rm.get_source(session=session)
    assert isinstance(source, Node)
    assert source.id == second_account.id


async def test_update_relationship_many(
    db,
    session: AsyncSession,
    person_jack_main: Node,
    tag_blue_main: Node,
    tag_red_main: Node,
    tag_black_main: Node,
    branch: Branch,
):
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
        person_jack_main.id,
        tag_blue_main.id,
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_update"]["ok"] is True
    assert len(result.data["person_update"]["object"]["tags"]) == 1

    p11 = await NodeManager.get_one(session=session, id=person_jack_main.id, branch=branch)
    assert len(list(await p11.tags.get(session=session))) == 1

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
        person_jack_main.id,
        tag_red_main.id,
        tag_black_main.id,
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_update"]["ok"] is True
    assert len(result.data["person_update"]["object"]["tags"]) == 2

    p12 = await NodeManager.get_one(session=session, id=person_jack_main.id, branch=branch)
    tags = await p12.tags.get(session=session)
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
        person_jack_main.id,
        tag_blue_main.id,
        tag_black_main.id,
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_update"]["ok"] is True
    assert len(result.data["person_update"]["object"]["tags"]) == 2

    p13 = await NodeManager.get_one(session=session, id=person_jack_main.id, branch=branch)
    tags = await p13.tags.get(session=session)
    peers = [await tag.get_peer(session=session) for tag in tags]
    assert sorted([peer.name.value for peer in peers]) == ["Black", "Blue"]


async def test_update_relationship_many2(
    db,
    session: AsyncSession,
    person_jack_main: Node,
    tag_blue_main: Node,
    tag_red_main: Node,
    tag_black_main: Node,
    branch: Branch,
):
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
        person_jack_main.id,
        tag_blue_main.id,
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_update"]["ok"] is True
    assert len(result.data["person_update"]["object"]["tags"]) == 1

    p11 = await NodeManager.get_one(session=session, id=person_jack_main.id, branch=branch)
    assert len(list(await p11.tags.get(session=session))) == 1

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
        person_jack_main.id,
        tag_red_main.id,
        tag_black_main.id,
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_update"]["ok"] is True
    assert len(result.data["person_update"]["object"]["tags"]) == 2

    p12 = await NodeManager.get_one(session=session, id=person_jack_main.id, branch=branch)
    tags = await p12.tags.get(session=session)
    peers = [await tag.get_peer(session=session) for tag in tags]
    assert sorted([peer.name.value for peer in peers]) == ["Black", "Red"]


@pytest.mark.xfail(reason="Currently not working need to investigate")
async def test_update_relationship_previously_deleted(
    db,
    session: AsyncSession,
    person_jack_main: Node,
    tag_blue_main: Node,
    tag_red_main: Node,
    tag_black_main: Node,
    branch: Branch,
):
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
        person_jack_main.id,
        tag_blue_main.id,
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_update"]["ok"] is True
    assert len(result.data["person_update"]["object"]["tags"]) == 1

    p11 = await NodeManager.get_one(session=session, id=person_jack_main.id, branch=branch)
    assert len(list(await p11.tags.get(session=session))) == 1

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
        person_jack_main.id,
        tag_red_main.id,
        tag_black_main.id,
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_update"]["ok"] is True
    assert len(result.data["person_update"]["object"]["tags"]) == 2

    p12 = await NodeManager.get_one(session=session, id=person_jack_main.id, branch=branch)
    tags = await p12.tags.get(session=session)
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
        person_jack_main.id,
        tag_blue_main.id,
        tag_black_main.id,
    )
    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data["person_update"]["ok"] is True
    assert len(result.data["person_update"]["object"]["tags"]) == 2

    p13 = await NodeManager.get_one(session=session, id=person_jack_main.id, branch=branch)
    tags = await p13.tags.get(session=session)
    assert sorted([tag.peer.name.value for tag in tags]) == ["Black", "Blue"]
