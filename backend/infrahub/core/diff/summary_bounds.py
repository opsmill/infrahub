from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core.constants import DiffAction

if TYPE_CHECKING:
    from infrahub_sdk.diff import NodeDiff

    from infrahub.core.diff.model.path import EnrichedDiffRoot
    from infrahub.core.diff.summary_serializer import DiffSummarySerializer


@dataclass(frozen=True)
class SerializedDiffSummary:
    """A merge diff summary that fits the cache ceilings, paired with its dumped payload."""

    diff_summary: list[NodeDiff]
    payload: str
    node_count: int
    byte_size: int


@dataclass(frozen=True)
class OversizedDiffSummary:
    """A merge diff summary that exceeds a cache ceiling and must not be cached.

    ``byte_size`` is None when the node-count ceiling rejected the diff before it was serialized.
    """

    node_count: int
    byte_size: int | None


type BoundedDiffSummary = SerializedDiffSummary | OversizedDiffSummary


class BoundedDiffSummaryBuilder:
    """Serialize a merge diff only while it stays within the cache-size ceilings.

    The changed-node count is checked before serialization, so an oversized merge is rejected
    without paying the JSON encoding; the serialized size is then checked against the byte ceiling
    that keeps the payload under the cache backend's per-value limit.
    """

    def __init__(self, serializer: DiffSummarySerializer, max_nodes: int, max_bytes: int) -> None:
        self._serializer = serializer
        self._max_nodes = max_nodes
        self._max_bytes = max_bytes

    def build(self, *, root: EnrichedDiffRoot, target_branch_name: str) -> BoundedDiffSummary:
        node_count = sum(1 for node in root.nodes if node.action != DiffAction.UNCHANGED)
        if node_count > self._max_nodes:
            return OversizedDiffSummary(node_count=node_count, byte_size=None)
        diff_summary = self._serializer.serialize(root=root, target_branch_name=target_branch_name)
        payload = self._serializer.dump(diff_summary)
        byte_size = len(payload.encode())
        if byte_size > self._max_bytes:
            return OversizedDiffSummary(node_count=node_count, byte_size=byte_size)
        return SerializedDiffSummary(
            diff_summary=diff_summary, payload=payload, node_count=node_count, byte_size=byte_size
        )
