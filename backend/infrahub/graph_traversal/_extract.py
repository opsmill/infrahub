"""Internal helpers for converting QueryResult rows into ``PathData``.

The shape consumed here is the projection produced by the QPP renderer:
``start_node_uuid``, ``start_node_kind``, ``hops`` (list of
``{relationship_identifier, uuid, kind}``), and ``depth``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from infrahub.graph_traversal.results import PathData, PathHopData, PathNodeData

if TYPE_CHECKING:
    from infrahub.core.query import QueryResult


class _HopRow(TypedDict):
    relationship_identifier: str
    uuid: str
    kind: str


def extract_path_from_result(result: QueryResult) -> PathData | None:
    """Build a ``PathData`` from one row of the QPP projection.

    Returns ``None`` when the row is missing a start node or has no hops.
    """
    start_node = PathNodeData(
        uuid=result.get_as_str(label="start_node_uuid") or "",
        kind=result.get_as_str(label="start_node_kind") or "",
    )
    hop_rows = result.get_as_list_of_type(label="hops", return_type=_HopRow)
    depth = result.get_as_type(label="depth", return_type=int)
    if not start_node.uuid or not hop_rows:
        return None
    hops = [
        PathHopData(
            node=PathNodeData(uuid=row["uuid"], kind=row["kind"]),
            relationship_identifier=row["relationship_identifier"],
        )
        for row in hop_rows
    ]
    return PathData(start_node=start_node, hops=hops, depth=depth)


def extract_half_path_from_result(result: QueryResult) -> tuple[str, list[PathHopData]] | None:
    """Build one half-path from a row of the exhaustive half-enumeration projection.

    Returns ``(mid_uuid, hops)`` where ``mid_uuid`` is the half's free endpoint (left half) or
    start (right half) and ``hops`` runs outward from the fixed anchor. Returns ``None`` when the
    row carries no middle uuid.
    """
    mid_uuid = result.get_as_str(label="mid_uuid")
    if not mid_uuid:
        return None
    hop_rows = result.get_as_list_of_type(label="hops", return_type=_HopRow)
    hops = [
        PathHopData(
            node=PathNodeData(uuid=row["uuid"], kind=row["kind"]),
            relationship_identifier=row["relationship_identifier"],
        )
        for row in hop_rows
    ]
    return mid_uuid, hops
