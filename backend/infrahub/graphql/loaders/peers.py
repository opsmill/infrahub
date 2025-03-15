from dataclasses import dataclass
from typing import Any

from aiodataloader import DataLoader

from infrahub.core.branch.models import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.relationship.model import Relationship
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

from .shared import to_frozen_set


@dataclass
class QueryPeerParams:
    branch: Branch | str
    source_kind: str
    schema: RelationshipSchema
    filters: dict[str, Any]
    fields: dict | None = None
    at: Timestamp | str | None = None
    branch_agnostic: bool = False

    def __hash__(self) -> int:
        frozen_fields: frozenset | None = None
        if self.fields:
            frozen_fields = to_frozen_set(self.fields)
        frozen_filters = to_frozen_set(self.filters)
        timestamp = Timestamp(self.at)
        branch = self.branch.name if isinstance(self.branch, Branch) else self.branch
        hash_str = "|".join(
            [
                str(hash(frozen_fields)),
                str(hash(frozen_filters)),
                timestamp.to_string(),
                branch,
                self.schema.name,
                str(self.source_kind),
                str(self.branch_agnostic),
            ]
        )
        return hash(hash_str)


class PeerRelationshipsDataLoader(DataLoader[str, list[Relationship]]):
    def __init__(self, db: InfrahubDatabase, query_params: QueryPeerParams, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.query_params = query_params
        self.db = db

    async def batch_load_fn(self, keys: list[Any]) -> list[list[Relationship]]:  # pylint: disable=method-hidden
        async with self.db.start_session() as db:
            peer_rels = await NodeManager.query_peers(
                db=db,
                ids=keys,
                source_kind=self.query_params.source_kind,
                schema=self.query_params.schema,
                filters=self.query_params.filters,
                fields=self.query_params.fields,
                at=self.query_params.at,
                branch=self.query_params.branch,
                branch_agnostic=self.query_params.branch_agnostic,
                fetch_peers=True,
            )
        peer_rels_by_node_id: dict[str, list[Relationship]] = {}
        for rel in peer_rels:
            node_id = rel.node_id
            if node_id not in peer_rels_by_node_id:
                peer_rels_by_node_id[node_id] = []
            peer_rels_by_node_id[node_id].append(rel)

        results = []
        for node_id in keys:
            results.append(peer_rels_by_node_id.get(node_id, []))
        return results
