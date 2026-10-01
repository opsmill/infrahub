from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.manager import NodeManager
from infrahub.database import DatabaseType
from infrahub.profiles.queries.get_profile_data import GetProfileDataQuery, RelationshipFilter
from tests.component.profiles.queries.helpers import ALL_FILTERS, Peers, create_node

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase


def _sum_db_hits(operator: dict[str, Any]) -> int:
    return operator["dbHits"] + sum(_sum_db_hits(operator=child) for child in operator.get("children", []))


async def _count_db_hits(
    db: InfrahubDatabase, branch: Branch, profile_id: str, include_relationships: list[RelationshipFilter]
) -> int:
    query = await GetProfileDataQuery.init(
        db=db,
        branch=branch,
        profile_ids=[profile_id],
        attr_names=["description", "status"],
        include_relationships=include_relationships,
    )
    rendered = query.render()
    # Plan again with the current statistics: an old plan from a smaller database can scan full relationship indexes.
    await db.execute_query(query="CALL db.prepareForReplanning()")
    _, metadata = await db.execute_query_with_metadata(
        query=f"PROFILE\n{rendered.text}", params=rendered.params, name=query.name, type=query.type
    )
    return _sum_db_hits(operator=metadata["profile"])


async def _create_linked_profile(
    db: InfrahubDatabase, branch: Branch, peers: Peers, name: str, linked_nodes: int
) -> Node:
    profile = await create_node(
        db=db,
        branch=branch,
        kind="ProfileTestDevice",
        profile_name=name,
        profile_priority=10,
        description=name,
        site=peers.sites[0],
        rack=peers.racks[0],
        labels=peers.labels[:2],
    )
    for idx in range(linked_nodes):
        await create_node(db=db, branch=branch, kind="TestDevice", name=f"{name}-device-{idx}", profiles=[profile])
    return profile


@pytest.mark.parametrize(
    "include_relationships",
    [pytest.param([], id="attributes-only"), pytest.param(ALL_FILTERS, id="with-relationship-filters")],
)
async def test_db_hits_do_not_grow_with_linked_nodes(
    db: InfrahubDatabase, default_branch: Branch, peers: Peers, include_relationships: list[RelationshipFilter]
) -> None:
    if db.db_type != DatabaseType.NEO4J:
        pytest.skip("PROFILE and db.prepareForReplanning() exist only in Neo4j")

    few = await _create_linked_profile(db=db, branch=default_branch, peers=peers, name="few", linked_nodes=2)
    many = await _create_linked_profile(db=db, branch=default_branch, peers=peers, name="many", linked_nodes=10)
    many = await NodeManager.get_one(db=db, branch=default_branch, id=many.id, raise_on_error=True)
    assert len(await many.related_nodes.get_relationships(db=db)) == 10

    few_hits = await _count_db_hits(
        db=db, branch=default_branch, profile_id=few.id, include_relationships=include_relationships
    )
    many_hits = await _count_db_hits(
        db=db, branch=default_branch, profile_id=many.id, include_relationships=include_relationships
    )

    assert many_hits == few_hits
