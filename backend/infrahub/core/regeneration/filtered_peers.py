from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from infrahub.core.constants import DiffAction

from .predicates import parse_diff_action

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence

    from infrahub_sdk.diff import NodeDiff

    from infrahub.core.constants import RelationshipDirection
    from infrahub.core.validators.uniqueness.dependent_resolver import UniquenessDependentResolverInterface

    from .models import PeerFilters, RelationshipHop


class RelationshipPeerReader(Protocol):
    async def read(
        self,
        *,
        owner_kind: str,
        relationship_name: str,
        owner_ids: Sequence[str],
        peer_ids: Sequence[str],
        filters: Mapping[str, Any],
    ) -> set[tuple[str, str]]:
        """Return the (owner, peer) pairs the read returns with ``filters``, among ``peer_ids``."""
        ...


@dataclass(frozen=True)
class ChangedNodeIndex:
    """The nodes a diff changes on one branch, with their kind, action and changed fields."""

    kinds: Mapping[str, str]
    actions: Mapping[str, DiffAction]
    changed_fields: Mapping[str, frozenset[str]]

    @classmethod
    def from_diff(cls, *, diff_summary: Sequence[NodeDiff], query_branch: str) -> ChangedNodeIndex:
        """Index the nodes changed on ``query_branch``."""
        kinds: dict[str, str] = {}
        actions: dict[str, DiffAction] = {}
        changed_fields: dict[str, set[str]] = {}
        for node_diff in diff_summary:
            action = parse_diff_action(node_diff["action"])
            if node_diff["branch"] != query_branch or action == DiffAction.UNCHANGED:
                continue
            kinds[node_diff["id"]] = node_diff["kind"]
            actions[node_diff["id"]] = action
            changed_fields.setdefault(node_diff["id"], set()).update(
                element["name"]
                for element in node_diff["elements"]
                if parse_diff_action(element["action"]) != DiffAction.UNCHANGED
            )
        return cls(
            kinds=kinds,
            actions=actions,
            changed_fields={node_id: frozenset(fields) for node_id, fields in changed_fields.items()},
        )


@dataclass(frozen=True, slots=True)
class OwnerLookup:
    """A lookup of the owners of a kind that are related to one of the peers through a relationship."""

    owner_kind: str
    relationship_identifier: str
    relationship_direction: RelationshipDirection
    peer_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PeerRead:
    """A read of a relationship from some owners, limited to some peers; ``filters`` None means no filter."""

    owner_kind: str
    relationship_name: str
    owner_ids: tuple[str, ...]
    peer_ids: tuple[str, ...]
    filters: PeerFilters | None


class FilteredPeerReads:
    """Tell which owners read changed peers through a relationship, before or after the change.

    The diff gives the fields a peer changed, not their old values. A removed peer, or a peer that changed a
    filtered field, may have entered or left the filters, so the read is assumed to return it. Any other peer has
    the same filtered values before and after the change, so running the peer query on the current data tells
    whether the read returns it.
    """

    def __init__(
        self,
        *,
        changes: ChangedNodeIndex,
        dependents: UniquenessDependentResolverInterface,
        peers: RelationshipPeerReader,
    ) -> None:
        self._changes = changes
        self._dependents = dependents
        self._peers = peers
        self._owners: dict[OwnerLookup, set[str]] = {}
        self._pairs: dict[PeerRead, set[tuple[str, str]]] = {}

    async def owners(self, *, hop: RelationshipHop, peer_ids: Collection[str]) -> set[str]:
        """Return the owners of ``hop`` that read one of ``peer_ids``, before or after the change."""
        if hop.peer_filters is None:
            return await self._current_owners(hop=hop, peer_ids=peer_ids)
        crossed, unchanged = self._split(peer_ids=peer_ids, peer_filters=hop.peer_filters)
        owners = await self._current_owners(hop=hop, peer_ids=crossed)
        pairs = await self._read_from_current_owners(
            hop=hop,
            relationship_name=hop.peer_filters.relationship_name,
            peer_ids=unchanged,
            filters=hop.peer_filters,
        )
        return owners | {owner_id for owner_id, _ in pairs}

    def _split(
        self, *, peer_ids: Collection[str], peer_filters: PeerFilters
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Split the peers into those that may have entered or left the filters with the change, and the others."""
        crossed = {
            peer_id
            for peer_id in peer_ids
            if self._may_have_crossed(node_id=peer_id, fields=peer_filters.filtered_fields)
        }
        return tuple(sorted(crossed)), tuple(sorted(set(peer_ids) - crossed))

    def _may_have_crossed(self, *, node_id: str, fields: frozenset[str]) -> bool:
        """Whether a node that existed before the change was removed or changed one of ``fields``."""
        match self._changes.actions.get(node_id):
            case DiffAction.REMOVED:
                return True
            case DiffAction.ADDED:
                return False
            case _:
                return bool(self._changes.changed_fields.get(node_id, frozenset()) & fields)

    async def _current_owners(self, *, hop: RelationshipHop, peer_ids: Collection[str]) -> set[str]:
        """The owners currently related to one of ``peer_ids`` through the hop's relationship, cached."""
        if not peer_ids:
            return set()
        lookup = OwnerLookup(
            owner_kind=hop.node_kind,
            relationship_identifier=hop.relationship_identifier,
            relationship_direction=hop.relationship_direction,
            peer_ids=tuple(sorted(peer_ids)),
        )
        if lookup not in self._owners:
            self._owners[lookup] = await self._dependents.resolve(
                node_kind=lookup.owner_kind,
                relationship_identifier=lookup.relationship_identifier,
                relationship_direction=lookup.relationship_direction,
                peer_uuids=list(lookup.peer_ids),
            )
        return self._owners[lookup]

    async def _read_from_current_owners(
        self, *, hop: RelationshipHop, relationship_name: str, peer_ids: tuple[str, ...], filters: PeerFilters | None
    ) -> set[tuple[str, str]]:
        """The (owner, peer) pairs a read returns from the owners currently related to ``peer_ids``."""
        owners = await self._current_owners(hop=hop, peer_ids=peer_ids)
        return await self._read(
            PeerRead(
                owner_kind=hop.node_kind,
                relationship_name=relationship_name,
                owner_ids=tuple(sorted(owners)),
                peer_ids=peer_ids,
                filters=filters,
            )
        )

    async def _read(self, read: PeerRead) -> set[tuple[str, str]]:
        """The (owner, peer) pairs ``read`` returns, cached."""
        if not read.owner_ids or not read.peer_ids:
            return set()
        if read not in self._pairs:
            self._pairs[read] = await self._peers.read(
                owner_kind=read.owner_kind,
                relationship_name=read.relationship_name,
                owner_ids=list(read.owner_ids),
                peer_ids=list(read.peer_ids),
                filters=read.filters.as_query_filters() if read.filters else {},
            )
        return self._pairs[read]
