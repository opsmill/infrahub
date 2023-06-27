import pytest
from deepdiff import DeepDiff
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
    assert sorted(members.keys()) == sorted([person_john_main.id, person_jim_main.id, person_albert_main.id])


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
    assert sorted(members.keys()) == sorted(
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
    assert members == {}


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
    assert sorted(subscribers.keys()) == sorted(
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
    assert sorted(subscribers.keys()) == sorted([person_john_main.id, person_jim_main.id, person_albert_main.id])


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
    assert sorted(subscribers.keys()) == sorted([person_jim_main.id, person_albert_main.id])

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
    assert list(subscribers.keys()) == [person_albert_main.id]


async def test_query_groups(
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


async def test_query_group_members_same_type(
    db: AsyncDriver,
    session: AsyncSession,
    group_group1_members_main: Group,
    group_group2_subscribers_main: Group,
    person_john_main: Node,
    person_jim_main: Node,
    branch: Branch,
):
    query = """
    query {
        group {
            count
            edges {
                node {
                    id
                    members {
                        count
                        edges {
                            node {
                                id
                            }
                        }
                    }
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
            "count": 2,
            "edges": [
                {
                    "node": {
                        "id": group_group1_members_main.id,
                        "members": {
                            "count": 2,
                            "edges": [
                                {
                                    "node": {
                                        "id": person_john_main.id,
                                    },
                                },
                                {
                                    "node": {
                                        "id": person_jim_main.id,
                                    },
                                },
                            ],
                        },
                    },
                },
                {
                    "node": {
                        "id": group_group2_subscribers_main.id,
                        "members": {"count": 0, "edges": []},
                    },
                },
            ],
        },
    }

    assert result.errors is None
    assert DeepDiff(expected_results, result.data, ignore_order=True).to_dict() == {}


async def test_query_group_subscribers_different_type(
    db: AsyncDriver,
    session: AsyncSession,
    group_group2_subscribers_main: Group,
    person_john_main: Node,
    person_jim_main: Node,
    car_volt_main: Node,
    car_accord_main: Node,
    branch: Branch,
):
    query = """
    query {
        group {
            count
            edges {
                node {
                    id
                    subscribers {
                        count
                        edges {
                            node {
                                display_label
                                id
                                __typename
                                ...on Car {
                                    is_electric {
                                        value
                                    }
                                }
                            }
                        }
                    }
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
            "edges": [
                {
                    "node": {
                        "id": group_group2_subscribers_main.id,
                        "subscribers": {
                            "count": 4,
                            "edges": [
                                {
                                    "node": {
                                        "__typename": "Person",
                                        "display_label": "John",
                                        "id": person_john_main.id,
                                    },
                                },
                                {
                                    "node": {
                                        "__typename": "Person",
                                        "display_label": "Jim",
                                        "id": person_jim_main.id,
                                    },
                                },
                                {
                                    "node": {
                                        "__typename": "Car",
                                        "display_label": "volt #444444",
                                        "id": car_volt_main.id,
                                        "is_electric": {"value": True},
                                    },
                                },
                                {
                                    "node": {
                                        "__typename": "Car",
                                        "display_label": "accord #444444",
                                        "id": car_accord_main.id,
                                        "is_electric": {"value": False},
                                    },
                                },
                            ],
                        },
                    },
                },
            ],
        },
    }

    assert result.errors is None
    assert DeepDiff(expected_results, result.data, ignore_order=True, ignore_private_variables=False).to_dict() == {}


async def test_query_groups_per_node(
    db: AsyncDriver,
    session: AsyncSession,
    group_group1_members_main: Group,
    group_group2_members_main: Group,
    person_john_main: Node,
    person_jim_main: Node,
    person_albert_main: Node,
    branch: Branch,
):
    pass

    query = """
    query {
        person {
            count
            edges {
                node {
                    id
                    display_label
                }
                groups {
                    member {
                        count
                        edges {
                            node {
                                id
                                display_label
                            }
                        }
                    }
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
        "person": {
            "count": 3,
            "edges": [
                {
                    "groups": {
                        "member": {
                            "count": 2,
                            "edges": [
                                {
                                    "node": {
                                        "display_label": "group1",
                                        "id": group_group1_members_main.id,
                                    },
                                },
                                {
                                    "node": {
                                        "display_label": "group2",
                                        "id": group_group2_members_main.id,
                                    },
                                },
                            ],
                        },
                    },
                    "node": {"display_label": "John", "id": person_john_main.id},
                },
                {
                    "groups": {
                        "member": {
                            "count": 1,
                            "edges": [
                                {
                                    "node": {
                                        "display_label": "group1",
                                        "id": group_group1_members_main.id,
                                    },
                                },
                            ],
                        },
                    },
                    "node": {"display_label": "Jim", "id": person_jim_main.id},
                },
                {
                    "groups": {
                        "member": {
                            "count": 1,
                            "edges": [
                                {
                                    "node": {
                                        "display_label": "group2",
                                        "id": group_group2_members_main.id,
                                    },
                                },
                            ],
                        },
                    },
                    "node": {"display_label": "Albert", "id": person_albert_main.id},
                },
            ],
        },
    }

    assert result.errors is None
    assert DeepDiff(expected_results, result.data, ignore_order=True, ignore_private_variables=False).to_dict() == {}
