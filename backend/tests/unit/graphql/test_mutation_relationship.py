import uuid

import pytest
from graphql import graphql
from neo4j import AsyncDriver, AsyncSession

from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.graphql import generate_graphql_schema


@pytest.fixture(autouse=True)
def load_graphql_requirements(group_graphql):
    pass


async def test_relationship_add(
    db: AsyncDriver,
    session: AsyncSession,
    person_jack_main: Node,
    tag_blue_main: Node,
    tag_red_main: Node,
    tag_black_main: Node,
    branch: Branch,
):
    query = """
    mutation {
        relationship_add(data: {
            id: "%s",
            name: "tags",
            nodes: [{id: "%s"}, {id: "%s"}],
        }) {
            ok
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

    p1 = await NodeManager.get_one(session=session, id=person_jack_main.id, branch=branch)

    tags = await p1.tags.get(session=session)
    assert sorted([tag.peer_id for tag in tags]) == sorted(
        [
            tag_blue_main.id,
            tag_black_main.id,
        ]
    )

    # --------------------------------------
    # Add a Third member
    # --------------------------------------
    query = """
    mutation {
        relationship_add(data: {
            id: "%s",
            name: "tags",
            nodes: [{id: "%s"}, {id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        person_jack_main.id,
        tag_blue_main.id,
        tag_red_main.id,
    )

    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    p1 = await NodeManager.get_one(session=session, id=person_jack_main.id, branch=branch)

    tags = await p1.tags.get(session=session)
    assert sorted([tag.peer_id for tag in tags]) == sorted(
        [
            tag_blue_main.id,
            tag_black_main.id,
            tag_red_main.id,
        ]
    )


async def test_relationship_remove(
    db: AsyncDriver,
    session: AsyncSession,
    person_jack_tags_main: Node,
    tag_blue_main: Node,
    tag_red_main: Node,
    tag_black_main: Node,
    branch: Branch,
):
    query = """
    mutation {
        relationship_remove(data: {
            id: "%s",
            name: "tags",
            nodes: [{id: "%s"}, {id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        person_jack_tags_main.id,
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

    p1 = await NodeManager.get_one(session=session, id=person_jack_tags_main.id, branch=branch)

    tags = await p1.tags.get(session=session)
    assert sorted([tag.peer_id for tag in tags]) == sorted(
        [
            tag_red_main.id,
        ]
    )

    # --------------------------------------
    # remove the second one
    # --------------------------------------
    query = """
    mutation {
        relationship_remove(data: {
            id: "%s",
            name: "tags",
            nodes: [{id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        person_jack_tags_main.id,
        tag_red_main.id,
    )

    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    p1 = await NodeManager.get_one(session=session, id=person_jack_tags_main.id, branch=branch)

    tags = await p1.tags.get(session=session)
    assert [tag.peer_id for tag in tags] == sorted([])


async def test_relationship_wrong_name(
    db: AsyncDriver,
    session: AsyncSession,
    person_jack_main: Node,
    tag_blue_main: Node,
    tag_red_main: Node,
    tag_black_main: Node,
    branch: Branch,
):
    query = """
    mutation {
        relationship_add(data: {
            id: "%s",
            name: "notvalid",
            nodes: [{id: "%s"}],
        }) {
            ok
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

    assert result.errors
    assert result.errors[0].message == "'notvalid' is not a valid relationship for 'Person'"

    # Relationship existing relationship with the wrong cardinality
    query = """
    mutation {
        relationship_add(data: {
            id: "%s",
            name: "primary_tag",
            nodes: [{id: "%s"}],
        }) {
            ok
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

    assert result.errors
    assert result.errors[0].message == "'primary_tag' must be a relationship of cardinality Many"


async def test_relationship_wrong_node(
    db: AsyncDriver,
    session: AsyncSession,
    person_jack_main: Node,
    tag_blue_main: Node,
    tag_red_main: Node,
    tag_black_main: Node,
    branch: Branch,
):
    # Non existing Node
    bad_uuid = str(uuid.uuid4())
    query = """
    mutation {
        relationship_add(data: {
            id: "%s",
            name: "tags",
            nodes: [{id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        person_jack_main.id,
        bad_uuid,
    )

    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert result.errors[0].message == f"'{bad_uuid}': Unable to find the node in the database."

    # Wrong Kind
    query = """
    mutation {
        relationship_add(data: {
            id: "%s",
            name: "tags",
            nodes: [{id: "%s"}],
        }) {
            ok
        }
    }
    """ % (
        person_jack_main.id,
        person_jack_main.id,
    )

    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert result.errors[0].message == f"'{person_jack_main.id}' 'Person' is not a valid peer for 'Tag'"
