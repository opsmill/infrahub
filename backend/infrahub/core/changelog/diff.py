from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub_sdk.utils import str_to_bool
from opentelemetry import trace

from infrahub.core.constants import DiffAction, RelationshipCardinality
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.model.path import ConflictSelection
from infrahub.core.diff.ownership_differ import OwnershipDiffer
from infrahub.core.ownership.fields import (
    OWNERS_CHANGELOG_KIND,
    attribute_owners_change,
    diff_field_name,
    is_list_property,
    is_owners_field_name,
    owner_list_value,
    stored_owner_ids,
)
from infrahub.core.ownership.models import INHERIT
from infrahub.exceptions import SchemaNotFoundError

from .models import (
    AttributeChangelog,
    NodeChangelog,
    RelationshipCardinalityManyChangelog,
    RelationshipCardinalityOneChangelog,
    RelationshipPeerChangelog,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

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
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase

    from .hfid_resolver import ChangelogHfidResolver


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
        hfid_resolver: ChangelogHfidResolver,
        migration_tracker: MigrationTracker | None = None,
        merge_at: Timestamp | None = None,
    ) -> None:
        """Set `merge_at` to the time of a merge into `branch`.

        The changelog then leaves out each owner list that `branch` held just before the merge.
        """
        self._diff = diff
        self._branch = branch
        self._db = db
        self._hfid_resolver = hfid_resolver
        self._diff_nodes: dict[str, NodeInDiff]
        self.migration = migration_tracker or MigrationTracker()
        self._merge_at = merge_at
        self._owner_lists_held: set[tuple[str, str]] = set()

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
            pass
        try:
            schema = self._db.schema.get(node_kind, branch=self._branch, duplicate=False)
            return schema.get_relationship(name=relationship_name).peer
        except (SchemaNotFoundError, ValueError):
            # a schema migration removed the kind or the relationship, so the peer kind is not known anymore
            return "n/a"

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
        if is_owners_field_name(field_name=attribute.name) and (
            schema is None or attribute.name not in schema.attribute_names
        ):
            self._process_owner_list(node=node, attribute=attribute)
            return
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
                    if self._is_owner_list_change(node=node, field_name=attribute.name, owner_list=attr_property):
                        _add_owners_property(attribute=changelog_attribute, diff_property=attr_property)

        node.add_attribute(attribute=changelog_attribute)

    def _process_owner_list(self, node: NodeChangelog, attribute: EnrichedDiffAttribute) -> None:
        for owner_list in attribute.properties:
            if is_list_property(
                field_name=attribute.name, property_type=owner_list.property_type
            ) and self._is_owner_list_change(node=node, field_name=attribute.name, owner_list=owner_list):
                node.add_attribute(
                    attribute=AttributeChangelog(
                        name=attribute.name,
                        kind=OWNERS_CHANGELOG_KIND,
                        value=owner_list.new_value,
                        value_previous=owner_list.previous_value,
                    )
                )

    def _is_owner_list_change(self, node: NodeChangelog, field_name: str, owner_list: EnrichedDiffProperty) -> bool:
        return (
            _keep_branch_update(diff_property=owner_list) and (node.node_id, field_name) not in self._owner_lists_held
        )

    async def _read_owner_lists_held(self, nodes: list[EnrichedDiffNode]) -> set[tuple[str, str]]:
        """Return the node ID and the field name of each owner list of the diff that the branch held before the merge.

        The merge writes no edge for such a list.
        """
        owner_lists = [
            (node, attribute.name, diff_property)
            for node in nodes
            for attribute in node.attributes
            for diff_property in attribute.properties
            if is_list_property(field_name=attribute.name, property_type=diff_property.property_type)
        ]
        if self._merge_at is None or not owner_lists:
            return set()
        # The edges that the merge writes start at the merge time.
        states = await OwnershipDiffer(db=self._db).read_states(
            branch=self._branch,
            at=self._merge_at.subtract(microseconds=1),
            node_ids=sorted({node.uuid for node, _, _ in owner_lists}),
        )
        # After a kind change on the destination branch, only the schema of the merged branch has the kind of the diff.
        schema_branches = [
            self._db.schema.get_schema_branch(name=name) for name in (self._branch.name, self._diff.diff_branch_name)
        ]
        field_states = {}
        for (node_id, holder), state in states.items():
            kind = self.get_node(node_id=node_id).kind
            if field_name := diff_field_name(holder=holder, kind=kind, schema_branches=schema_branches):
                field_states[node_id, field_name] = state
        held = set()
        for node, field_name, diff_property in owner_lists:
            state = field_states.get((node.uuid, field_name), INHERIT)
            # A template mark that the branch closes is a change also when the owners stay the same.
            if state.template_id is None and owner_list_value(owner_ids=state.owner_ids) == owner_list_value(
                owner_ids=stored_owner_ids(value=diff_property.new_value)
            ):
                held.add((node.uuid, field_name))
        return held

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
        """Build a changelog for every changed node in the diff, with node and peer HFIDs resolved.

        Returns:
            One (action, changelog) pair per changed node that has recorded changes.

        """
        with trace.get_tracer(__name__).start_as_current_span("changelog.collect_changelogs") as span:
            self._populate_diff_nodes()
            changed_nodes = [node for node in self._diff.nodes if node.action != DiffAction.UNCHANGED]
            span.set_attribute("changelog.diff_node_count", len(self._diff.nodes))
            span.set_attribute("changelog.changed_node_count", len(changed_nodes))
            # A node whose kind was dropped by a schema migration in the merge has no schema to resolve
            # labels against; leave it out of the load so one such node cannot fail the whole batch.
            resolvable_ids = [node.uuid for node in changed_nodes if self._is_resolvable_kind(node.kind)]
            self._owner_lists_held = await self._read_owner_lists_held(nodes=changed_nodes)
            with trace.get_tracer(__name__).start_as_current_span("changelog.build_from_diff"):
                changelogs = [
                    (node.action, node_changelog)
                    for node in changed_nodes
                    if (node_changelog := self._process_node(node=node)).has_changes
                ]
            span.set_attribute("changelog.changelog_count", len(changelogs))
            await self._hfid_resolver.enrich(
                changelogs=changelogs, resolvable_ids=resolvable_ids, is_resolvable_kind=self._is_resolvable_kind
            )
            return changelogs

    def _is_resolvable_kind(self, kind: str) -> bool:
        """Whether a node kind still exists on the branch, so its labels can be loaded."""
        return self._db.schema.has(name=kind, branch=self._branch)


def _add_owners_property(attribute: AttributeChangelog, diff_property: EnrichedDiffProperty) -> None:
    name, value, value_previous = attribute_owners_change(
        owner_ids=stored_owner_ids(value=diff_property.new_value),
        previous_owner_ids=stored_owner_ids(value=diff_property.previous_value),
    )
    attribute.add_property(name=name, value_current=value, value_previous=value_previous)


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
