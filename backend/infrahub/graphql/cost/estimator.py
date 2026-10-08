from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core.constants import RelationshipCardinality
from infrahub.graphql.cost.constants import TOP_NODES_LIMIT
from infrahub.graphql.cost.models import (
    CostFigures,
    EstimateMode,
    EstimateReason,
    EstimateSource,
    FieldDescription,
    FieldEstimate,
    QueryEstimate,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from infrahub.graphql.cost.models import (
        CostTreeField,
        FirstStepCounts,
        FirstStepRelationshipCount,
        FirstStepTopLevelCount,
        KindStatistics,
        RelationshipRef,
        RelationshipSideStatistics,
        StatisticsSnapshot,
    )


def estimate(
    tree: Sequence[CostTreeField],
    snapshot: StatisticsSnapshot | None,
    first_step: FirstStepCounts | None,
    label_counts: Mapping[str, int],
    reads_main_now: bool,
) -> QueryEstimate:
    """Estimate the nodes, resolver calls and database rows of each field of a query.

    Each field passes to the fields under it, for each concrete kind of its nodes, the expected number of
    paths of the query that reach those nodes, the worst-case number of paths, and the worst-case number of
    paths that reach one node:

    - Expected nodes: the parent paths times the mean number of peers of the parent kind (for a
      cardinality-one field, the share of parent nodes with a peer), split between the concrete peer kinds
      in proportion to their stored totals.
    - Worst-case nodes: the parent paths are given to the parent nodes with the most peers first, at most
      the worst-case paths per node on each node; the listed nodes count with their exact peers, every other
      node with the largest peer count of its histogram bucket. Without a histogram, each parent path gets
      the largest peer count. The worst-case paths per node of the next step are the worst-case paths per
      parent node times the largest number of parents of one peer.
    - Resolver calls: one for each parent path, and one for a top-level field.
    - Database rows, for each node read: one row of the list or peer query (none for a cardinality-one
      field, whose peer ID is read with its parent), one row for the node, one for each selected attribute
      and one for each selected cardinality-one relationship; plus one row for each resolver call when the
      field selects `count`. A cardinality-one field that selects only the ID of its peer reads no row.
      Display labels, profile values and permission filtering are not counted.

    The top-level fields, and the fields directly under them, take the counts of the first step when it was
    counted. A top-level field estimated from the statistics has the node count of each kind scaled by its
    current label count, capped by its offset, limit and the IDs it is given; when every ID given is listed
    among the nodes with the most peers of a field under it, that field takes their stored peer counts.

    Args:
        first_step: Counts read on the branch and at the time of the request, or None for an estimate from
            the statistics only.
        label_counts: Current label count of each kind; a kind without one is taken as unchanged since the
            statistics were computed.
        reads_main_now: The request reads the default branch at the current time, the only case in which the
            worst case is a bound.

    Raises:
        ValueError: When a field under another field reads no relationship.

    """
    estimates: dict[str, FieldEstimate] = {}
    if snapshot is None:
        for tree_field in tree:
            _add_without_statistics(estimates=estimates, tree_field=tree_field)
    else:
        estimator = _QueryEstimator(
            snapshot=snapshot,
            first_step=first_step,
            label_counts=label_counts,
            reads_main_now=reads_main_now,
            estimates=estimates,
        )
        for tree_field in tree:
            estimator.add_top_level(tree_field=tree_field)

    return QueryEstimate(
        mode=EstimateMode.COUNTED_FIRST_STEP if first_step is not None else EstimateMode.STATISTICS_ONLY,
        statistics=snapshot.pointer if snapshot is not None else None,
        estimates=estimates,
    )


@dataclass(frozen=True, slots=True)
class _KindPaths:
    """Paths of the query that reach the nodes of one concrete kind at one field."""

    expected: float
    worst_case: int
    worst_case_per_node: int
    """Largest number of these paths that can reach one node."""


@dataclass(frozen=True, slots=True)
class _Step:
    """Figures of one field, and the paths it passes to the fields under it."""

    expected_nodes: float
    worst_case_nodes: int
    expected_calls: float
    worst_case_calls: int
    peer_paths: Mapping[str, _KindPaths]
    source: EstimateSource


@dataclass(frozen=True, slots=True)
class _KindPeers:
    """Peers that the paths reaching one parent kind return."""

    expected: float
    worst_case: int
    overflow: int
    """Worst-case peers of the paths that the stored parent nodes cannot take, which only data added since the
    statistics were computed can produce."""


@dataclass(frozen=True, slots=True)
class _PeerWindow:
    """Peers that one resolver call returns, given the offset and limit of the field."""

    offset: int
    limit: int | None

    @classmethod
    def of(cls, tree_field: CostTreeField) -> _PeerWindow:
        return cls(
            offset=_int_argument(tree_field=tree_field, name="offset") or 0,
            limit=_int_argument(tree_field=tree_field, name="limit"),
        )

    def count(self, peers: int) -> int:
        returned = max(0, peers - self.offset)
        return returned if self.limit is None else min(returned, self.limit)

    def mean(self, peers: float) -> float:
        returned = max(0.0, peers - self.offset)
        return returned if self.limit is None else min(returned, self.limit)


class _QueryEstimator:
    def __init__(
        self,
        snapshot: StatisticsSnapshot,
        first_step: FirstStepCounts | None,
        label_counts: Mapping[str, int],
        reads_main_now: bool,
        estimates: dict[str, FieldEstimate],
    ) -> None:
        self.snapshot = snapshot
        self.first_step = first_step
        self.label_counts = label_counts
        self.reads_main_now = reads_main_now
        self.estimates = estimates

    def add_top_level(self, tree_field: CostTreeField) -> None:
        counted = self.first_step.top_level.get(tree_field.path) if self.first_step is not None else None
        if counted is not None:
            step = self._counted_top_level(counted=counted)
        else:
            step = self._statistics_top_level(tree_field=tree_field)
        if step is None:
            _add_without_statistics(estimates=self.estimates, tree_field=tree_field)
            return

        self._add(tree_field=tree_field, step=step)
        listed_ids = _literal_ids(tree_field=tree_field) if step.source == EstimateSource.STATISTICS else ()
        for child in tree_field.children:
            self._add_relationship(
                tree_field=child,
                parent_paths=step.peer_paths,
                counted_parent=counted is not None and not counted.exceeds_size_limit,
                listed_ids=listed_ids,
            )

    def _counted_top_level(self, counted: FirstStepTopLevelCount) -> _Step | None:
        node_counts = {count.kind: count.node_count for count in counted.kinds if count.node_count > 0}
        if any(kind not in self.snapshot.kinds for kind in node_counts):
            return None
        total = sum(node_counts.values())
        return _Step(
            expected_nodes=total,
            worst_case_nodes=total,
            expected_calls=1,
            worst_case_calls=1,
            peer_paths={
                kind: _KindPaths(expected=count, worst_case=count, worst_case_per_node=1)
                for kind, count in node_counts.items()
            },
            source=EstimateSource.COUNTED,
        )

    def _statistics_top_level(self, tree_field: CostTreeField) -> _Step | None:
        expected_by_kind: dict[str, float] = {}
        worst_case_by_kind: dict[str, int] = {}
        for kind in tree_field.concrete_kinds:
            current_label_count = self.label_counts.get(kind)
            kind_statistics = self.snapshot.kinds.get(kind)
            if kind_statistics is None:
                if current_label_count == 0:
                    continue
                return None
            expected_by_kind[kind], worst_case_by_kind[kind] = _scaled_node_count(
                kind_statistics=kind_statistics, current_label_count=current_label_count
            )

        available = sum(expected_by_kind.values())
        expected_total = _returned_nodes(tree_field=tree_field, available=available)
        worst_case_total = int(_returned_nodes(tree_field=tree_field, available=sum(worst_case_by_kind.values())))
        share = expected_total / available if available else 0.0
        return _Step(
            expected_nodes=expected_total,
            worst_case_nodes=worst_case_total,
            expected_calls=1,
            worst_case_calls=1,
            peer_paths={
                kind: _KindPaths(
                    expected=expected_by_kind[kind] * share,
                    worst_case=min(worst_case_by_kind[kind], worst_case_total),
                    worst_case_per_node=1,
                )
                for kind in expected_by_kind
            },
            source=EstimateSource.STATISTICS,
        )

    def _add_relationship(
        self,
        tree_field: CostTreeField,
        parent_paths: Mapping[str, _KindPaths],
        counted_parent: bool,
        listed_ids: tuple[str, ...],
    ) -> None:
        relationship = tree_field.relationship
        if relationship is None:
            raise ValueError(f"The field '{tree_field.path}' is under another field but reads no relationship")
        if relationship.hierarchical:
            _add_without_statistics(estimates=self.estimates, tree_field=tree_field)
            return

        applicable_paths = {kind: paths for kind, paths in parent_paths.items() if kind in tree_field.parent_kinds}
        sides: dict[str, tuple[RelationshipSideStatistics, KindStatistics]] = {}
        for kind, paths in applicable_paths.items():
            if paths.worst_case == 0:
                continue
            side = self.snapshot.side(identifier=relationship.identifier, direction=relationship.direction, kind=kind)
            kind_statistics = self.snapshot.kinds.get(kind)
            if side is None or kind_statistics is None:
                _add_without_statistics(estimates=self.estimates, tree_field=tree_field)
                return
            sides[kind] = (side, kind_statistics)

        counted = (
            self.first_step.relationships.get(tree_field.path)
            if counted_parent and self.first_step is not None
            else None
        )
        if counted is not None:
            step = self._counted_relationship(parent_paths=applicable_paths, counted=counted)
        else:
            step = self._statistics_relationship(
                tree_field=tree_field,
                relationship=relationship,
                parent_paths=applicable_paths,
                sides=sides,
                listed_ids=listed_ids,
            )

        self._add(tree_field=tree_field, step=step)
        for child in tree_field.children:
            self._add_relationship(tree_field=child, parent_paths=step.peer_paths, counted_parent=False, listed_ids=())

    def _counted_relationship(
        self, parent_paths: Mapping[str, _KindPaths], counted: FirstStepRelationshipCount
    ) -> _Step:
        return _Step(
            expected_nodes=counted.returned_paths,
            worst_case_nodes=counted.returned_paths,
            expected_calls=sum(paths.expected for paths in parent_paths.values()),
            worst_case_calls=sum(paths.worst_case for paths in parent_paths.values()),
            peer_paths={
                peer_count.peer_kind: _KindPaths(
                    expected=min(peer_count.expected_returned_paths, peer_count.max_returned_paths),
                    worst_case=peer_count.max_returned_paths,
                    worst_case_per_node=min(peer_count.max_parents, peer_count.max_returned_paths),
                )
                for peer_count in counted.peer_kinds
            },
            source=EstimateSource.COUNTED,
        )

    def _statistics_relationship(
        self,
        tree_field: CostTreeField,
        relationship: RelationshipRef,
        parent_paths: Mapping[str, _KindPaths],
        sides: Mapping[str, tuple[RelationshipSideStatistics, KindStatistics]],
        listed_ids: tuple[str, ...],
    ) -> _Step:
        """Estimate the peers of the parent paths from the statistics of each parent kind.

        A parent node given by its ID and listed among the nodes with the most peers takes its stored peer
        count, and the other IDs are estimated from the other nodes of the kind.
        """
        node_ids = tuple(dict.fromkeys(listed_ids))
        listed_by_kind = _listed_peer_counts(sides=sides, node_ids=node_ids)
        listed_ids_found = frozenset(node_id for listed in listed_by_kind.values() for node_id in listed)
        window = _PeerWindow.of(tree_field=tree_field)

        expected_nodes = 0.0
        worst_case_nodes = 0
        expected_calls = 0.0
        worst_case_calls = 0
        expected_by_peer: dict[str, float] = defaultdict(float)
        worst_case_by_peer: dict[str, int] = defaultdict(int)
        parent_paths_per_node: dict[str, int] = defaultdict(int)
        for kind, (side, kind_statistics) in sides.items():
            listed = listed_by_kind.get(kind, {})
            paths = parent_paths[kind]
            if listed_ids_found:
                unlisted = len(node_ids) - len(listed_ids_found)
                paths = _KindPaths(
                    expected=paths.expected * unlisted / len(node_ids),
                    worst_case=min(unlisted, paths.worst_case),
                    worst_case_per_node=1,
                )
            peers = _kind_peers(
                tree_field=tree_field,
                side=side,
                active_count=kind_statistics.active_count,
                paths=paths,
                excluded_node_ids=listed_ids_found,
            )
            listed_peers = sum(window.count(peers=peer_count) for peer_count in listed.values())
            expected_kind_peers = listed_peers + peers.expected
            worst_case_kind_peers = listed_peers + peers.worst_case
            expected_nodes += expected_kind_peers
            worst_case_nodes += worst_case_kind_peers
            expected_calls += len(listed) + paths.expected
            worst_case_calls += len(listed) + paths.worst_case
            for peer_kind, peer_total in side.peers_by_kind.items():
                if not peer_total:
                    continue
                expected_by_peer[peer_kind] += expected_kind_peers * peer_total / side.total_peers
                worst_case_by_peer[peer_kind] += min(
                    worst_case_kind_peers, paths.worst_case_per_node * peer_total + peers.overflow
                )
                parent_paths_per_node[peer_kind] = max(parent_paths_per_node[peer_kind], paths.worst_case_per_node)

        return _Step(
            expected_nodes=expected_nodes,
            worst_case_nodes=worst_case_nodes,
            expected_calls=expected_calls,
            worst_case_calls=worst_case_calls,
            peer_paths=self._peer_paths(
                relationship=relationship,
                expected_by_peer=expected_by_peer,
                worst_case_by_peer=worst_case_by_peer,
                parent_paths_per_node=parent_paths_per_node,
            ),
            source=EstimateSource.STATISTICS,
        )

    def _peer_paths(
        self,
        relationship: RelationshipRef,
        expected_by_peer: Mapping[str, float],
        worst_case_by_peer: Mapping[str, int],
        parent_paths_per_node: Mapping[str, int],
    ) -> dict[str, _KindPaths]:
        peer_paths: dict[str, _KindPaths] = {}
        for peer_kind, worst_case in worst_case_by_peer.items():
            opposite_side = self.snapshot.side(
                identifier=relationship.identifier, direction=relationship.direction.neighbor_direction, kind=peer_kind
            )
            largest_parents = _largest_peer_count(side=opposite_side) if opposite_side is not None else None
            peer_paths[peer_kind] = _KindPaths(
                # IDs that are not listed are estimated from the mean of the whole kind, listed nodes included,
                # which can put the expected figure above the bound.
                expected=min(expected_by_peer[peer_kind], worst_case),
                worst_case=worst_case,
                worst_case_per_node=worst_case
                if largest_parents is None
                else min(worst_case, parent_paths_per_node[peer_kind] * largest_parents),
            )
        return peer_paths

    def _add(self, tree_field: CostTreeField, step: _Step) -> None:
        expected_nodes = step.expected_nodes if tree_field.selects_nodes else 0.0
        worst_case_nodes = step.worst_case_nodes if tree_field.selects_nodes else 0
        field_estimate = FieldEstimate(
            field=_describe(tree_field=tree_field),
            expected=CostFigures(
                nodes=_round(expected_nodes),
                resolver_calls=_round(step.expected_calls),
                database_rows=_round(
                    _database_rows(tree_field=tree_field, nodes=expected_nodes, calls=step.expected_calls)
                ),
            ),
            worst_case=CostFigures(
                nodes=worst_case_nodes,
                resolver_calls=step.worst_case_calls,
                database_rows=math.ceil(
                    _database_rows(tree_field=tree_field, nodes=worst_case_nodes, calls=step.worst_case_calls)
                ),
            ),
            source=step.source,
            worst_case_is_bound=self.reads_main_now,
            reason=None,
        )
        _record(estimates=self.estimates, path=tree_field.path, field_estimate=field_estimate)


def _add_without_statistics(estimates: dict[str, FieldEstimate], tree_field: CostTreeField) -> None:
    _record(
        estimates=estimates,
        path=tree_field.path,
        field_estimate=FieldEstimate(
            field=_describe(tree_field=tree_field),
            expected=None,
            worst_case=None,
            source=None,
            worst_case_is_bound=False,
            reason=EstimateReason.NO_STATISTICS,
        ),
    )
    for child in tree_field.children:
        _add_without_statistics(estimates=estimates, tree_field=child)


def _record(estimates: dict[str, FieldEstimate], path: str, field_estimate: FieldEstimate) -> None:
    """Add the estimate of a field, or add it to the estimate of another field with the same path.

    Only a field whose alias is `edges` or `node` shares the path of its parent, and the actual counts of both
    are recorded under that path too.
    """
    existing = estimates.get(path)
    if existing is None:
        estimates[path] = field_estimate
        return
    if (
        existing.expected is None
        or existing.worst_case is None
        or field_estimate.expected is None
        or field_estimate.worst_case is None
    ):
        estimates[path] = FieldEstimate(
            field=existing.field,
            expected=None,
            worst_case=None,
            source=None,
            worst_case_is_bound=False,
            reason=EstimateReason.NO_STATISTICS,
        )
        return
    estimates[path] = FieldEstimate(
        field=existing.field,
        expected=_add_figures(existing.expected, field_estimate.expected),
        worst_case=_add_figures(existing.worst_case, field_estimate.worst_case),
        source=EstimateSource.COUNTED
        if existing.source == field_estimate.source == EstimateSource.COUNTED
        else EstimateSource.STATISTICS,
        worst_case_is_bound=existing.worst_case_is_bound and field_estimate.worst_case_is_bound,
        reason=None,
    )


def _add_figures(first: CostFigures, second: CostFigures) -> CostFigures:
    return CostFigures(
        nodes=first.nodes + second.nodes,
        resolver_calls=first.resolver_calls + second.resolver_calls,
        database_rows=first.database_rows + second.database_rows,
    )


def _describe(tree_field: CostTreeField) -> FieldDescription:
    return FieldDescription(
        kind=tree_field.kind,
        relationship_identifier=tree_field.relationship.identifier if tree_field.relationship is not None else None,
        cardinality=tree_field.cardinality,
    )


def _kind_peers(
    tree_field: CostTreeField,
    side: RelationshipSideStatistics,
    active_count: int,
    paths: _KindPaths,
    excluded_node_ids: frozenset[str],
) -> _KindPeers:
    """Estimate the peers that the paths reaching one parent kind return, the excluded parent nodes left out."""
    window = _PeerWindow.of(tree_field=tree_field)
    stored_peers = side.nodes_with_peers if tree_field.cardinality == RelationshipCardinality.ONE else side.total_peers
    mean = window.mean(peers=stored_peers / active_count if active_count else 0.0)

    sequence = _peer_count_sequence(side=side, excluded_node_ids=excluded_node_ids)
    if sequence is None:
        largest = window.count(peers=side.top_nodes[0].peers if side.top_nodes else 0)
        worst_case = paths.worst_case * largest
        return _KindPeers(expected=paths.expected * min(mean, largest), worst_case=worst_case, overflow=worst_case)

    returned = sorted(((window.count(peers=peers), node_count) for peers, node_count in sequence), reverse=True)
    node_total = sum(node_count for _, node_count in returned)
    sequence_mean = sum(peers * node_count for peers, node_count in returned) / node_total if node_total else 0.0
    assigned, leftover = _assign_paths(sequence=returned, paths=paths.worst_case, per_node=paths.worst_case_per_node)
    overflow = leftover * (returned[0][0] if returned else 0)
    return _KindPeers(
        expected=paths.expected * min(mean, sequence_mean), worst_case=assigned + overflow, overflow=overflow
    )


def _peer_count_sequence(
    side: RelationshipSideStatistics, excluded_node_ids: frozenset[str]
) -> list[tuple[int, int]] | None:
    """Return the peer counts of the nodes as (peers, number of nodes), or None when no histogram is stored.

    A listed node counts with its exact peers, unless it is excluded. Every other node counts with the
    maximum of its bucket, and never more than the listed node with the fewest peers; when fewer nodes than
    the list holds have a peer, every node with a peer is listed and the others have none.
    """
    if not side.histogram:
        return None
    listed = [node.peers for node in side.top_nodes]
    unlisted_by_bucket = {bucket.lower: bucket.node_count for bucket in side.histogram}
    for peers in listed:
        for bucket in side.histogram:
            if bucket.lower <= peers <= bucket.upper and unlisted_by_bucket[bucket.lower]:
                unlisted_by_bucket[bucket.lower] -= 1
                break
    unlisted_ceiling = min(listed) if len(listed) >= TOP_NODES_LIMIT else 0
    return [(node.peers, 1) for node in side.top_nodes if node.node_id not in excluded_node_ids] + [
        (min(bucket.max, unlisted_ceiling), unlisted_by_bucket[bucket.lower])
        for bucket in side.histogram
        if unlisted_by_bucket[bucket.lower]
    ]


def _listed_peer_counts(
    sides: Mapping[str, tuple[RelationshipSideStatistics, KindStatistics]], node_ids: tuple[str, ...]
) -> dict[str, dict[str, int]]:
    """Return the stored peer counts of the given nodes listed among the nodes with the most peers, by kind."""
    listed_by_kind: dict[str, dict[str, int]] = defaultdict(dict)
    for node_id in node_ids:
        for kind, (side, _) in sides.items():
            peers = next((node.peers for node in side.top_nodes if node.node_id == node_id), None)
            if peers is not None:
                listed_by_kind[kind][node_id] = peers
                break
    return listed_by_kind


def _assign_paths(sequence: Sequence[tuple[int, int]], paths: int, per_node: int) -> tuple[int, int]:
    """Give the paths to the nodes with the most peers first, at most `per_node` paths on each node.

    Returns:
        The peers the assigned paths return, and the paths left over when the nodes cannot take them all.

    """
    remaining = paths
    peers_total = 0
    for peers, node_count in sequence:
        if remaining == 0:
            break
        assigned = min(remaining, node_count * per_node)
        peers_total += assigned * peers
        remaining -= assigned
    return peers_total, remaining


def _largest_peer_count(side: RelationshipSideStatistics) -> int | None:
    if side.histogram:
        return side.histogram[-1].max
    if side.top_nodes:
        return side.top_nodes[0].peers
    return None


def _scaled_node_count(kind_statistics: KindStatistics, current_label_count: int | None) -> tuple[float, int]:
    """Return the expected and the worst-case active nodes of a kind now, from its label count now and then."""
    if current_label_count is None:
        return float(kind_statistics.active_count), kind_statistics.active_count
    if kind_statistics.label_count == 0:
        return float(current_label_count), current_label_count
    scaled = kind_statistics.active_count * current_label_count
    return scaled / kind_statistics.label_count, -(-scaled // kind_statistics.label_count)


def _returned_nodes(tree_field: CostTreeField, available: float) -> float:
    returned = max(0.0, available - (_int_argument(tree_field=tree_field, name="offset") or 0))
    for cap in (_int_argument(tree_field=tree_field, name="limit"), tree_field.max_matching_nodes):
        if cap is not None:
            returned = min(returned, cap)
    return returned


def _database_rows(tree_field: CostTreeField, nodes: float, calls: float) -> float:
    if tree_field.id_only:
        return 0.0
    rows_per_node = 1 + tree_field.selected_attribute_count + tree_field.selected_cardinality_one_count
    if tree_field.relationship is None or tree_field.cardinality == RelationshipCardinality.MANY:
        rows_per_node += 1
    return nodes * rows_per_node + (calls if tree_field.selects_count else 0.0)


def _int_argument(tree_field: CostTreeField, name: str) -> int | None:
    value = tree_field.arguments.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return max(0, value)


def _literal_ids(tree_field: CostTreeField) -> tuple[str, ...]:
    ids = tree_field.arguments.get("ids")
    if not isinstance(ids, list) or not all(isinstance(node_id, str) for node_id in ids):
        return ()
    return tuple(ids)


def _round(value: float) -> int:
    return math.floor(value + 0.5)
