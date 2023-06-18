import pytest
from graphql import graphql
from neo4j import AsyncDriver, AsyncSession

from infrahub.core.branch import Branch
from infrahub.core.group import Group
from infrahub.core.node import Node
from infrahub.graphql import generate_graphql_schema


@pytest.fixture(autouse=True)
def load_graphql_requirements(group_graphql):
    pass


async def test_group_member_add(
    db: AsyncDriver, session: AsyncSession, person_john_main: Node, person_jim_main: Node, branch: Branch
):
    g1 = await Group.init(session=session, schema="StandardGroup", branch=branch)
    await g1.new(session=session, name="group-of-person")
    await g1.save(session=session)

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

    members = await g1.members.get()
    assert members == []
