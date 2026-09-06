from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.core.constants import RelationshipDirection
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch


@dataclass(frozen=True, slots=True)
class DerivedPathHop:
    """One relationship crossed while following a derived path, from the kind that owns it.

    ``owner_kind`` owns the relationship; ``relationship_name`` is the name a diff reports its
    change under, ``relationship_identifier`` and ``relationship_direction`` map that change back.
    Hops are reported in walk order, reading kind first.
    """

    owner_kind: str
    relationship_name: str
    relationship_identifier: str
    relationship_direction: RelationshipDirection


@dataclass(frozen=True, slots=True)
class ScopedToReadingKind:
    """The value is built from the reading kind's own attribute: no peer, no widening."""


@dataclass(frozen=True, slots=True)
class ReachesPeer:
    """The path crosses one or more relationships to a peer attribute that backs the value.

    ``peer_kinds`` is a generic's implementations, else the single owning kind. ``hops`` are in
    walk order, so the caller reverses them to map a change on the peer back to the reading kind.
    """

    backing_field: str
    peer_kinds: tuple[str, ...]
    hops: tuple[DerivedPathHop, ...]


@dataclass(frozen=True, slots=True)
class Unresolvable:
    """The path could not be followed to a backing attribute; the caller must widen."""


type DerivedPathResolution = ScopedToReadingKind | ReachesPeer | Unresolvable


class DerivedPathResolver:
    """Follow a display_label / human_friendly_id path to the schema element that backs it.

    A path whose first segment is one of the reading kind's own attributes is scoped to that kind.
    A path that crosses relationships to a peer's attribute reaches that peer, carrying the hops it
    crossed. Anything else -- a segment that is neither a usable relationship nor a final attribute,
    or a relationship onto a kind the branch does not define -- is unresolvable.
    """

    def __init__(self, schema_branch: SchemaBranch) -> None:
        self.schema_branch = schema_branch

    def resolve(self, *, reading_schema: MainSchemaTypes, path: str) -> DerivedPathResolution:
        schema: MainSchemaTypes | None = reading_schema
        current_kind = reading_schema.kind
        hops: list[DerivedPathHop] = []
        for segment in path.split("__"):
            if schema is None:
                return Unresolvable()
            if segment in schema.attribute_names:
                if not hops:
                    return ScopedToReadingKind()
                return ReachesPeer(backing_field=segment, peer_kinds=schema.concrete_kinds, hops=tuple(hops))
            relationship = schema.get_relationship_or_none(name=segment)
            if relationship is None or not relationship.identifier:
                return Unresolvable()
            hops.append(
                DerivedPathHop(
                    owner_kind=current_kind,
                    relationship_name=relationship.name,
                    relationship_identifier=relationship.identifier,
                    relationship_direction=relationship.direction,
                )
            )
            current_kind = relationship.peer
            schema = self._node_schema(current_kind)
        return Unresolvable()

    def _node_schema(self, kind: str) -> MainSchemaTypes | None:
        return self.schema_branch.get(name=kind, duplicate=False) if self.schema_branch.has(name=kind) else None
