from __future__ import annotations

from dataclasses import dataclass
from itertools import batched
from typing import TYPE_CHECKING

from infrahub.core.schema import GenericSchema, NodeSchema, ProfileSchema, TemplateSchema
from infrahub.graphql.cost.histogram import RelationshipSideAccumulator
from infrahub.graphql.cost.models import KindStatistics
from infrahub.graphql.cost.queries import KindActiveNodeIdsQuery, KindLabelCountQuery, RelationshipSideDegreeQuery
from infrahub.telemetry.queries import CountNodesByKindsQuery

if TYPE_CHECKING:
    from collections.abc import Collection

    from infrahub.core.branch import Branch
    from infrahub.core.constants import RelationshipDirection
    from infrahub.core.schema import NonGenericSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class RelationshipSide:
    identifier: str
    direction: RelationshipDirection
    """Direction of the edges, seen from a node of the kind that holds the side."""


@dataclass(frozen=True)
class CollectedStatistics:
    kinds: tuple[KindStatistics, ...]
    query_count: int
    """Database queries run to read the statistics."""

    @property
    def side_count(self) -> int:
        return sum(len(kind.relationships) for kind in self.kinds)


class StatisticsCollector:
    """Read the statistics of every concrete kind of a branch, scoping each degree query to a chunk of node ids.

    For each relationship of a kind, both sides are read: the side of the kind, and the opposite side of each
    concrete peer kind, since the largest number of nodes that reach one peer needs the opposite side even when
    the peer kind declares no relationship back.
    """

    def __init__(self, db: InfrahubDatabase, branch: Branch, schema_branch: SchemaBranch, chunk_size: int) -> None:
        if chunk_size < 1:
            raise ValueError(f"The chunk size must be at least 1, got {chunk_size}")
        self.db = db
        self.branch = branch
        self.schema_branch = schema_branch
        self.chunk_size = chunk_size

    async def collect(self, at: Timestamp) -> CollectedStatistics:
        """Read the statistics as the branch stands at the given time, so nodes changed during the run do not count."""
        schemas = self._list_concrete_schemas()
        if not schemas:
            return CollectedStatistics(kinds=(), query_count=0)
        sides_by_kind = self._list_sides(schemas=schemas)

        label_count_query = await KindLabelCountQuery.init(
            db=self.db, branch=self.branch, at=at, kinds=[schema.kind for schema in schemas]
        )
        await label_count_query.execute(db=self.db)
        label_counts = {result.kind: result.count for result in label_count_query.get_data()}

        active_count_query = await CountNodesByKindsQuery.init(db=self.db, branch=self.branch, at=at, schemas=schemas)
        await active_count_query.execute(db=self.db)
        active_counts = {result.kind: result.count for result in active_count_query.get_data()}

        query_count = 2
        kinds: list[KindStatistics] = []
        for schema in schemas:
            active_count = active_counts.get(schema.kind, 0)
            node_ids: list[str] = []
            if active_count:
                node_ids, id_query_count = await self._read_active_node_ids(kind=schema.kind, at=at)
                query_count += id_query_count

            relationships = []
            for side in sides_by_kind[schema.kind]:
                accumulator = RelationshipSideAccumulator(
                    identifier=side.identifier, direction=side.direction, kind=schema.kind
                )
                for node_ids_chunk in batched(node_ids, self.chunk_size):
                    degree_query = await RelationshipSideDegreeQuery.init(
                        db=self.db,
                        branch=self.branch,
                        at=at,
                        kind=schema.kind,
                        node_ids=node_ids_chunk,
                        identifier=side.identifier,
                        direction=side.direction,
                    )
                    await degree_query.execute(db=self.db)
                    query_count += 1
                    accumulator.add_chunk(rows=degree_query.get_data())
                relationships.append(accumulator.build(active_count=active_count))

            kinds.append(
                KindStatistics(
                    kind=schema.kind,
                    label_count=label_counts.get(schema.kind, 0),
                    active_count=active_count,
                    relationships=tuple(relationships),
                )
            )
        return CollectedStatistics(kinds=tuple(kinds), query_count=query_count)

    def _list_concrete_schemas(self) -> list[NonGenericSchemaTypes]:
        all_schemas = self.schema_branch.get_all(duplicate=False)
        schemas = [all_schemas[kind] for kind in sorted(all_schemas)]
        return [schema for schema in schemas if isinstance(schema, NodeSchema | ProfileSchema | TemplateSchema)]

    def _list_sides(self, schemas: list[NonGenericSchemaTypes]) -> dict[str, list[RelationshipSide]]:
        concrete_kinds = {schema.kind for schema in schemas}
        sides: dict[str, set[RelationshipSide]] = {kind: set() for kind in concrete_kinds}
        for schema in schemas:
            for relationship in schema.relationships:
                identifier = relationship.get_identifier()
                sides[schema.kind].add(RelationshipSide(identifier=identifier, direction=relationship.direction))
                opposite_side = RelationshipSide(
                    identifier=identifier, direction=relationship.direction.neighbor_direction
                )
                for peer_kind in self._list_concrete_kinds(kind=relationship.peer, concrete_kinds=concrete_kinds):
                    sides[peer_kind].add(opposite_side)
        return {
            kind: sorted(kind_sides, key=lambda side: (side.identifier, side.direction.value))
            for kind, kind_sides in sides.items()
        }

    def _list_concrete_kinds(self, kind: str, concrete_kinds: Collection[str]) -> list[str]:
        schema = self.schema_branch.get(name=kind, duplicate=False)
        if isinstance(schema, GenericSchema):
            return [used_by for used_by in schema.used_by if used_by in concrete_kinds]
        return [kind] if kind in concrete_kinds else []

    async def _read_active_node_ids(self, kind: str, at: Timestamp) -> tuple[list[str], int]:
        """Return the ids of the kind's nodes active on the branch, and the number of queries that read them."""
        node_ids: list[str] = []
        query_count = 0
        offset = 0
        while True:
            query = await KindActiveNodeIdsQuery.init(
                db=self.db, branch=self.branch, at=at, kind=kind, limit=self.chunk_size, offset=offset
            )
            await query.execute(db=self.db)
            query_count += 1
            page = list(query.get_data())
            node_ids.extend(row.node_id for row in page if row.is_active)
            if len(page) < self.chunk_size:
                return node_ids, query_count
            offset += self.chunk_size
