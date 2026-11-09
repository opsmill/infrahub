from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.core.diff.model.path import NodeDiffFieldSummary


class NodeDiffIndex:
    """Which fields and nodes changed, per kind, in a data diff.

    The node uuids are kept per changed field, not merged per kind, so a consumer can ask which
    nodes changed a specific field rather than every node of the kind.

    `initialize` must be called for a given diff before any query method is used.
    """

    def __init__(self) -> None:
        self._initialized: bool = False
        self._kinds: set[str] = set()
        self._attribute_uuids_by_kind_field: dict[tuple[str, str], set[str]] = {}
        self._relationship_uuids_by_kind_field: dict[tuple[str, str], set[str]] = {}

    def initialize(self, node_diffs: list[NodeDiffFieldSummary]) -> None:
        self._kinds = set()
        self._attribute_uuids_by_kind_field = {}
        self._relationship_uuids_by_kind_field = {}
        for node_diff in node_diffs:
            self._kinds.add(node_diff.kind)
            for name, uuids in node_diff.attribute_node_uuids.items():
                self._attribute_uuids_by_kind_field.setdefault((node_diff.kind, name), set()).update(uuids)
            for name, uuids in node_diff.relationship_node_uuids.items():
                self._relationship_uuids_by_kind_field.setdefault((node_diff.kind, name), set()).update(uuids)
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
        return (kind, name) in self._attribute_uuids_by_kind_field

    def has_relationship_diff(self, kind: str, name: str) -> bool:
        self._ensure_initialized()
        return (kind, name) in self._relationship_uuids_by_kind_field

    def get_uuids_for_attribute(self, kind: str, name: str) -> set[str]:
        """UUIDs of the nodes of `kind` whose attribute `name` changed in the diff."""
        self._ensure_initialized()
        return set(self._attribute_uuids_by_kind_field.get((kind, name), set()))

    def get_uuids_for_relationship(self, kind: str, name: str) -> set[str]:
        """UUIDs of the nodes of `kind` whose relationship `name` changed in the diff."""
        self._ensure_initialized()
        return set(self._relationship_uuids_by_kind_field.get((kind, name), set()))
