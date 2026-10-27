from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from infrahub.core.constants import RelationshipDirection


@dataclass(frozen=True, slots=True)
class DependentResolverCall:
    node_kind: str
    relationship_identifier: str
    relationship_direction: RelationshipDirection
    peer_uuids: tuple[str, ...]


@dataclass
class RecordingDependentResolver:
    """Resolver double that records each hop and answers from a fixed per-identifier mapping.

    Keeps the calls in order so a test asserts the exact hop sequence, and returns a superset of the
    truly-related nodes exactly as the real resolver does, so the chaining is exercised end to end
    without a database.
    """

    owners_by_identifier: dict[str, dict[str, set[str]]]
    calls: list[DependentResolverCall] = field(default_factory=list)

    async def resolve(
        self,
        node_kind: str,
        relationship_identifier: str,
        relationship_direction: RelationshipDirection,
        peer_uuids: list[str],
    ) -> set[str]:
        self.calls.append(
            DependentResolverCall(
                node_kind=node_kind,
                relationship_identifier=relationship_identifier,
                relationship_direction=relationship_direction,
                peer_uuids=tuple(peer_uuids),
            )
        )
        owners: set[str] = set()
        for peer in peer_uuids:
            owners |= self.owners_by_identifier.get(relationship_identifier, {}).get(peer, set())
        return owners


@dataclass(frozen=True, slots=True)
class PeerReaderCall:
    owner_kind: str
    relationship_name: str
    owner_ids: tuple[str, ...]
    peer_ids: tuple[str, ...]
    filters: tuple[tuple[str, Any], ...]


@dataclass
class RecordingPeerReader:
    """Peer query double: each peer is related to its listed owners, and a filtered read returns only ``passing`` peers.

    Records each read, with its filters sorted by key.
    """

    owners_by_peer: Mapping[str, set[str]]
    passing: set[str] = field(default_factory=set)
    calls: list[PeerReaderCall] = field(default_factory=list)

    async def read(
        self,
        *,
        owner_kind: str,
        relationship_name: str,
        owner_ids: Sequence[str],
        peer_ids: Sequence[str],
        filters: Mapping[str, Any],
    ) -> set[tuple[str, str]]:
        self.calls.append(
            PeerReaderCall(
                owner_kind=owner_kind,
                relationship_name=relationship_name,
                owner_ids=tuple(owner_ids),
                peer_ids=tuple(peer_ids),
                filters=tuple(sorted(filters.items())),
            )
        )
        return {
            (owner_id, peer_id)
            for peer_id in peer_ids
            for owner_id in self.owners_by_peer.get(peer_id, set())
            if owner_id in owner_ids and (not filters or peer_id in self.passing)
        }
