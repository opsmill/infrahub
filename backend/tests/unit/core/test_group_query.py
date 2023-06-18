from neo4j import AsyncSession

from infrahub.core.branch import Branch
from infrahub.core.group import Group, GroupAssociationType
from infrahub.core.node import Node
from infrahub.core.query.group import (
    GroupAddAssociationQuery,
    GroupGetAssociationQuery,
    GroupHasAssociationQuery,
    GroupRemoveAssociationQuery,
)
from infrahub.core.utils import get_paths_between_nodes


async def test_query_GroupAddAssociationQuery(
    session: AsyncSession,
    group_group1_main: Group,
    person_john_main: Node,
    person_jim_main: Node,
    branch: Branch,
):
    group1 = group_group1_main

    group_members = [person_john_main, person_jim_main]
    for member in group_members:
        paths = await get_paths_between_nodes(
            session=session, source_id=group1.db_id, destination_id=member.db_id, max_length=1
        )
        assert len(paths) == 0

    query = await GroupAddAssociationQuery.init(
        session=session,
        branch=branch,
        association_type=GroupAssociationType.MEMBER,
        group=group1,
        node_ids=[person_john_main.id, person_jim_main.id],
    )
    await query.execute(session=session)

    group_members = [person_john_main, person_jim_main]
    for member in group_members:
        paths = await get_paths_between_nodes(
            session=session, source_id=group1.db_id, destination_id=member.db_id, max_length=1
        )
        assert len(paths) == 1


async def test_query_GroupGetAssociationQuery(
    session: AsyncSession,
    group_group1_main: Group,
    person_john_main: Node,
    person_jim_main: Node,
    branch: Branch,
):
    group1 = group_group1_main

    query = await GroupAddAssociationQuery.init(
        session=session,
        branch=branch,
        association_type=GroupAssociationType.MEMBER,
        group=group1,
        node_ids=[person_john_main.id, person_jim_main.id],
    )
    await query.execute(session=session)

    query = await GroupGetAssociationQuery.init(
        session=session, branch=branch, association_type=GroupAssociationType.MEMBER, group=group1
    )
    await query.execute(session=session)

    assert len(await query.get_members()) == 2


async def test_query_GroupHasAssociationQuery(
    session: AsyncSession,
    group_group1_members_main: Group,
    person_john_main: Node,
    person_jim_main: Node,
    person_albert_main: Node,
    branch: Branch,
):
    group1 = group_group1_members_main

    query = await GroupHasAssociationQuery.init(
        session=session,
        branch=branch,
        association_type=GroupAssociationType.MEMBER,
        group=group1,
        node_ids=[person_john_main.id, person_jim_main.id, person_albert_main.id],
    )
    await query.execute(session=session)
    memberships = await query.get_memberships()

    assert memberships[person_john_main.id] is True
    assert memberships[person_jim_main.id] is True
    assert memberships[person_albert_main.id] is False


async def test_query_GroupRemoveAssociationQuery(
    session: AsyncSession,
    group_group1_subscribers_main: Group,
    person_john_main: Node,
    person_jim_main: Node,
    person_albert_main: Node,
    branch: Branch,
):
    group1 = group_group1_subscribers_main

    group_members = [person_john_main, person_jim_main, person_albert_main]
    for member in group_members:
        paths = await get_paths_between_nodes(
            session=session, source_id=group1.db_id, destination_id=member.db_id, max_length=1
        )
        assert len(paths) == 1

    query = await GroupRemoveAssociationQuery.init(
        session=session,
        branch=branch,
        association_type=GroupAssociationType.SUBSCRIBER,
        group=group1,
        node_ids=[person_john_main.id, person_jim_main.id],
    )
    await query.execute(session=session)

    group_members = [person_john_main, person_jim_main]
    for member in group_members:
        paths = await get_paths_between_nodes(
            session=session, source_id=group1.db_id, destination_id=member.db_id, max_length=1
        )
        assert len(paths) == 2

    paths = await get_paths_between_nodes(
        session=session, source_id=group1.db_id, destination_id=person_albert_main.db_id, max_length=1
    )
    assert len(paths) == 1
