from __future__ import annotations

from typing import TYPE_CHECKING

from .constants import MAX_INHERITANCE_DEPTH, MAX_NODES_FOR_LINEAGE_WALK
from .models import NODE_HOLDER
from .resolution import resolve_node_ownership

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from .models import ResolvedOwnership, StoredNodeOwnership
    from .repository import OwnershipRepository


class OwnershipResolver:
    """Resolve the owners that apply to many nodes with their parents and their profiles."""

    def __init__(self, repository: OwnershipRepository) -> None:
        self.repository = repository

    async def resolve(self, node_ids: Iterable[str]) -> dict[str, ResolvedOwnership]:
        """Return the owners that apply to each node that is active at the read time of the repository.

        A node with more parents above it than the depth limit, and no state below the limit, gets no inherited owner.
        """
        requested = list(dict.fromkeys(node_ids))
        stored = await self._read_with_parents(node_ids=requested)
        return {
            node_id: resolve_node_ownership(lineage=_lineage(node_id=node_id, stored=stored), profiles=stored)
            for node_id in requested
            if node_id in stored
        }

    async def _read_with_parents(self, node_ids: list[str]) -> dict[str, StoredNodeOwnership]:
        """Read the nodes with the parents and the profiles that can give them owners.

        A few nodes take one read, with a walk to the parents in the query. More nodes take one read for each level
        of parents.
        """
        # The nodes of a page share their parents, and the walk of the query reads the parents again for each node.
        walks = len(node_ids) <= MAX_NODES_FOR_LINEAGE_WALK
        stored = await self.repository.read(node_ids=node_ids, lineage=walks)
        seen = set(node_ids) | set(stored)
        # A parent or a profile that the first read did not return is read here, one level for each read.
        for _ in range(MAX_INHERITANCE_DEPTH + 1):
            missing = _needed(node_ids=node_ids, stored=stored) - seen
            if not missing:
                break
            seen.update(missing)
            stored.update(await self.repository.read(node_ids=sorted(missing)))
        return stored


def _needed(node_ids: list[str], stored: Mapping[str, StoredNodeOwnership]) -> set[str]:
    """Return the parents and the profiles that the resolution of the nodes reads, from what is stored so far."""
    needed: set[str] = set()
    for node_id in node_ids:
        node = stored.get(node_id)
        for depth in range(MAX_INHERITANCE_DEPTH + 1):
            if node is None:
                break
            own = node.get(NODE_HOLDER)
            has_state = own.owner_ids is not None
            if not has_state or own.template_id is not None:
                needed.update(profile_id for profile_id, _ in node.profiles)
            if has_state or node.parent_id is None or depth == MAX_INHERITANCE_DEPTH:
                break
            needed.add(node.parent_id)
            node = stored.get(node.parent_id)
    return needed


def _lineage(node_id: str, stored: Mapping[str, StoredNodeOwnership]) -> list[StoredNodeOwnership]:
    lineage = [stored[node_id]]
    for _ in range(MAX_INHERITANCE_DEPTH):
        parent_id = lineage[-1].parent_id
        if parent_id is None or parent_id not in stored:
            break
        lineage.append(stored[parent_id])
    return lineage
