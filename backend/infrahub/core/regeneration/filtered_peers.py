from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from infrahub.core.constants import DiffAction

from .models import ExcludedChange
from .predicates import parse_diff_action

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence

    from infrahub_sdk.diff import NodeDiff

    from infrahub.core.constants import RelationshipDirection
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.validators.uniqueness.dependent_resolver import UniquenessDependentResolverInterface

    from .models import PeerFilters, RelationshipHop, RelationshipRead


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

    async def reads_any(self, *, read: RelationshipRead, peer_ids: Collection[str]) -> bool:
        """Whether ``read`` can return one of ``peer_ids``, before or after the change.

        A peer that no owner is currently related to cannot be passed to the peer query, so the read is assumed to
        return it.
        """
        if read.peer_filters is None:
            return bool(peer_ids)
        crossed, unchanged = self._split(peer_ids=peer_ids, peer_filters=read.peer_filters)
        if crossed:
            return True
        passing = await self._read_from_current_owners(
            hop=read.hop, relationship_name=read.relationship_name, peer_ids=unchanged, filters=read.peer_filters
        )
        if passing:
            return True
        held = await self._read_from_current_owners(
            hop=read.hop, relationship_name=read.relationship_name, peer_ids=unchanged, filters=None
        )
        # A peer related to no owner, such as one just removed from the relationship, cannot be tested against the
        # filters, so the read is assumed to return it.
        return bool(set(unchanged) - {peer_id for _, peer_id in held})

    def _split(
        self, *, peer_ids: Collection[str], peer_filters: PeerFilters
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Split the peers into those that may have entered or left the filters with the change, and the others."""
        fields = peer_filters.filtered_fields
        crossed = {peer_id for peer_id in peer_ids if self._may_have_crossed(node_id=peer_id, fields=fields)}
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


class FilteredRelationshipExclusions:
    """Find the owners' relationship changes that no read of that relationship returns a peer for.

    The diff says the relationship changed but not which peer, so the peers are the nodes of the same diff whose
    side of the relationship changed. A change is excluded only when every read of the relationship is filtered and
    none can return one of those peers.
    """

    def __init__(
        self,
        *,
        reads: Sequence[RelationshipRead],
        schema_branch: SchemaBranch,
        changes: ChangedNodeIndex,
        peer_reads: FilteredPeerReads,
    ) -> None:
        self._reads_by_field: defaultdict[tuple[str, str], list[RelationshipRead]] = defaultdict(list)
        for read in reads:
            self._reads_by_field[read.owner_kind, read.relationship_name].append(read)
        self._schema_branch = schema_branch
        self._changes = changes
        self._peer_reads = peer_reads
        self._verdicts: dict[tuple[str, str], bool] = {}
        self._side_names: dict[tuple[str, str], frozenset[str]] = {}

    @property
    def has_filtered_reads(self) -> bool:
        """Whether a read has filters, the only case where a change can be excluded."""
        return any(read.peer_filters is not None for reads in self._reads_by_field.values() for read in reads)

    async def excluded_changes(self, *, diff_summary: list[NodeDiff]) -> frozenset[ExcludedChange]:
        """Return the relationship changes of updated owners whose peers no read returns."""
        excluded: set[ExcludedChange] = set()
        for node_diff in diff_summary:
            if self._changes.actions.get(node_diff["id"]) != DiffAction.UPDATED:
                continue
            for element in node_diff["elements"]:
                if await self._filters_out_every_peer(owner_kind=node_diff["kind"], field_name=element["name"]):
                    excluded.add(ExcludedChange(node_id=node_diff["id"], field_name=element["name"]))
        return frozenset(excluded)

    async def _filters_out_every_peer(self, *, owner_kind: str, field_name: str) -> bool:
        """Whether no read of the owner's relationship returns one of its changed peers, cached per relationship."""
        key = (owner_kind, field_name)
        if key not in self._verdicts:
            self._verdicts[key] = await self._decide(reads=self._reads_by_field.get(key, []))
        return self._verdicts[key]

    async def _decide(self, *, reads: list[RelationshipRead]) -> bool:
        """Whether the owner's relationship change can be excluded.

        It can be excluded only when all three hold:
        1. every read of the relationship has filters;
        2. the diff holds the peers whose side of the relationship changed;
        3. no read can return one of those peers, before or after the change.
        """
        if not reads or any(read.peer_filters is None for read in reads):
            return False
        for read in reads:
            peers = self._changed_peers(read)
            if not peers or await self._peer_reads.reads_any(read=read, peer_ids=peers):
                return False
        return True

    def _changed_peers(self, read: RelationshipRead) -> list[str]:
        """The nodes of the read's peer kinds whose side of the relationship changed in the diff."""
        return [
            node_id
            for node_id, kind in self._changes.kinds.items()
            if kind in read.peer_kinds
            and self._changes.changed_fields[node_id]
            & self._peer_side_names(kind=kind, identifier=read.relationship_identifier)
        ]

    def _peer_side_names(self, *, kind: str, identifier: str) -> frozenset[str]:
        """The names of the relationship ``identifier`` on ``kind``, cached."""
        key = (kind, identifier)
        if key not in self._side_names:
            self._side_names[key] = (
                frozenset(
                    relationship.name
                    for relationship in self._schema_branch.get(
                        name=kind, duplicate=False
                    ).get_relationships_by_identifier(id=identifier)
                )
                if self._schema_branch.has(name=kind)
                else frozenset()
            )
        return self._side_names[key]
