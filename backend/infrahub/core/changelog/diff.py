from __future__ import annotations

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
        migration_tracker: MigrationTracker | None = None,
    ) -> None:
        self._diff = diff
        self._branch = branch
        self._db = db
        self._diff_nodes: dict[str, NodeInDiff]
        self.migration = migration_tracker or MigrationTracker()

    def _populate_diff_nodes(self) -> None:
        self._diff_nodes = {
            node.uuid: NodeInDiff(node_id=node.uuid, kind=node.kind, label=node.label) for node in self._diff.nodes
        }

    def get_node(self, node_id: str) -> NodeInDiff:
        return self._diff_nodes[node_id]

    def get_peer_kind(self, peer_id: str, node_kind: str, relationship_name: str) -> str:
        """If the peer kind doesn't exist in the diff use the peer kind from the schema"""
        try:
            return self.get_node(node_id=peer_id).kind
        except KeyError:
            schema = self._db.schema.get(node_kind, branch=self._branch, duplicate=False)
            rel_schema = schema.get_relationship(name=relationship_name)
            return rel_schema.peer

    def _process_node(self, node: EnrichedDiffNode) -> NodeChangelog:
        node_changelog = NodeChangelog(node_id=node.uuid, node_kind=node.kind, display_label=node.label)
        try:
            schema = self._db.schema.get(node_changelog.node_kind, branch=self._branch, duplicate=False)
        except SchemaNotFoundError:
            # if the schema has been deleted on self._branch
            schema = None
        for attribute in node.attributes:
            self._process_node_attribute(node=node_changelog, attribute=attribute, schema=schema)

        for relationship in node.relationships:
            self._process_node_relationship(node=node_changelog, relationship=relationship)

        return node_changelog

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
                case DatabaseEdgeType.IS_VISIBLE:
                    if _keep_branch_update(diff_property=attr_property):
                        changelog_attribute.add_property(
                            name="is_visible",
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
                    case DatabaseEdgeType.IS_VISIBLE:
                        changelog_rel.add_property(
                            name="is_visible",
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
        """Convert string based boolean for is_protected and is_visible."""
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
                peer_status=peer.action,
            )
            for peer_prop in peer.properties:
                match peer_prop.property_type:
                    case DatabaseEdgeType.IS_VISIBLE:
                        peer_log.add_property(
                            name="is_visible",
                            value_current=self._convert_string_boolean_value(value=peer_prop.new_value),
                            value_previous=self._convert_string_boolean_value(value=peer_prop.previous_value),
                        )
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

    def collect_changelogs(self) -> Sequence[tuple[DiffAction, NodeChangelog]]:
        self._populate_diff_nodes()
        changelogs = [
            (node.action, self._process_node(node=node))
            for node in self._diff.nodes
            if node.action != DiffAction.UNCHANGED
        ]
        return [(action, node_changelog) for action, node_changelog in changelogs if node_changelog.has_changes]


def _keep_branch_update(diff_property: EnrichedDiffProperty) -> bool:
    if diff_property.conflict and diff_property.conflict.selected_branch == ConflictSelection.BASE_BRANCH:
        return False
    return True


class MigrationTracker:
    """Keeps track of schema updates that happened as part of a migration"""

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
        """Return the current name of the requested attribute"""
        if node.node_kind not in self._migrations_attribute_map:
            return attribute.name
        if attribute.name not in self._migrations_attribute_map[node.node_kind]:
            return attribute.name

        return self._migrations_attribute_map[node.node_kind][attribute.name]
