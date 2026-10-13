from __future__ import annotations

import heapq
from collections import defaultdict
from typing import TYPE_CHECKING

from infrahub.graphql.cost.constants import TOP_NODES_LIMIT
from infrahub.graphql.cost.models import HistogramBucket, RelationshipSideStatistics, TopNode

if TYPE_CHECKING:
    from collections.abc import Iterable

    from infrahub.core.constants import RelationshipDirection
    from infrahub.graphql.cost.queries import RelationshipSideDegreeQueryResult


def _bucket_lower(peers: int) -> int:
    """Lower bound of the powers-of-two bucket holding a peer count: 0, 1, 2, 4, 8, and so on."""
    return 0 if peers == 0 else 1 << (peers.bit_length() - 1)


def _top_node_rank(node: TopNode) -> tuple[int, str]:
    return -node.peers, node.node_id


class RelationshipSideAccumulator:
    """Statistics of one relationship side of a kind, built from the peer counts of its nodes one chunk at a time.

    Every row of a node must come in the same chunk, and only the nodes with at least one peer have rows.
    """

    def __init__(self, identifier: str, direction: RelationshipDirection, kind: str) -> None:
        self.identifier = identifier
        self.direction = direction
        self.kind = kind
        self._bucket_node_counts: dict[int, int] = defaultdict(int)
        self._bucket_maximums: dict[int, int] = defaultdict(int)
        self._nodes_with_peers = 0
        self._total_peers = 0
        self._peers_by_kind: dict[str, int] = defaultdict(int)
        self._top_nodes: list[TopNode] = []

    def add_chunk(self, rows: Iterable[RelationshipSideDegreeQueryResult]) -> None:
        """Add the rows of the nodes of one chunk, one row for each node and concrete peer kind.

        Raises:
            ValueError: When a row has no peer.

        """
        peers_by_node: dict[str, int] = defaultdict(int)
        for row in rows:
            if row.peers < 1:
                raise ValueError(
                    f"The peer count must be at least 1, got {row.peers} for node {row.node_id} "
                    f"of {self.kind} through {self.identifier}"
                )
            peers_by_node[row.node_id] += row.peers
            self._peers_by_kind[row.peer_kind] += row.peers

        for peers in peers_by_node.values():
            lower = _bucket_lower(peers=peers)
            self._bucket_node_counts[lower] += 1
            self._bucket_maximums[lower] = max(self._bucket_maximums[lower], peers)
            self._total_peers += peers
        self._nodes_with_peers += len(peers_by_node)

        candidates = self._top_nodes + [
            TopNode(node_id=node_id, peers=peers) for node_id, peers in peers_by_node.items()
        ]
        self._top_nodes = heapq.nsmallest(TOP_NODES_LIMIT, candidates, key=_top_node_rank)

    def build(self, active_count: int) -> RelationshipSideStatistics:
        """Return the statistics, counting the active nodes that had no row as nodes without peers.

        Raises:
            ValueError: When more nodes have a peer than there are active nodes.

        """
        if active_count < self._nodes_with_peers:
            raise ValueError(
                f"{self._nodes_with_peers} nodes of {self.kind} have a peer through {self.identifier} "
                f"({self.direction.value}), more than its {active_count} active nodes"
            )
        node_counts = dict(self._bucket_node_counts)
        if active_count > self._nodes_with_peers:
            node_counts[0] = active_count - self._nodes_with_peers
        histogram = tuple(
            HistogramBucket(
                lower=lower,
                upper=max(2 * lower - 1, 0),
                node_count=node_counts[lower],
                max=self._bucket_maximums.get(lower, 0),
            )
            for lower in sorted(node_counts)
        )
        return RelationshipSideStatistics(
            identifier=self.identifier,
            direction=self.direction,
            nodes_with_peers=self._nodes_with_peers,
            total_peers=self._total_peers,
            peers_by_kind=dict(sorted(self._peers_by_kind.items())),
            histogram=histogram,
            top_nodes=tuple(self._top_nodes),
        )


def peers_at_percentile(statistics: RelationshipSideStatistics, percentile: int) -> int:
    """Return the peer count at a percentile of the nodes, read as the maximum of the bucket that holds it.

    The node at the percentile is the one of rank ceil(percentile * nodes / 100), counting from 1 in
    increasing order of peers; a side without nodes returns 0.

    Raises:
        ValueError: When the percentile is not between 1 and 100.

    """
    if not 1 <= percentile <= 100:
        raise ValueError(f"The percentile must be between 1 and 100, got {percentile}")
    node_count = sum(bucket.node_count for bucket in statistics.histogram)
    rank = -(-percentile * node_count // 100)
    nodes_up_to_bucket = 0
    for bucket in statistics.histogram:
        nodes_up_to_bucket += bucket.node_count
        if nodes_up_to_bucket >= rank:
            return bucket.max
    return 0


def max_peers(statistics: RelationshipSideStatistics) -> int:
    return statistics.histogram[-1].max if statistics.histogram else 0


def mean_peers(statistics: RelationshipSideStatistics) -> float:
    """Return the mean number of peers of the active nodes, 0 when there is no active node."""
    node_count = sum(bucket.node_count for bucket in statistics.histogram)
    return statistics.total_peers / node_count if node_count else 0.0
