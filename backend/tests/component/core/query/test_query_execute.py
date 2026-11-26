from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.query.relationship import RelationshipGetPeerQuery
from infrahub.core.relationship import Relationship

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


@pytest.mark.parametrize("peer_count", [3, 6])
async def test_read_without_limit_returns_every_row_in_order(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_tag_schema: None,
    query_limit_of_one: None,
    peer_count: int,
) -> None:
    """A read with no limit returns every row in its order, even when it has more rows than the size limit."""
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

    query = await RelationshipGetPeerQuery.init(
        db=db,
        source=person,
        rel=Relationship(
            schema=person.get_schema().get_relationship(name="tags"),
            branch=default_branch,
            source_kind=person.get_kind(),
            node=person,
        ),
    )
    await query.execute(db=db)

    assert [peer.peer_id for peer in query.get_peers()] == [tag.id for tag in reversed(tags)]
