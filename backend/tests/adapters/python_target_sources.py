"""In-memory sources for the Python transform target resolver."""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.query_group.subscribers import SubscriberRef

if TYPE_CHECKING:
    from infrahub.core.merge.python_target_resolution import PythonAttributeReadSet


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


class FailingSubscriberSource:
    """Raises on every lookup, to prove the resolver widens instead of skipping."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    async def subscribers(self, *, node_ids: list[str], branch: str) -> list[SubscriberRef]:
        self.calls.append(tuple(node_ids))
        raise RuntimeError("subscriber lookup rejected")
