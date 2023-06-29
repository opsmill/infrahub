from neo4j import AsyncSession

from infrahub.core.branch import Branch
from infrahub.core.group import Group
from infrahub.core.node import Node
from infrahub.core.utils import get_paths_between_nodes


async def test_group_add(
    session: AsyncSession,
    group_schema,
    person_john_main: Node,
    person_jim_main: Node,
    branch: Branch,
):
    g1 = await Group.init(session=session, schema="StandardGroup")
    await g1.new(session=session, name="group-of-person")
    await g1.save(session=session)

    await g1.members.add(session=session, nodes=person_john_main)
    await g1.members.add(session=session, nodes=person_jim_main)

    group_members = [person_john_main, person_jim_main]
    for member in group_members:
        paths = await get_paths_between_nodes(
            session=session, source_id=g1.db_id, destination_id=member.db_id, max_length=1
        )
        assert len(paths) == 1


async def test_group_get(
    session: AsyncSession,
    group_schema,
    person_john_main: Node,
    person_jim_main: Node,
    branch: Branch,
):
    g1 = await Group.init(session=session, schema="StandardGroup")
    await g1.new(session=session, name="group-of-person")
    await g1.save(session=session)

    await g1.members.add(session=session, nodes=[person_john_main, person_jim_main])

    member_ids = await g1.members.get(session=session)
    assert sorted(member_ids) == sorted([person_john_main.id, person_jim_main.id])

    await g1.members.add(session=session, nodes=[person_john_main.id, person_jim_main.id])
    member_ids = await g1.members.get(session=session)
    assert sorted(member_ids) == sorted([person_john_main.id, person_jim_main.id])
