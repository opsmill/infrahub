import pytest

from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.graph_traversal.path import PathTraversalQuery


@pytest.fixture
async def jack_with_blue_tag(
    db: InfrahubDatabase, default_branch: Branch, person_tag_schema: None, tag_blue_main: Node
) -> tuple[Node, Node]:
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, firstname="Jack", lastname="Russell", primary_tag=tag_blue_main)
    await person.save(db=db)
    return person, tag_blue_main


async def test_returns_direct_peer_path_on_default_branch(
    db: InfrahubDatabase, default_branch: Branch, jack_with_blue_tag: tuple[Node, Node]
) -> None:
    person, tag = jack_with_blue_tag

    query = await PathTraversalQuery.init(
        db=db,
        branch=default_branch,
        source_id=person.id,
        destination_id=tag.id,
        excluded_namespaces=[],
    )
    await query.execute(db=db)
    paths = query.get_paths()

    assert len(paths) >= 1
    shortest = paths[0]
    assert shortest.depth == 1
    assert len(shortest.hops) == 2
    assert shortest.hops[0].node.uuid == person.id
    assert shortest.hops[0].relationship_identifier is None
    assert shortest.hops[-1].node.uuid == tag.id
    assert shortest.hops[-1].relationship_identifier


async def test_returns_direct_peer_path_on_non_default_branch(
    db: InfrahubDatabase, default_branch: Branch, jack_with_blue_tag: tuple[Node, Node]
) -> None:
    person, tag = jack_with_blue_tag
    feature_branch = await create_branch(db=db, branch_name="feature")

    query = await PathTraversalQuery.init(
        db=db,
        branch=feature_branch,
        source_id=person.id,
        destination_id=tag.id,
        excluded_namespaces=[],
    )
    await query.execute(db=db)
    paths = query.get_paths()

    assert len(paths) >= 1
    assert paths[0].depth == 1
    assert paths[0].hops[0].node.uuid == person.id
    assert paths[0].hops[0].relationship_identifier is None
    assert paths[0].hops[-1].node.uuid == tag.id
    assert paths[0].hops[-1].relationship_identifier
