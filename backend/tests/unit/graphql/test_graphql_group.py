import pytest
from graphql import graphql
from neo4j import AsyncDriver, AsyncSession

from infrahub.core.branch import Branch
from infrahub.core.group import Group
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.graphql import generate_graphql_schema


@pytest.fixture(autouse=True)
def load_graphql_requirements(group_graphql):
    pass


async def test_group_member_add(
    db: AsyncDriver,
    session: AsyncSession,
    group_group1_main: Group,
    person_john_main: Node,
    person_jim_main: Node,
    person_albert_main: Node,
    branch: Branch,
):
    g1 = group_group1_main

    query = """
    mutation {
        group_member_add(data: {
            id: "%s",
            members: ["%s", "%s"],
        }) {
            ok
        }
    }
    """ % (
        g1.id,
        person_john_main.id,
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

    g1: Group = await NodeManager.get_one(session=session, id=g1.id, branch=branch)

    members = await g1.members.get(session=session)
    assert sorted(members) == sorted(
        [
            person_john_main.id,
            person_jim_main.id,
        ]
    )

    # --------------------------------------
    # Add a Third member
    # --------------------------------------
    query = """
    mutation {
        group_member_add(data: {
            id: "%s",
            members: ["%s"],
        }) {
            ok
        }
    }
    """ % (
        g1.id,
        person_albert_main.id,
    )

    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    members = await g1.members.get(session=session)
    assert sorted(members) == sorted([person_john_main.id, person_jim_main.id, person_albert_main.id])


async def test_group_member_remove(
    db: AsyncDriver,
    session: AsyncSession,
    group_group1_members_main: Group,
    person_john_main: Node,
    person_jim_main: Node,
    person_albert_main: Node,
    branch: Branch,
):
    g1 = group_group1_members_main

    query = """
    mutation {
        group_member_remove(data: {
            id: "%s",
            members: ["%s"],
        }) {
            ok
        }
    }
    """ % (
        g1.id,
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

    g1: Group = await NodeManager.get_one(session=session, id=g1.id, branch=branch)

    members = await g1.members.get(session=session)
    assert sorted(members) == sorted(
        [
            person_jim_main.id,
        ]
    )

    # --------------------------------------
    # Remove the second one with another on that is not part of the group
    # --------------------------------------
    query = """
    mutation {
        group_member_remove(data: {
            id: "%s",
            members: ["%s", "%s"],
        }) {
            ok
        }
    }
    """ % (
        g1.id,
        person_albert_main.id,
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

    members = await g1.members.get(session=session)
    assert members == []


async def test_group_subscriber_add(
    db: AsyncDriver,
    session: AsyncSession,
    group_group1_main: Group,
    person_john_main: Node,
    person_jim_main: Node,
    person_albert_main: Node,
    branch: Branch,
):
    g1 = group_group1_main

    query = """
    mutation {
        group_subscriber_add(data: {
            id: "%s",
            subscribers: ["%s", "%s"],
        }) {
            ok
        }
    }
    """ % (
        g1.id,
        person_john_main.id,
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

    g1: Group = await NodeManager.get_one(session=session, id=g1.id, branch=branch)

    subscribers = await g1.subscribers.get(session=session)
    assert sorted(subscribers) == sorted(
        [
            person_john_main.id,
            person_jim_main.id,
        ]
    )

    # --------------------------------------
    # Add a Third Subscriber
    # --------------------------------------
    query = """
    mutation {
        group_subscriber_add(data: {
            id: "%s",
            subscribers: ["%s"],
        }) {
            ok
        }
    }
    """ % (
        g1.id,
        person_albert_main.id,
    )

    result = await graphql(
        schema=await generate_graphql_schema(session=session, include_subscription=False, branch=branch),
        source=query,
        context_value={"infrahub_session": session, "infrahub_database": db, "infrahub_branch": branch},
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    subscribers = await g1.subscribers.get(session=session)
    assert sorted(subscribers) == sorted([person_john_main.id, person_jim_main.id, person_albert_main.id])


async def test_group_subscriber_remove(
    db: AsyncDriver,
    session: AsyncSession,
    group_group1_subscribers_main: Group,
    person_john_main: Node,
    person_jim_main: Node,
    person_albert_main: Node,
    branch: Branch,
):
    g1 = group_group1_subscribers_main

    query = """
    mutation {
        group_subscriber_remove(data: {
            id: "%s",
            subscribers: ["%s"],
        }) {
            ok
        }
    }
    """ % (
        g1.id,
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

    g1: Group = await NodeManager.get_one(session=session, id=g1.id, branch=branch)

    subscribers = await g1.subscribers.get(session=session)
    assert sorted(subscribers) == sorted([person_jim_main.id, person_albert_main.id])

    # --------------------------------------
    # Remove the second one with another on that is not part of the group
    # --------------------------------------
    query = """
    mutation {
        group_subscriber_remove(data: {
            id: "%s",
            subscribers: ["%s", "%s"],
        }) {
            ok
        }
    }
    """ % (
        g1.id,
        person_john_main.id,
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

    subscribers = await g1.subscribers.get(session=session)
    assert subscribers == [person_albert_main.id]


async def test_query_group_members(
    db: AsyncDriver,
    session: AsyncSession,
    group_group1_members_main: Group,
    branch: Branch,
):
    pass

    query = """
    query {
        group {
            count
            edges {
                node {
                    id
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

    expected_results = {
        "group": {
            "count": 1,
            "edges": [{"node": {"id": group_group1_members_main.id}}],
        },
    }

    assert result.errors is None
    assert result.data == expected_results
