from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import BranchSupportType, RelationshipCardinality
from infrahub.graphql.cost.constants import ESTIMATE_FIELD_PATH
from infrahub.graphql.cost.models import FirstStepCounts, FirstStepKindCount, FirstStepPeerCount, FirstStepTopLevelCount
from infrahub.graphql.cost.queries import FirstStepNodesQuery, FirstStepPeerCountQuery, KindLabelCountQuery
from infrahub.graphql.cost.recorder import resolving_field
from infrahub.graphql.order import deserialize_order_input
from infrahub.graphql.resolvers.many_relationship import build_peer_filters
from infrahub.graphql.resolvers.resolver import build_node_list_filters, validate_offset_and_limit

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Sequence

    from infrahub.core.branch import Branch
    from infrahub.core.schema import RelationshipSchema
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.cost.models import CostTreeField


def concrete_kinds_of(tree: Iterable[CostTreeField]) -> set[str]:
    """Return the concrete kinds of every field of an estimation tree."""
    kinds: set[str] = set()
    for tree_field in tree:
        kinds.update(tree_field.concrete_kinds)
        kinds.update(concrete_kinds_of(tree=tree_field.children))
    return kinds


class FirstStepCounter:
    """Count the first step of a query on the branch and at the time the query reads.

    The first step is the nodes each top-level field returns and the peers of each relationship field directly
    under it. The queries run while the reserved estimate path is the current field, so their rows are reported
    apart from the rows of the fields.
    """

    def __init__(
        self, db: InfrahubDatabase, branch: Branch, at: Timestamp, schema_branch: SchemaBranch, query_size_limit: int
    ) -> None:
        """Prepare the counts of the first step of the queries on one branch and time.

        Args:
            query_size_limit: Most top-level nodes whose relationship fields are counted; a top-level field that
                returns more is counted without the fields under it.

        """
        self.db = db
        self.branch = branch
        self.at = at
        self.schema_branch = schema_branch
        self.query_size_limit = query_size_limit

    async def count(self, tree: Sequence[CostTreeField]) -> FirstStepCounts:
        """Count the top-level fields of an estimation tree, then the relationship fields directly under them.

        A top-level field filtered by its human-friendly ID is not counted, and only the current label counts of
        its kinds are read. Hierarchical fields, and fields that include the descendants of their parents, are
        not counted.

        Raises:
            GraphQLError: When the offset or the limit of a top-level field is negative.

        """
        top_level: dict[str, FirstStepTopLevelCount] = {}
        relationships: dict[str, tuple[FirstStepPeerCount, ...]] = {}
        label_counts: dict[str, int] = {}
        async with self.db.start_session(read_only=True) as db:
            with resolving_field(path=ESTIMATE_FIELD_PATH):
                for tree_field in tree:
                    filters = build_node_list_filters(arguments=tree_field.arguments)
                    kinds = concrete_kinds_of(tree=[tree_field])
                    if "hfid" in filters:
                        label_counts.update(await self._read_label_counts(db=db, kinds=kinds))
                        continue

                    counted, field_label_counts = await self._count_nodes(
                        db=db, tree_field=tree_field, filters=filters, label_count_kinds=kinds
                    )
                    top_level[tree_field.path] = counted
                    label_counts.update(field_label_counts)
                    if counted.exceeds_size_limit:
                        continue
                    for child in tree_field.children:
                        if _counts_peers(tree_field=child):
                            relationships[child.path] = await self._count_peers(db=db, tree_field=child, parent=counted)

        return FirstStepCounts(top_level=top_level, relationships=relationships, label_counts=label_counts)

    async def read_label_counts(self, kinds: Collection[str]) -> dict[str, int]:
        """Return the current label count of each kind, read while the reserved estimate path is the current field."""
        async with self.db.start_session(read_only=True) as db:
            with resolving_field(path=ESTIMATE_FIELD_PATH):
                return await self._read_label_counts(db=db, kinds=kinds)

    async def _read_label_counts(self, db: InfrahubDatabase, kinds: Collection[str]) -> dict[str, int]:
        if not kinds:
            return {}
        query = await KindLabelCountQuery.init(db=db, branch=self.branch, at=self.at, kinds=list(kinds))
        await query.execute(db=db)
        return {result.kind: result.count for result in query.get_data()}

    async def _count_nodes(
        self, db: InfrahubDatabase, tree_field: CostTreeField, filters: dict[str, Any], label_count_kinds: set[str]
    ) -> tuple[FirstStepTopLevelCount, dict[str, int]]:
        offset = _int_argument(tree_field=tree_field, name="offset")
        limit = _int_argument(tree_field=tree_field, name="limit")
        validate_offset_and_limit(offset=offset, limit=limit)
        query = await FirstStepNodesQuery.init(
            db=db,
            branch=self.branch,
            at=self.at,
            schema=self.schema_branch.get(name=tree_field.kind, duplicate=False),
            filters=filters or None,
            partial_match=bool(tree_field.arguments.get("partial_match")),
            order=deserialize_order_input(input_data=tree_field.arguments.get("order")),
            node_offset=offset,
            node_limit=limit,
            id_limit=self.query_size_limit,
            label_count_kinds=sorted(label_count_kinds),
        )
        await query.execute(db=db)
        result = query.get_data()

        kinds = tuple(
            FirstStepKindCount(kind=kind.kind, node_count=kind.node_count, node_ids=tuple(kind.node_ids))
            for kind in sorted(result.kinds, key=lambda kind: kind.kind)
        )
        counted = FirstStepTopLevelCount(
            kinds=kinds, exceeds_size_limit=sum(kind.node_count for kind in kinds) > self.query_size_limit
        )
        return counted, {label_count.kind: label_count.count for label_count in result.label_counts}

    async def _count_peers(
        self, db: InfrahubDatabase, tree_field: CostTreeField, parent: FirstStepTopLevelCount
    ) -> tuple[FirstStepPeerCount, ...]:
        source_ids = [
            node_id for kind in parent.kinds if kind.kind in tree_field.parent_kinds for node_id in kind.node_ids
        ]
        if not source_ids:
            return ()
        relationship = self._relationship_schema(tree_field=tree_field)
        query = await FirstStepPeerCountQuery.init(
            db=db,
            branch=self.branch,
            at=self.at,
            source_ids=source_ids,
            schema=relationship,
            filters=build_peer_filters(field_name=relationship.name, arguments=tree_field.arguments)
            if tree_field.cardinality == RelationshipCardinality.MANY
            else {},
            branch_agnostic=relationship.branch is BranchSupportType.AGNOSTIC,
        )
        await query.execute(db=db)
        return tuple(
            FirstStepPeerCount(
                peer_kind=peer_count.peer_kind,
                paths=peer_count.paths,
                distinct_peers=peer_count.distinct_peers,
                max_parents=peer_count.max_parents,
            )
            for peer_count in sorted(query.get_data(), key=lambda peer_count: peer_count.peer_kind)
        )

    def _relationship_schema(self, tree_field: CostTreeField) -> RelationshipSchema:
        """Return the schema of the relationship a field reads, from the first of its parent kinds that has it.

        Raises:
            ValueError: When no parent kind of the field has its relationship.

        """
        if tree_field.relationship is None:
            raise ValueError(f"The field '{tree_field.path}' reads no relationship")
        for kind in tree_field.parent_kinds:
            relationship = self.schema_branch.get(name=kind, duplicate=False).get_relationship_or_none(
                name=tree_field.relationship.name
            )
            if relationship is not None:
                return relationship
        raise ValueError(
            f"No parent kind of the field '{tree_field.path}' has the relationship '{tree_field.relationship.name}'"
        )


def _counts_peers(tree_field: CostTreeField) -> bool:
    """Tell whether the peers of a field directly under a top-level field are counted.

    The descendants a field can include, and the hierarchy fields, are read by other queries than the peer query.
    """
    return (
        tree_field.relationship is not None
        and not tree_field.relationship.hierarchical
        and not tree_field.arguments.get("include_descendants")
    )


def _int_argument(tree_field: CostTreeField, name: str) -> int | None:
    value = tree_field.arguments.get(name)
    return value if isinstance(value, int) and not isinstance(value, bool) else None
