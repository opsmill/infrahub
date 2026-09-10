from __future__ import annotations

from typing import TYPE_CHECKING

from opentelemetry import trace

from infrahub.core.changelog.enrichment import PLACEHOLDER_LABELS, NodeLabelLoader, NodeLabels
from infrahub.core.constants import DiffAction, RelationshipCardinality
from infrahub.log import get_logger

from .models import (
    NodeChangelog,
    RelationshipCardinalityManyChangelog,
    RelationshipCardinalityOneChangelog,
    RelationshipPeerChangelog,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.manager import RelationshipSchema
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

log = get_logger()


def peer_relationships(peer_schema: MainSchemaTypes, rel_schema: RelationshipSchema) -> list[RelationshipSchema]:
    """Return the peer's side of ``rel_schema``.

    A hierarchy declares ``parent`` and ``children`` under one identifier, so only the mirrored
    direction tells them apart. When no candidate mirrors the direction the whole set is returned
    and logged: the answer is a guess, but dropping it would hide a change that did happen.
    """
    candidates = peer_schema.get_relationships_by_identifier(id=rel_schema.get_identifier())
    mirrored = [candidate for candidate in candidates if candidate.direction == rel_schema.direction.neighbor_direction]
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


def _labels_for(peer_id: str, labels: dict[str, NodeLabels]) -> NodeLabels:
    """Return a peer's labels, or a placeholder when it could not be resolved (e.g. deleted)."""
    return labels.get(peer_id, PLACEHOLDER_LABELS)


class RelationshipChangelogGetter:
    """Builds the secondary node changelogs a relationship mutation implies.

    A relationship change on the mutated node also changes the reciprocal relationship on each
    peer, so one secondary changelog is emitted per affected peer. The mutated node's own
    relationships and each secondary are filled with the peer's display label and HFID, resolved
    for every referenced peer in a single batched load.
    """

    def __init__(self, db: InfrahubDatabase, branch: Branch, label_loader: NodeLabelLoader) -> None:
        self._db = db
        self._branch = branch
        self._label_loader = label_loader

    async def get_changelogs(self, primary_changelog: NodeChangelog) -> list[NodeChangelog]:
        """Enrich the mutated node's relationships in place and return the secondaries they imply.

        Args:
            primary_changelog: Changelog of the node that was directly mutated. Its relationships
                are filled in place with each peer's display label and HFID.

        Returns:
            The secondary changelogs, one per affected peer.

        """
        referenced_peer_ids = self._referenced_peer_ids(changelog=primary_changelog)
        labels = await self._label_loader.load_labels(referenced_peer_ids)
        self._enrich_relationship_peers(changelog=primary_changelog, labels=labels)

        with trace.get_tracer(__name__).start_as_current_span("changelog.build_secondaries") as span:
            span.set_attribute("changelog.referenced_peer_count", len(referenced_peer_ids))
            span.set_attribute("changelog.resolved_peer_count", len(labels))
            secondaries = self._build_secondaries(primary_changelog=primary_changelog, labels=labels)
            span.set_attribute("changelog.secondary_count", len(secondaries))
        return secondaries

    def _build_secondaries(
        self, primary_changelog: NodeChangelog, labels: dict[str, NodeLabels]
    ) -> list[NodeChangelog]:
        """Build one secondary changelog per peer whose reciprocal relationship changed."""
        schema_branch = self._db.schema.get_schema_branch(name=self._branch.name)
        node_schema = schema_branch.get(name=primary_changelog.node_kind, duplicate=False)

        secondaries: list[NodeChangelog] = []
        for relationship in primary_changelog.relationships.values():
            if isinstance(relationship, RelationshipCardinalityOneChangelog):
                secondaries.extend(
                    self._parse_cardinality_one_relationship(
                        relationship=relationship,
                        node_schema=node_schema,
                        primary_changelog=primary_changelog,
                        schema_branch=schema_branch,
                        labels=labels,
                    )
                )
            elif isinstance(relationship, RelationshipCardinalityManyChangelog):
                secondaries.extend(
                    self._parse_cardinality_many_relationship(
                        relationship=relationship,
                        node_schema=node_schema,
                        primary_changelog=primary_changelog,
                        schema_branch=schema_branch,
                        labels=labels,
                    )
                )
        return self._merge_secondaries_by_node(secondaries)

    @staticmethod
    def _merge_secondaries_by_node(secondaries: list[NodeChangelog]) -> list[NodeChangelog]:
        """Collapse the secondaries so each affected peer yields a single changelog.

        A mutation can change several relationships to the same peer, and each produces its own
        secondary for that peer; emitting them separately would deliver duplicate events. Fold the
        later ones into the first changelog seen for the peer, keeping every distinct reciprocal
        relationship it carries.
        """
        merged: dict[str, NodeChangelog] = {}
        for secondary in secondaries:
            existing = merged.get(secondary.node_id)
            if existing is None:
                merged[secondary.node_id] = secondary
                continue
            for name, relationship in secondary.relationships.items():
                existing.relationships.setdefault(name, relationship)
        return list(merged.values())

    @staticmethod
    def _referenced_peer_ids(changelog: NodeChangelog) -> list[str]:
        """Collect the IDs of every peer referenced by this changelog's relationships."""
        ids: list[str] = []
        for relationship in changelog.relationships.values():
            if isinstance(relationship, RelationshipCardinalityOneChangelog):
                ids += [peer_id for peer_id in (relationship.peer_id, relationship.peer_id_previous) if peer_id]
            elif isinstance(relationship, RelationshipCardinalityManyChangelog):
                ids += [peer.peer_id for peer in relationship.peers if peer.peer_id]
        return ids

    @staticmethod
    def _enrich_relationship_peers(changelog: NodeChangelog, labels: dict[str, NodeLabels]) -> None:
        """Fill each current relationship peer of the mutated node with its display label and HFID."""
        for relationship in changelog.relationships.values():
            if isinstance(relationship, RelationshipCardinalityOneChangelog):
                if relationship.peer_id:
                    peer_labels = _labels_for(peer_id=relationship.peer_id, labels=labels)
                    relationship.peer_display_label = peer_labels.display_label
                    relationship.peer_hfid = peer_labels.hfid
            elif isinstance(relationship, RelationshipCardinalityManyChangelog):
                for peer in relationship.peers:
                    peer_labels = _labels_for(peer_id=peer.peer_id, labels=labels)
                    peer.peer_display_label = peer_labels.display_label
                    peer.peer_hfid = peer_labels.hfid

    def _parse_cardinality_one_relationship(
        self,
        relationship: RelationshipCardinalityOneChangelog,
        node_schema: MainSchemaTypes,
        primary_changelog: NodeChangelog,
        schema_branch: SchemaBranch,
        labels: dict[str, NodeLabels],
    ) -> list[NodeChangelog]:
        secondaries: list[NodeChangelog] = []
        rel_schema = node_schema.get_relationship(name=relationship.name)

        if relationship.peer_status == DiffAction.ADDED:
            peer_schema = schema_branch.get(name=str(relationship.peer_kind), duplicate=False)
            secondaries.extend(
                self._process_reciprocal_peers(
                    peer_id=str(relationship.peer_id),
                    peer_kind=str(relationship.peer_kind),
                    peer_schema=peer_schema,
                    rel_schema=rel_schema,
                    primary_changelog=primary_changelog,
                    labels=labels,
                    peer_status=DiffAction.ADDED,
                )
            )
        elif relationship.peer_status == DiffAction.UPDATED:
            peer_schema = schema_branch.get(name=str(relationship.peer_kind), duplicate=False)
            secondaries.extend(
                self._process_reciprocal_peers(
                    peer_id=str(relationship.peer_id),
                    peer_kind=str(relationship.peer_kind),
                    peer_schema=peer_schema,
                    rel_schema=rel_schema,
                    primary_changelog=primary_changelog,
                    labels=labels,
                    peer_status=DiffAction.ADDED,
                )
            )
            previous_peer_schema = schema_branch.get(name=str(relationship.peer_kind_previous), duplicate=False)
            secondaries.extend(
                self._process_reciprocal_peers(
                    peer_schema=previous_peer_schema,
                    peer_id=str(relationship.peer_id_previous),
                    peer_kind=str(relationship.peer_kind_previous),
                    rel_schema=rel_schema,
                    primary_changelog=primary_changelog,
                    labels=labels,
                    peer_status=DiffAction.REMOVED,
                )
            )
        elif relationship.peer_status == DiffAction.REMOVED:
            peer_schema = schema_branch.get(name=str(relationship.peer_kind_previous), duplicate=False)
            secondaries.extend(
                self._process_reciprocal_peers(
                    peer_id=str(relationship.peer_id_previous),
                    peer_kind=str(relationship.peer_kind_previous),
                    peer_schema=peer_schema,
                    rel_schema=rel_schema,
                    primary_changelog=primary_changelog,
                    labels=labels,
                    peer_status=DiffAction.REMOVED,
                )
            )
        return secondaries

    def _parse_cardinality_many_relationship(
        self,
        relationship: RelationshipCardinalityManyChangelog,
        node_schema: MainSchemaTypes,
        primary_changelog: NodeChangelog,
        schema_branch: SchemaBranch,
        labels: dict[str, NodeLabels],
    ) -> list[NodeChangelog]:
        secondaries: list[NodeChangelog] = []
        rel_schema = node_schema.get_relationship(name=relationship.name)

        for peer in relationship.peers:
            if peer.peer_status == DiffAction.ADDED:
                peer_schema = schema_branch.get(name=peer.peer_kind, duplicate=False)
                secondaries.extend(
                    self._process_reciprocal_peers(
                        peer_id=peer.peer_id,
                        peer_kind=peer.peer_kind,
                        peer_schema=peer_schema,
                        rel_schema=rel_schema,
                        primary_changelog=primary_changelog,
                        labels=labels,
                        peer_status=DiffAction.ADDED,
                    )
                )
            elif peer.peer_status == DiffAction.REMOVED:
                peer_schema = schema_branch.get(name=peer.peer_kind, duplicate=False)
                secondaries.extend(
                    self._process_reciprocal_peers(
                        peer_id=peer.peer_id,
                        peer_kind=peer.peer_kind,
                        peer_schema=peer_schema,
                        rel_schema=rel_schema,
                        primary_changelog=primary_changelog,
                        labels=labels,
                        peer_status=DiffAction.REMOVED,
                    )
                )
        return secondaries

    def _process_reciprocal_peers(
        self,
        peer_id: str,
        peer_kind: str,
        peer_schema: MainSchemaTypes,
        rel_schema: RelationshipSchema,
        primary_changelog: NodeChangelog,
        labels: dict[str, NodeLabels],
        peer_status: DiffAction,
    ) -> list[NodeChangelog]:
        """Build the secondary changelog a peer gets when its relationship to the primary changes."""
        peer_labels = _labels_for(peer_id=peer_id, labels=labels)
        node_changelog = NodeChangelog(
            node_id=peer_id,
            node_kind=peer_kind,
            display_label=peer_labels.display_label,
            hfid=peer_labels.hfid,
        )
        for peer_relation in peer_relationships(peer_schema=peer_schema, rel_schema=rel_schema):
            if peer_relation.cardinality == RelationshipCardinality.ONE:
                node_changelog.relationships[peer_relation.name] = self._reciprocal_one_relationship(
                    name=peer_relation.name, primary_changelog=primary_changelog, peer_status=peer_status
                )
            elif peer_relation.cardinality == RelationshipCardinality.MANY:
                node_changelog.relationships[peer_relation.name] = RelationshipCardinalityManyChangelog(
                    name=peer_relation.name,
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

        return [node_changelog] if node_changelog.relationships else []

    @staticmethod
    def _reciprocal_one_relationship(
        name: str, primary_changelog: NodeChangelog, peer_status: DiffAction
    ) -> RelationshipCardinalityOneChangelog:
        """Build the one-cardinality reciprocal, placing the primary as the current or removed peer."""
        if peer_status == DiffAction.REMOVED:
            # The primary is the removed (previous) peer, so no current-peer label.
            return RelationshipCardinalityOneChangelog(
                name=name,
                peer_id_previous=primary_changelog.node_id,
                peer_kind_previous=primary_changelog.node_kind,
            )
        return RelationshipCardinalityOneChangelog(
            name=name,
            peer_id=primary_changelog.node_id,
            peer_kind=primary_changelog.node_kind,
            peer_display_label=primary_changelog.display_label,
            peer_hfid=primary_changelog.hfid,
        )
