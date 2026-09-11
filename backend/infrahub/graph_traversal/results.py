"""Structured result types returned by the graph-traversal Query classes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.core.constants import RelationshipDirection


@dataclass(frozen=True)
class PathNodeData:
    uuid: str
    kind: str


@dataclass(frozen=True)
class PathHopData:
    node: PathNodeData
    # Schema relationship identifier (e.g. "device_interfaces") of the edge
    # traversed to reach this node from the previous hop.
    relationship_identifier: str
    # Direction the source end of this hop declares, read from the stored edge orientation.
    # The destination end holds ``from_direction.neighbor_direction``.
    from_direction: RelationshipDirection


@dataclass(frozen=True)
class PathData:
    start_node: PathNodeData
    hops: list[PathHopData]
    depth: int


@dataclass(frozen=True)
class PathTraversalResult:
    """Outcome of a by-id path traversal.

    ``truncated_at_depth`` is ``None`` when the search ran to completion (``max_paths`` reached or
    every reachable path enumerated). It is set to the depth at which a query exceeded its budget,
    in which case ``paths`` holds only the paths found at shallower depths and deeper paths may exist.
    """

    paths: list[PathData]
    truncated_at_depth: int | None = None
