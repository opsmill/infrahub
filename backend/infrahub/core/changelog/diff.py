from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

from infrahub_sdk.utils import str_to_bool

from infrahub.core.constants import DiffAction, RelationshipCardinality
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.model.path import ConflictSelection
from infrahub.exceptions import SchemaNotFoundError

from .models import (
    AttributeChangelog,
    NodeChangelog,
    RelationshipCardinalityManyChangelog,
    RelationshipCardinalityOneChangelog,
    RelationshipPeerChangelog,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from infrahub.core.branch import Branch
    from infrahub.core.diff.model.path import (
        EnrichedDiffAttribute,
        EnrichedDiffNode,
        EnrichedDiffProperty,
        EnrichedDiffRelationship,
        EnrichedDiffRoot,
    )
    from infrahub.core.models import SchemaUpdateMigrationInfo
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.database import InfrahubDatabase

    from .enrichment import NodeLabelLoader


@dataclass
class NodeInDiff:
    node_id: str
    kind: str
    label: str


class DiffChangelogCollector:
    def __init__(
        self,
        diff: EnrichedDiffRoot,
        branch: Branch,
        db: InfrahubDatabase,
        label_loader: NodeLabelLoader,
        migration_tracker: MigrationTracker | None = None,
    ) -> None:
        self._diff = diff
        self._branch = branch
        self._db = db
        self._label_loader = label_loader
        self._diff_nodes: dict[str, NodeInDiff]
        self._node_hfids: dict[str, list[str] | None] = {}
        self.migration = migration_tracker or MigrationTracker()

    def _populate_diff_nodes(self) -> None:
        self._diff_nodes = {
            node.uuid: NodeInDiff(node_id=node.uuid, kind=node.kind, label=node.label) for node in self._diff.nodes
        }

    def get_node(self, node_id: str) -> NodeInDiff:
        return self._diff_nodes[node_id]

    def get_peer_kind(self, peer_id: str, node_kind: str, relationship_name: str) -> str:
        """If the peer kind doesn't exist in the diff use the peer kind from the schema."""
        try:
            return self.get_node(node_id=peer_id).kind
        except KeyError:
            try:
                schema = self._db.schema.get(node_kind, branch=self._branch, duplicate=False)
            except SchemaNotFoundError:
                # The node's kind was dropped by a schema migration, so an unchanged peer's kind
                # cannot be resolved from the schema; degrade as the attribute path does.
                return "n/a"
            rel_schema = schema.get_relationship(name=relationship_name)
            return rel_schema.peer

    def _peer_hfid(self, peer_id: str) -> list[str] | None:
        """Return a peer's HFID when it is among the changed nodes already loaded for this diff.

        A changed relationship is symmetric, so a peer referenced here is normally a changed node
        itself and its HFID comes for free from the batch; a peer outside the diff keeps None.
        """
        return self._node_hfids.get(peer_id)

    def _process_node(self, node: EnrichedDiffNode) -> NodeChangelog:
        node_changelog = NodeChangelog(node_id=node.uuid, node_kind=node.kind, display_label=node.label)
        node_changelog.hfid = self._node_hfids.get(node.uuid)
        try:
            schema = self._db.schema.get(node_changelog.node_kind, branch=self._branch, duplicate=False)
        except SchemaNotFoundError:
            # if the schema has been deleted on self._branch
            schema = None
        for attribute in node.attributes:
            self._process_node_attribute(node=node_changelog, attribute=attribute, schema=schema)

        if node_changelog.hfid is None and node.action == DiffAction.REMOVED:
            # A removed node is gone when the batch load runs, but the diff still records its HFID;
            # recover it so removed nodes report it like directly-deleted ones.
            node_changelog.hfid = self._hfid_from_diff(node_changelog)

        for relationship in node.relationships:
            self._process_node_relationship(node=node_changelog, relationship=relationship)

        return node_changelog

    @staticmethod
    def _hfid_from_diff(node_changelog: NodeChangelog) -> list[str] | None:
        """Recover a node's HFID from the human-friendly-id attribute the diff carries for it."""
        attribute = node_changelog.attributes.get("human_friendly_id")
        if attribute is None:
            return None
        raw = attribute.value if attribute.value is not None else attribute.value_previous
        if not isinstance(raw, str):
            return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, list) else None

    def _process_node_attribute(
        self, node: NodeChangelog, attribute: EnrichedDiffAttribute, schema: MainSchemaTypes | None
    ) -> None:
        if schema is None:
            attribute_kind = "n/a"
        else:
            try:
                schema_attribute = schema.get_attribute(name=attribute.name)
                attribute_kind = schema_attribute.kind
            except ValueError:
                # This would currently happen if there has been a schema migration as part of the merge
                # then we don't have access to the attribute kind
                attribute_kind = "n/a"

        changelog_attribute = AttributeChangelog(
            name=self.migration.get_attribute_name(node=node, attribute=attribute), kind=attribute_kind
        )
        for attr_property in attribute.properties:
            match attr_property.property_type:
                case DatabaseEdgeType.HAS_VALUE:
                    # TODO deserialize correct value type from string
                    if _keep_branch_update(diff_property=attr_property):
                        changelog_attribute.set_value(value=attr_property.new_value)
                        changelog_attribute.set_value_previous(value=attr_property.previous_value)
                case DatabaseEdgeType.IS_PROTECTED:
                    if _keep_branch_update(diff_property=attr_property):
                        changelog_attribute.add_property(
                            name="is_protected",
                            value_current=self._convert_string_boolean_value(value=attr_property.new_value),
                            value_previous=self._convert_string_boolean_value(value=attr_property.previous_value),
                        )
                case DatabaseEdgeType.HAS_SOURCE:
                    if _keep_branch_update(diff_property=attr_property):
                        changelog_attribute.add_property(
                            name="source",
                            value_current=attr_property.new_value,
                            value_previous=attr_property.previous_value,
                        )
                case DatabaseEdgeType.HAS_OWNER:
                    if _keep_branch_update(diff_property=attr_property):
                        changelog_attribute.add_property(
                            name="owner",
                            value_current=attr_property.new_value,
                            value_previous=attr_property.previous_value,
                        )

        node.add_attribute(attribute=changelog_attribute)

    def _process_node_relationship(self, node: NodeChangelog, relationship: EnrichedDiffRelationship) -> None:
        match relationship.cardinality:
            case RelationshipCardinality.ONE:
                self._process_node_cardinality_one_relationship(node=node, relationship=relationship)

            case RelationshipCardinality.MANY:
                self._process_node_cardinality_many_relationship(node=node, relationship=relationship)

    def _process_node_cardinality_one_relationship(
        self, node: NodeChangelog, relationship: EnrichedDiffRelationship
    ) -> None:
        changelog_rel = RelationshipCardinalityOneChangelog(name=relationship.name)
        for entry in relationship.relationships:
            for rel_prop in entry.properties:
                match rel_prop.property_type:
                    case DatabaseEdgeType.IS_RELATED:
                        if rel_prop.new_value:
                            changelog_rel.peer_id = rel_prop.new_value
                            changelog_rel.peer_kind = self.get_peer_kind(
                                peer_id=rel_prop.new_value,
                                node_kind=node.node_kind,
                                relationship_name=relationship.name,
                            )
                            # The peer's display label is already carried by the diff, no load needed.
                            changelog_rel.peer_display_label = entry.peer_label
                            changelog_rel.peer_hfid = self._peer_hfid(peer_id=rel_prop.new_value)
                        if rel_prop.previous_value:
                            changelog_rel.peer_id_previous = rel_prop.previous_value
                            changelog_rel.peer_kind_previous = self.get_peer_kind(
                                peer_id=rel_prop.previous_value,
                                node_kind=node.node_kind,
                                relationship_name=relationship.name,
                            )
                    case DatabaseEdgeType.IS_PROTECTED:
                        changelog_rel.add_property(
                            name="is_protected",
                            value_current=self._convert_string_boolean_value(value=rel_prop.new_value),
                            value_previous=self._convert_string_boolean_value(value=rel_prop.previous_value),
                        )
                    case DatabaseEdgeType.HAS_OWNER:
                        changelog_rel.add_property(
                            name="owner",
                            value_current=rel_prop.new_value,
                            value_previous=rel_prop.previous_value,
                        )
                    case DatabaseEdgeType.HAS_SOURCE:
                        changelog_rel.add_property(
                            name="source",
                            value_current=rel_prop.new_value,
                            value_previous=rel_prop.previous_value,
                        )

        node.add_relationship(relationship_changelog=changelog_rel)

    def _convert_string_boolean_value(self, value: str | None) -> bool | None:
        """Convert string based boolean for is_protected."""
        if value is not None:
            return str_to_bool(value)

        return None

    def _process_node_cardinality_many_relationship(
        self, node: NodeChangelog, relationship: EnrichedDiffRelationship
    ) -> None:
        changelog_rel = RelationshipCardinalityManyChangelog(name=relationship.name)
        for peer in relationship.relationships:
            peer_log = RelationshipPeerChangelog(
                peer_id=peer.peer_id,
                peer_kind=self.get_peer_kind(
                    peer_id=peer.peer_id, node_kind=node.node_kind, relationship_name=relationship.name
                ),
                peer_display_label=peer.peer_label,
                peer_hfid=self._peer_hfid(peer_id=peer.peer_id),
                peer_status=peer.action,
            )
            for peer_prop in peer.properties:
                match peer_prop.property_type:
                    case DatabaseEdgeType.IS_PROTECTED:
                        peer_log.add_property(
                            name="is_protected",
                            value_current=self._convert_string_boolean_value(value=peer_prop.new_value),
                            value_previous=self._convert_string_boolean_value(value=peer_prop.previous_value),
                        )
                    case DatabaseEdgeType.HAS_OWNER:
                        peer_log.add_property(
                            name="owner",
                            value_current=peer_prop.new_value,
                            value_previous=peer_prop.previous_value,
                        )
                    case DatabaseEdgeType.HAS_SOURCE:
                        peer_log.add_property(
                            name="source",
                            value_current=peer_prop.new_value,
                            value_previous=peer_prop.previous_value,
                        )

            changelog_rel.peers.append(peer_log)

        node.add_relationship(relationship_changelog=changelog_rel)

    async def collect_changelogs(self) -> Sequence[tuple[DiffAction, NodeChangelog]]:
        """Build a changelog for every changed node in the diff, filled with each node's HFID.

        Every changed node's HFID is resolved in a single batched load, since the diff itself does
        not carry it.

        Returns:
            One (action, changelog) pair per changed node that has recorded changes.

        """
        self._populate_diff_nodes()
        changed_nodes = [node for node in self._diff.nodes if node.action != DiffAction.UNCHANGED]
        # A node whose kind was dropped by a schema migration in the merge has no schema to resolve
        # labels against; leave it out of the load so one such node cannot fail the whole batch.
        labelable_ids = [
            node.uuid for node in changed_nodes if self._db.schema.has(name=node.kind, branch=self._branch)
        ]
        self._node_hfids = await self._label_loader.load_hfids(labelable_ids)
        changelogs = [(node.action, self._process_node(node=node)) for node in changed_nodes]
        changelogs = [(action, node_changelog) for action, node_changelog in changelogs if node_changelog.has_changes]
        await self._resolve_external_peer_hfids([node_changelog for _, node_changelog in changelogs])
        return changelogs

    def _peer_entries(
        self, changelogs: list[NodeChangelog]
    ) -> Iterator[RelationshipCardinalityOneChangelog | RelationshipPeerChangelog]:
        """Yield every relationship-peer holder across the changelogs (one-cardinality and each many-peer)."""
        for changelog in changelogs:
            for relationship in changelog.relationships.values():
                yield from relationship.peer_entries()

    def _needs_external_hfid(self, peer: RelationshipCardinalityOneChangelog | RelationshipPeerChangelog) -> bool:
        """True for a referenced peer whose HFID the changed-node load did not already resolve."""
        return peer.peer_hfid is None and peer.peer_id not in self._node_hfids

    async def _resolve_external_peer_hfids(self, changelogs: list[NodeChangelog]) -> None:
        """Fill the HFID of relationship peers that are referenced but not themselves changed nodes.

        A changed relationship is usually symmetric, so most peers are changed nodes already loaded;
        this resolves the rest so a peer's HFID does not depend on whether the peer also changed.
        """
        peers = list(self._peer_entries(changelogs))
        external_ids = [peer.peer_id for peer in peers if peer.peer_id and self._needs_external_hfid(peer)]
        if not external_ids:
            return
        peer_hfids = await self._label_loader.load_hfids(external_ids)
        for peer in peers:
            if peer.peer_hfid is None and peer.peer_id in peer_hfids:
                peer.peer_hfid = peer_hfids[peer.peer_id]


def _keep_branch_update(diff_property: EnrichedDiffProperty) -> bool:
    if diff_property.conflict and diff_property.conflict.selected_branch == ConflictSelection.BASE_BRANCH:
        return False
    return True


class MigrationTracker:
    """Keeps track of schema updates that happened as part of a migration."""

    def __init__(self, migrations: list[SchemaUpdateMigrationInfo] | None = None) -> None:
        # A dictionary of Node kind, previous attribute name and new attribute
        # {"TestPerson": {"old_attribute_name": "new_attribute_name"}}
        self._migrations_attribute_map: dict[str, dict[str, str]] = {}

        migrations = migrations or []
        for migration in migrations:
            if migration.migration_name == "attribute.name.update":
                if migration.path.schema_kind not in self._migrations_attribute_map:
                    self._migrations_attribute_map[migration.path.schema_kind] = {}
                if migration.path.property_name and migration.path.field_name:
                    self._migrations_attribute_map[migration.path.schema_kind][migration.path.property_name] = (
                        migration.path.field_name
                    )

    def get_attribute_name(self, node: NodeChangelog, attribute: EnrichedDiffAttribute) -> str:
        """Return the current name of the requested attribute."""
        if node.node_kind not in self._migrations_attribute_map:
            return attribute.name
        if attribute.name not in self._migrations_attribute_map[node.node_kind]:
            return attribute.name

        return self._migrations_attribute_map[node.node_kind][attribute.name]
