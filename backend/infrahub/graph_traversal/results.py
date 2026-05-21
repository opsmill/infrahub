"""Structured result types returned by the graph-traversal Query classes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PathNodeData:
    uuid: str
    kind: str


@dataclass(frozen=True)
class PathHopData:
    node: PathNodeData
    # Schema relationship identifier (e.g. "device_interfaces") of the edge
    # traversed to reach this node from the previous hop. None on the first hop.
    relationship_identifier: str | None


@dataclass(frozen=True)
class PathData:
    hops: list[PathHopData]
    depth: int
