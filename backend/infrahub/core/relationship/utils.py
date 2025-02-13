from infrahub.core.query.relationship import RelationshipGetPeerQuery
from infrahub.core.relationship import Relationship
from infrahub.core.schema import RelationshipSchema
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


async def query_peers_relationships(  # type: ignore[no-untyped-def]
    db: InfrahubDatabase,
    source_ids: list[str],
    source_kind: str,
    rel_schema: RelationshipSchema,
    filters: dict,
    at: Timestamp,
    branch,  # from infrahub.core.branch import Branch leads to circular import and cannot be used within TYPE_CHECKING block. Why?
    branch_agnostic: bool = False,
    offset: int | None = None,
    limit: int | None = None,
) -> list[Relationship]:
    rel = Relationship(schema=rel_schema, branch=branch, node_id="PLACEHOLDER")

    query = await RelationshipGetPeerQuery.init(
        db=db,
        source_ids=source_ids,
        source_kind=source_kind,
        schema=rel_schema,
        filters=filters,
        rel=rel,
        offset=offset,
        limit=limit,
        at=at,
        branch_agnostic=branch_agnostic,
    )
    await query.execute(db=db)

    rels = [
        await Relationship(schema=rel_schema, branch=branch, at=at, node_id=str(peer.source_id)).load(
            db=db,
            id=peer.rel_node_id,
            db_id=peer.rel_node_db_id,
            updated_at=peer.updated_at,
            data=peer,
        )
        for peer in query.get_peers()
    ]
    return rels
