from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.core.diff.model.path import NodeDiffFieldSummary


class NodeDiffIndex:
    """Which fields and nodes changed, per kind, in a data diff.

    `initialize` must be called for a given diff before any query method is used.
    """

    def __init__(self) -> None:
        self._initialized: bool = False
        self._kinds: set[str] = set()
        self._attribute_names_by_kind: dict[str, set[str]] = {}
        self._relationship_names_by_kind: dict[str, set[str]] = {}
        self._node_uuids_by_kind: dict[str, set[str]] = {}

    def initialize(self, node_diffs: list[NodeDiffFieldSummary]) -> None:
        self._kinds = set()
        self._attribute_names_by_kind = {}
        self._relationship_names_by_kind = {}
        self._node_uuids_by_kind = {}
        for node_diff in node_diffs:
            self._kinds.add(node_diff.kind)
            self._attribute_names_by_kind.setdefault(node_diff.kind, set()).update(node_diff.attribute_names)
            self._relationship_names_by_kind.setdefault(node_diff.kind, set()).update(node_diff.relationship_names)
            self._node_uuids_by_kind.setdefault(node_diff.kind, set()).update(node_diff.node_uuids)
        self._initialized = True

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError("NodeDiffIndex must be initialized with initialize() before its query methods are used")

    @property
    def kinds(self) -> set[str]:
        self._ensure_initialized()
        return self._kinds

    def has_attribute_diff(self, kind: str, name: str) -> bool:
        self._ensure_initialized()
        return name in self._attribute_names_by_kind.get(kind, set())

    def has_relationship_diff(self, kind: str, name: str) -> bool:
        self._ensure_initialized()
        return name in self._relationship_names_by_kind.get(kind, set())

    def uuids_for_kinds(self, kinds: set[str]) -> set[str]:
        self._ensure_initialized()
        uuids: set[str] = set()
        for kind in kinds:
            uuids |= self._node_uuids_by_kind.get(kind, set())
        return uuids
