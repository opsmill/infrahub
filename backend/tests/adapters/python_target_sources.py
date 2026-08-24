"""In-memory sources for the Python transform target resolver."""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.query_group.subscribers import SubscriberRef

if TYPE_CHECKING:
    from collections.abc import Iterable

    from infrahub.computed_attribute.scoping import ChangedElementSet
    from infrahub.core.merge.python_target_resolution import PythonAttributeReadSet
    from infrahub.core.merge.recompute_coalescing import AffectedTarget, MergeChange


class StaticPythonReadSetSource:
    """Serves a fixed read-set index and records the branches it was asked for."""

    def __init__(self, read_sets: list[PythonAttributeReadSet]) -> None:
        self.configured_read_sets = read_sets
        self.calls: list[str] = []

    async def read_sets(self, *, branch: str) -> list[PythonAttributeReadSet]:
        self.calls.append(branch)
        return self.configured_read_sets


class RecordingSubscriberSource:
    """Serves subscribers from a fixed node-to-subscriber map and records every lookup."""

    def __init__(
        self,
        subscribers: dict[str, list[tuple[str, str]]],
        empties_lookup: set[str] | None = None,
    ) -> None:
        self.subscribers_by_node = subscribers
        self.empties_lookup = empties_lookup or set()
        self.calls: list[tuple[str, ...]] = []

    async def subscribers(self, *, node_ids: list[str], branch: str) -> list[SubscriberRef]:
        """Report the subscribers of the given nodes, one entry per matching group.

        ``empties_lookup`` reproduces a measured server behaviour: a deleted node id in the members
        filter returns nothing at all, so the live ids sharing that lookup lose their readers too.
        """
        self.calls.append(tuple(node_ids))
        if self.empties_lookup & set(node_ids):
            return []
        return [
            SubscriberRef(id=subscriber_id, kind=kind)
            for node_id in node_ids
            for subscriber_id, kind in self.subscribers_by_node.get(node_id, [])
        ]


class RecordingPythonTargetDeriver:
    """Serves a fixed target list and records the branch, node ids and schema scope of every call."""

    def __init__(self, targets: list[AffectedTarget]) -> None:
        self.targets = targets
        self.calls: list[tuple[str, tuple[str, ...], ChangedElementSet | None]] = []

    async def resolve(
        self,
        *,
        changes: Iterable[MergeChange],
        branch: str,
        schema_changed_elements: ChangedElementSet | None,
    ) -> list[AffectedTarget]:
        self.calls.append((branch, tuple(change.node_id for change in changes), schema_changed_elements))
        return self.targets


class FailingSubscriberSource:
    """Raises on every lookup, to prove the resolver widens instead of skipping."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    async def subscribers(self, *, node_ids: list[str], branch: str) -> list[SubscriberRef]:
        self.calls.append(tuple(node_ids))
        raise RuntimeError("subscriber lookup rejected")
