from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.query.relationship import RelationshipGetPeerQuery
from infrahub.core.relationship import Relationship
from tests.helpers.db_query_counter import CountingInfrahubDatabase

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


@pytest.mark.parametrize("peer_count", [3, 6])
async def test_read_without_limit_runs_once(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_tag_schema: None,
    query_limit_of_one: None,
    peer_count: int,
) -> None:
    """A read with no limit runs once and keeps its order, whatever its row count against the size limit."""
    # Saved in the reverse of the order the query sorts them, so a read in save order fails.
    tags: list[Node] = []
    for index in reversed(range(peer_count)):
        tag = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
        await tag.new(db=db, name=f"tag-{index}")
        await tag.save(db=db)
        tags.append(tag)
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, firstname="Read", lastname="Once", tags=tags)
    await person.save(db=db)
    counting_db = CountingInfrahubDatabase.from_db(db=db)

    query = await RelationshipGetPeerQuery.init(
        db=counting_db,
        source=person,
        rel=Relationship(
            schema=person.get_schema().get_relationship(name="tags"),
            branch=default_branch,
            source_kind=person.get_kind(),
            node=person,
        ),
    )
    await query.execute(db=counting_db)

    assert [peer.peer_id for peer in query.get_peers()] == [tag.id for tag in reversed(tags)]
    assert counting_db.count_for(RelationshipGetPeerQuery.name) == 1
    assert counting_db.rows_for(RelationshipGetPeerQuery.name) == peer_count
