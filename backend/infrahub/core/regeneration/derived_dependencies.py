from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, assert_never

from infrahub.core.schema.derived_path import (
    DerivedPathResolver,
    ReachesPeer,
    ScopedToReadingKind,
    Unresolvable,
)
from infrahub.core.schema.schema_branch_computed.python_transform import IMPRECISE_READ_FIELDS

from .models import ReachedPath, RelationshipHop

if TYPE_CHECKING:
    from collections.abc import Mapping

    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.derived_path import DerivedPathHop
    from infrahub.core.schema.schema_branch import SchemaBranch


@dataclass(frozen=True, slots=True)
class PeerDependency:
    """A related kind whose change moves a display_label / human_friendly_id, and how to map it back.

    ``kind`` is the concrete kind a change is reported against, ``field_name`` its attribute that
    feeds the derived value, ``path`` the relationship chain from that kind back to ``reading_kind``,
    and ``reading_kind`` the kind that reads the derived value -- the chain stops there, so a caller
    whose ``reading_kind`` is itself relationship-reached must extend it to reach the root member.
    """

    kind: str
    field_name: str
    path: ReachedPath
    reading_kind: str


@dataclass(frozen=True, slots=True)
class DerivedFieldDependencies:
    """The peers a query's derived reads depend on, plus whether any read could not be resolved.

    ``widen`` is set when a derived read cannot be mapped to a peer chain -- no declared path, an
    absent kind, a segment that is neither a relationship nor a final attribute -- so the caller has
    to fall back to processing every target rather than risk leaving a reader stale.
    """

    peers: tuple[PeerDependency, ...]
    widen: bool


class DerivedFieldDependencyResolver:
    """Resolve the peer kinds a query's display_label / human_friendly_id reads depend on.

    A derived value can be composed from a related node's field, so a change to that peer moves the
    value while the peer's kind is never named in the query's read surface. This walks each derived
    field's declared paths, following relationships to the kind that owns the backing attribute, and
    reports the relationship chain that maps a changed peer back to the reading member. A read built
    only from the reading kind's own attributes yields no peer -- the imprecise-read rule already
    covers a same-kind change -- and anything that cannot be resolved sets ``widen``.
    """

    def __init__(self, schema_branch: SchemaBranch) -> None:
        self.schema_branch = schema_branch
        self.path_resolver = DerivedPathResolver(schema_branch=schema_branch)

    def _node_schema(self, kind: str) -> MainSchemaTypes | None:
        """The schema for ``kind``, or None when the branch does not define it."""
        return self.schema_branch.get(name=kind, duplicate=False) if self.schema_branch.has(name=kind) else None

    def resolve(self, readable_fields_by_kind: Mapping[str, set[str]]) -> DerivedFieldDependencies:
        """Resolve every display_label / human_friendly_id read in the read surface to its peers.

        Peers union across all reads; ``widen`` is set as soon as one read cannot be resolved.
        """
        peers: list[PeerDependency] = []
        widen = False
        for kind in sorted(readable_fields_by_kind):
            for field_name in sorted(readable_fields_by_kind[kind] & IMPRECISE_READ_FIELDS):
                field_peers, field_widen = self._resolve_field(reading_kind=kind, field_name=field_name)
                peers.extend(field_peers)
                widen |= field_widen
        return DerivedFieldDependencies(peers=tuple(peers), widen=widen)

    def _resolve_field(self, *, reading_kind: str, field_name: str) -> tuple[list[PeerDependency], bool]:
        """The peers one derived field on ``reading_kind`` depends on, and whether it must widen.

        A field with no declared path, or on a kind absent from the schema, cannot be resolved: it
        yields no peer and widens. Otherwise every declared path is followed and their peers unioned.
        """
        reading_schema = self._node_schema(reading_kind)
        if reading_schema is None:
            return [], True
        paths = reading_schema.get_derived_field_paths(field_name)
        if paths is None:
            return [], True

        peers: list[PeerDependency] = []
        widen = False
        for path in paths:
            path_peers, path_widen = self._resolve_path(reading_schema=reading_schema, path=path)
            peers.extend(path_peers)
            widen = widen or path_widen
        return peers, widen

    def _resolve_path(self, *, reading_schema: MainSchemaTypes, path: str) -> tuple[list[PeerDependency], bool]:
        """Map one derived-value path to every peer a change on which moves it.

        A path scoped to the reading kind's own attribute yields no peer and does not widen -- a
        same-kind change is already relevant through the imprecise-read rule. A path reaching a peer
        yields the backing attribute on the final peer, plus each intermediate relationship the chain
        crosses: re-pointing a relationship past the reading kind moves the value just as a change to
        the backing attribute does. The reading kind's own first hop is covered by its imprecise read,
        so intermediates start at the second hop. A path that cannot be followed to a backing
        attribute widens.
        """
        resolution = self.path_resolver.resolve(reading_schema=reading_schema, path=path)
        match resolution:
            case ScopedToReadingKind():
                return [], False
            case Unresolvable():
                return [], True
            case ReachesPeer(backing_field=field_name, peer_kinds=peer_kinds, hops=hops):
                reading_kind = reading_schema.kind
                peers = [
                    PeerDependency(
                        kind=kind, field_name=field_name, path=self._reached_path(hops), reading_kind=reading_kind
                    )
                    for kind in peer_kinds
                ]
                for index in range(1, len(hops)):
                    hop = hops[index]
                    reached = self._reached_path(hops[:index])
                    peers.extend(
                        PeerDependency(
                            kind=kind, field_name=hop.relationship_name, path=reached, reading_kind=reading_kind
                        )
                        for kind in self._concrete_kinds(hop.owner_kind)
                    )
                return peers, False
            case _ as unreachable:
                assert_never(unreachable)

    def _reached_path(self, hops: tuple[DerivedPathHop, ...]) -> ReachedPath:
        """The chain that maps a change on the kind ``hops`` end at back to the reading member.

        Reversed so the hop nearest that kind resolves first.
        """
        return ReachedPath(
            hops=tuple(
                reversed(
                    [
                        RelationshipHop(
                            node_kind=hop.owner_kind,
                            relationship_identifier=hop.relationship_identifier,
                            relationship_direction=hop.relationship_direction,
                        )
                        for hop in hops
                    ]
                )
            )
        )

    def _concrete_kinds(self, kind: str) -> tuple[str, ...]:
        """The concrete kinds a change on ``kind`` is reported against: a generic's implementations."""
        schema = self._node_schema(kind)
        return schema.concrete_kinds if schema is not None else (kind,)
