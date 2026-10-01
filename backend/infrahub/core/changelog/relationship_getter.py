from __future__ import annotations

from typing import TYPE_CHECKING

from opentelemetry import trace

from infrahub.core.constants import DiffAction

from .models import (
    NodeChangelog,
    RelationshipCardinalityManyChangelog,
    RelationshipCardinalityOneChangelog,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.manager import RelationshipSchema
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

    from .peer_labels import PeerLabelResolver, ResolvedPeerLabels
    from .reciprocal import ReciprocalRelationshipBuilder
    from .secondary_merger import SecondaryChangelogMerger


class RelationshipChangelogGetter:
    """Builds the secondary node changelogs a relationship mutation implies.

    A relationship change on the mutated node also changes the reciprocal relationship on each
    peer, so one secondary changelog is emitted per affected peer. The mutated node's own
    relationships and each secondary are filled with the peer's display label and HFID, resolved
    for every referenced peer in a single batched load.
    """

    def __init__(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        peer_label_resolver: PeerLabelResolver,
        reciprocal_builder: ReciprocalRelationshipBuilder,
        merger: SecondaryChangelogMerger,
    ) -> None:
        self._db = db
        self._branch = branch
        self._peer_label_resolver = peer_label_resolver
        self._reciprocal_builder = reciprocal_builder
        self._merger = merger

    async def get_changelogs(self, primary_changelog: NodeChangelog) -> list[NodeChangelog]:
        """Enrich the mutated node's relationships in place and return the secondaries they imply.

        Args:
            primary_changelog: Changelog of the node that was directly mutated. Its relationships
                are filled in place with each peer's display label and HFID.

        Returns:
            The secondary changelogs, one per affected peer.

        """
        peer_labels = await self._peer_label_resolver.resolve(changelog=primary_changelog)
        peer_labels.enrich(changelog=primary_changelog)

        with trace.get_tracer(__name__).start_as_current_span("changelog.build_secondaries") as span:
            span.set_attribute("changelog.referenced_peer_count", peer_labels.referenced_count)
            span.set_attribute("changelog.resolved_peer_count", peer_labels.resolved_count)
            secondaries = self._build_secondaries(primary_changelog=primary_changelog, peer_labels=peer_labels)
            span.set_attribute("changelog.secondary_count", len(secondaries))
        return secondaries

    def _build_secondaries(
        self, primary_changelog: NodeChangelog, peer_labels: ResolvedPeerLabels
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
                        peer_labels=peer_labels,
                    )
                )
            elif isinstance(relationship, RelationshipCardinalityManyChangelog):
                secondaries.extend(
                    self._parse_cardinality_many_relationship(
                        relationship=relationship,
                        node_schema=node_schema,
                        primary_changelog=primary_changelog,
                        schema_branch=schema_branch,
                        peer_labels=peer_labels,
                    )
                )
        return self._merger.merge(secondaries)

    def _parse_cardinality_one_relationship(
        self,
        relationship: RelationshipCardinalityOneChangelog,
        node_schema: MainSchemaTypes,
        primary_changelog: NodeChangelog,
        schema_branch: SchemaBranch,
        peer_labels: ResolvedPeerLabels,
    ) -> list[NodeChangelog]:
        secondaries: list[NodeChangelog] = []
        rel_schema = node_schema.get_relationship(name=relationship.name)

        if relationship.peer_status in (DiffAction.ADDED, DiffAction.UPDATED):
            peer_schema = schema_branch.get(name=str(relationship.peer_kind), duplicate=False)
            secondaries.extend(
                self._process_reciprocal_peers(
                    peer_id=str(relationship.peer_id),
                    peer_kind=str(relationship.peer_kind),
                    peer_schema=peer_schema,
                    rel_schema=rel_schema,
                    primary_changelog=primary_changelog,
                    peer_labels=peer_labels,
                    peer_status=DiffAction.ADDED,
                )
            )
        if relationship.peer_status in (DiffAction.UPDATED, DiffAction.REMOVED):
            previous_peer_schema = schema_branch.get(name=str(relationship.peer_kind_previous), duplicate=False)
            secondaries.extend(
                self._process_reciprocal_peers(
                    peer_id=str(relationship.peer_id_previous),
                    peer_kind=str(relationship.peer_kind_previous),
                    peer_schema=previous_peer_schema,
                    rel_schema=rel_schema,
                    primary_changelog=primary_changelog,
                    peer_labels=peer_labels,
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
        peer_labels: ResolvedPeerLabels,
    ) -> list[NodeChangelog]:
        secondaries: list[NodeChangelog] = []
        rel_schema = node_schema.get_relationship(name=relationship.name)

        for peer in relationship.peers:
            if peer.peer_status not in (DiffAction.ADDED, DiffAction.REMOVED):
                continue
            peer_schema = schema_branch.get(name=peer.peer_kind, duplicate=False)
            secondaries.extend(
                self._process_reciprocal_peers(
                    peer_id=peer.peer_id,
                    peer_kind=peer.peer_kind,
                    peer_schema=peer_schema,
                    rel_schema=rel_schema,
                    primary_changelog=primary_changelog,
                    peer_labels=peer_labels,
                    peer_status=peer.peer_status,
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
        peer_labels: ResolvedPeerLabels,
        peer_status: DiffAction,
    ) -> list[NodeChangelog]:
        """Build the secondary changelog a peer gets when its relationship to the primary changes."""
        labels = peer_labels.labels_of(peer_id=peer_id)
        node_changelog = NodeChangelog(
            node_id=peer_id,
            node_kind=peer_kind,
            display_label=labels.display_label,
            hfid=labels.hfid,
        )
        for reciprocal in self._reciprocal_builder.build(
            peer_schema=peer_schema,
            rel_schema=rel_schema,
            primary_changelog=primary_changelog,
            peer_status=peer_status,
        ).values():
            # Adding the relationship lifts the parent it names onto the changelog of the peer.
            node_changelog.add_relationship(relationship_changelog=reciprocal)

        return [node_changelog] if node_changelog.relationships else []
