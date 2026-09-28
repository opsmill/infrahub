from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import DiffAction, RelationshipCardinality, RelationshipKind
from infrahub.log import get_logger

from .models import (
    RelationshipCardinalityManyChangelog,
    RelationshipCardinalityOneChangelog,
    RelationshipPeerChangelog,
)

if TYPE_CHECKING:
    from infrahub.core.manager import RelationshipSchema
    from infrahub.core.schema import MainSchemaTypes

    from .models import NodeChangelog

log = get_logger()


class ReciprocalRelationshipBuilder:
    """Builds the relationships a peer gets when its side of a changed relationship is mirrored.

    One peer-side relationship changelog is built per mirrored relationship, holding the mutated
    node as the peer that was added or removed.
    """

    def build(
        self,
        peer_schema: MainSchemaTypes,
        rel_schema: RelationshipSchema,
        primary_changelog: NodeChangelog,
        peer_status: DiffAction,
    ) -> dict[str, RelationshipCardinalityOneChangelog | RelationshipCardinalityManyChangelog]:
        """Return the peer-side relationship changelogs, keyed by relationship name."""
        relationships: dict[str, RelationshipCardinalityOneChangelog | RelationshipCardinalityManyChangelog] = {}
        for peer_relation in self.peer_relationships(peer_schema=peer_schema, rel_schema=rel_schema):
            if peer_relation.cardinality == RelationshipCardinality.ONE:
                relationships[peer_relation.name] = self._cardinality_one(
                    name=peer_relation.name,
                    primary_changelog=primary_changelog,
                    peer_status=peer_status,
                    rel_kind=peer_relation.kind,
                )
            elif peer_relation.cardinality == RelationshipCardinality.MANY:
                relationships[peer_relation.name] = self._cardinality_many(
                    name=peer_relation.name, primary_changelog=primary_changelog, peer_status=peer_status
                )
        return relationships

    def peer_relationships(
        self, peer_schema: MainSchemaTypes, rel_schema: RelationshipSchema
    ) -> list[RelationshipSchema]:
        """Return the peer's side of ``rel_schema``.

        A hierarchy declares ``parent`` and ``children`` under one identifier, so only the mirrored
        direction tells them apart. When no candidate mirrors the direction the whole set is returned
        and logged: the answer is a guess, but dropping it would hide a change that did happen.
        """
        candidates = peer_schema.get_relationships_by_identifier(id=rel_schema.get_identifier())
        mirrored = [candidate for candidate in candidates if candidate.mirrors(rel_schema)]
        if mirrored:
            return mirrored

        if candidates:
            log.warning(
                "No peer relationship mirrors the direction, reporting every candidate",
                peer_kind=peer_schema.kind,
                identifier=rel_schema.get_identifier(),
                direction=rel_schema.direction.value,
                candidates=[candidate.name for candidate in candidates],
            )

        return candidates

    def _cardinality_one(
        self, name: str, primary_changelog: NodeChangelog, peer_status: DiffAction, rel_kind: RelationshipKind
    ) -> RelationshipCardinalityOneChangelog:
        """Build the one-cardinality reciprocal, placing the primary as the current or removed peer.

        The peer holds the mutated node through this relationship, so when the relationship is a
        parent one the mutated node is the peer's parent and is recorded as such.
        """
        if peer_status == DiffAction.REMOVED:
            # The primary is the removed (previous) peer, so no current-peer label.
            changelog = RelationshipCardinalityOneChangelog(
                name=name,
                peer_id_previous=primary_changelog.node_id,
                peer_kind_previous=primary_changelog.node_kind,
            )
        else:
            changelog = RelationshipCardinalityOneChangelog(
                name=name,
                peer_id=primary_changelog.node_id,
                peer_kind=primary_changelog.node_kind,
                peer_display_label=primary_changelog.display_label,
                peer_hfid=primary_changelog.hfid,
            )
        changelog.set_parent_from_relationship(rel_kind=rel_kind)
        return changelog

    def _cardinality_many(
        self, name: str, primary_changelog: NodeChangelog, peer_status: DiffAction
    ) -> RelationshipCardinalityManyChangelog:
        """Build the many-cardinality reciprocal, holding the primary as its single changed peer."""
        return RelationshipCardinalityManyChangelog(
            name=name,
            peers=[
                RelationshipPeerChangelog(
                    peer_id=primary_changelog.node_id,
                    peer_kind=primary_changelog.node_kind,
                    peer_display_label=primary_changelog.display_label,
                    peer_hfid=primary_changelog.hfid,
                    peer_status=peer_status,
                )
            ],
        )
