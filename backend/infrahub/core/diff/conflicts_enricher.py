from uuid import uuid4

import ujson

from infrahub.core.constants import NULL_VALUE, DiffAction, RelationshipCardinality
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import BranchNotFoundError, InitializationError, SchemaNotFoundError

from .model.path import (
    EnrichedDiffAttribute,
    EnrichedDiffConflict,
    EnrichedDiffNode,
    EnrichedDiffProperty,
    EnrichedDiffRelationship,
    EnrichedDiffRoot,
    EnrichedDiffSingleRelationship,
)

# Attribute kinds whose value is a JSON collection that an "ordered=False" schema flag can make
# order-insensitive during conflict detection.
_UNORDERED_CAPABLE_KINDS = {"List", "JSON"}


class ConflictsEnricher:
    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db
        self._base_branch_name: str | None = None
        self._diff_branch_name: str | None = None
        # node kind -> set of attribute names to compare order-insensitively, cached per run
        self._order_insensitive_attrs: dict[str, set[str]] = {}

    @property
    def base_branch_name(self) -> str:
        if not self._base_branch_name:
            raise RuntimeError("could not identify base branch")
        return self._base_branch_name

    @property
    def diff_branch_name(self) -> str:
        if not self._diff_branch_name:
            raise RuntimeError("could not identify diff branch")
        return self._diff_branch_name

    async def add_conflicts_to_branch_diff(
        self, base_diff_root: EnrichedDiffRoot, branch_diff_root: EnrichedDiffRoot
    ) -> None:
        self._base_branch_name = branch_diff_root.base_branch_name
        self._diff_branch_name = branch_diff_root.diff_branch_name
        self._order_insensitive_attrs = {}

        base_node_map = {n.uuid: n for n in base_diff_root.nodes}
        branch_node_map = {n.uuid: n for n in branch_diff_root.nodes}
        branch_node_map_uuids = set(branch_node_map.keys())
        common_node_uuids = set(base_node_map.keys()) & branch_node_map_uuids
        for node_uuid in common_node_uuids:
            base_node = base_node_map[node_uuid]
            branch_node = branch_node_map[node_uuid]
            self._add_node_conflicts(base_node=base_node, branch_node=branch_node)
        # remove conflicts from branch nodes that have been manually corrected on the base branch
        for branch_only_node_uuid in branch_node_map_uuids - common_node_uuids:
            branch_node = branch_node_map[branch_only_node_uuid]
            branch_node.clear_conflicts()

    def _add_node_conflicts(self, base_node: EnrichedDiffNode, branch_node: EnrichedDiffNode) -> None:
        if base_node.action != branch_node.action and DiffAction.UNCHANGED not in {
            base_node.action,
            branch_node.action,
        }:
            self._add_node_conflict(base_node=base_node, branch_node=branch_node)
        elif branch_node.conflict:
            branch_node.conflict = None
        # adding attr/rel conflicts when there is an unresolvable node-level conflict is pointless
        if branch_node.conflict and branch_node.conflict.resolvable is False:
            return
        base_attribute_map = {a.name: a for a in base_node.attributes}
        branch_attribute_map = {a.name: a for a in branch_node.attributes}
        common_attribute_names = set(base_attribute_map.keys()) & set(branch_attribute_map.keys())
        order_insensitive_attrs = self._get_order_insensitive_attrs(node_kind=branch_node.kind)
        for branch_attribute in branch_node.attributes:
            if branch_attribute.name in common_attribute_names:
                base_attribute = base_attribute_map[branch_attribute.name]
                self._add_attribute_conflicts(
                    base_attribute=base_attribute,
                    branch_attribute=branch_attribute,
                    ignore_order=branch_attribute.name in order_insensitive_attrs,
                )
            else:
                branch_attribute.clear_conflicts()
        base_relationship_map = {r.name: r for r in base_node.relationships}
        branch_relationship_map = {r.name: r for r in branch_node.relationships}
        common_relationship_names = set(base_relationship_map.keys()) & set(branch_relationship_map.keys())
        for branch_relationship in branch_node.relationships:
            if branch_relationship.name in common_relationship_names:
                base_relationship = base_relationship_map[branch_relationship.name]
                self._add_relationship_conflicts(
                    base_relationship=base_relationship,
                    branch_relationship=branch_relationship,
                )
            else:
                branch_relationship.clear_conflicts()

    def _get_order_insensitive_attrs(self, node_kind: str) -> set[str]:
        """Names of the node's attributes whose element order should be ignored when detecting conflicts.

        The schema is resolved from the diff (source) branch so that a branch which itself changes an
        attribute's ``ordered`` flag is honored within its own diff, rather than the value on the base.
        """
        if node_kind in self._order_insensitive_attrs:
            return self._order_insensitive_attrs[node_kind]
        names: set[str] = set()
        try:
            node_schema = self.db.schema.get(name=node_kind, branch=self._diff_branch_name, duplicate=False)
        except (SchemaNotFoundError, BranchNotFoundError, InitializationError):
            # Without a resolvable schema we cannot know the ordering intent; fall back to
            # order-sensitive comparison rather than risk suppressing a real conflict.
            self._order_insensitive_attrs[node_kind] = names
            return names
        for attribute_schema in node_schema.attributes:
            if attribute_schema.kind in _UNORDERED_CAPABLE_KINDS and attribute_schema.ordered is False:
                names.add(attribute_schema.name)
        self._order_insensitive_attrs[node_kind] = names
        return names

    def _add_node_conflict(self, base_node: EnrichedDiffNode, branch_node: EnrichedDiffNode) -> None:
        if branch_node.conflict:
            conflict_uuid = branch_node.conflict.uuid
            selected_branch = branch_node.conflict.selected_branch
        else:
            conflict_uuid = str(uuid4())
            selected_branch = None
        resolvable = True
        # this condition should always be true, but it's good to be explicit
        if DiffAction.REMOVED in [base_node.action, branch_node.action]:
            resolvable = False
        branch_node.conflict = EnrichedDiffConflict(
            uuid=conflict_uuid,
            base_branch_action=base_node.action,
            base_branch_value=None,
            base_branch_changed_at=base_node.changed_at,
            diff_branch_action=branch_node.action,
            diff_branch_value=None,
            diff_branch_changed_at=branch_node.changed_at,
            selected_branch=selected_branch,
            resolvable=resolvable,
        )

    def _add_attribute_conflicts(
        self,
        base_attribute: EnrichedDiffAttribute,
        branch_attribute: EnrichedDiffAttribute,
        ignore_order: bool = False,
    ) -> None:
        base_property_map = {p.property_type: p for p in base_attribute.properties}
        branch_property_map = {p.property_type: p for p in branch_attribute.properties}
        common_property_types = set(base_property_map.keys()) & set(branch_property_map.keys())
        for branch_property in branch_attribute.properties:
            if branch_property.property_type not in common_property_types:
                branch_property.conflict = None
                continue
            base_property = base_property_map[branch_property.property_type]
            property_actions = {branch_property.action, base_property.action}
            if DiffAction.UNCHANGED in property_actions:
                branch_property.conflict = None
                continue
            # only the attribute value edge can hold a reorderable collection
            value_order_insensitive = ignore_order and branch_property.property_type is DatabaseEdgeType.HAS_VALUE
            same_value = self._have_same_value(
                base_property=base_property,
                branch_property=branch_property,
                ignore_order=value_order_insensitive,
            )
            if same_value:
                branch_property.conflict = None
                continue
            self._add_property_conflict(
                base_property=base_property,
                branch_property=branch_property,
            )

    def _add_relationship_conflicts(
        self,
        base_relationship: EnrichedDiffRelationship,
        branch_relationship: EnrichedDiffRelationship,
    ) -> None:
        is_cardinality_one = branch_relationship.cardinality is RelationshipCardinality.ONE
        if is_cardinality_one:
            if not base_relationship.relationships or not branch_relationship.relationships:
                branch_relationship.clear_conflicts()
                return
            base_element = next(iter(base_relationship.relationships))
            branch_element = next(iter(branch_relationship.relationships))
            self._add_relationship_conflicts_for_one_peer(
                base_element=base_element,
                branch_element=branch_element,
                is_cardinality_one=is_cardinality_one,
            )
            return
        base_peer_id_map = {element.peer_id: element for element in base_relationship.relationships}
        branch_peer_id_map = {element.peer_id: element for element in branch_relationship.relationships}
        common_peer_ids = set(base_peer_id_map.keys()) & set(branch_peer_id_map.keys())
        for branch_element in branch_relationship.relationships:
            if branch_element.peer_id not in common_peer_ids:
                branch_element.clear_conflicts()
                continue
            base_element = base_peer_id_map[branch_element.peer_id]
            self._add_relationship_conflicts_for_one_peer(
                base_element=base_element,
                branch_element=branch_element,
                is_cardinality_one=is_cardinality_one,
            )

    def _add_relationship_conflicts_for_one_peer(
        self,
        base_element: EnrichedDiffSingleRelationship,
        branch_element: EnrichedDiffSingleRelationship,
        is_cardinality_one: bool,
    ) -> None:
        base_properties_by_type = {p.property_type: p for p in base_element.properties}
        branch_properties_by_type = {p.property_type: p for p in branch_element.properties}
        common_property_types = set(base_properties_by_type.keys()) & set(branch_properties_by_type.keys())
        for branch_property in branch_element.properties:
            if branch_property.property_type not in common_property_types:
                branch_property.conflict = None
                continue
            base_property = base_properties_by_type[branch_property.property_type]
            includes_unchanged = DiffAction.UNCHANGED in {branch_property.action, base_property.action}
            same_value = self._have_same_value(base_property=base_property, branch_property=branch_property)
            # special handling for cardinality-one peer ID conflict
            if branch_property.property_type is DatabaseEdgeType.IS_RELATED and is_cardinality_one:
                if same_value or includes_unchanged:
                    branch_element.conflict = None
                    branch_property.conflict = None
                    continue
                if branch_element.conflict:
                    conflict_uuid = branch_element.conflict.uuid
                    selected_branch = branch_element.conflict.selected_branch
                else:
                    conflict_uuid = str(uuid4())
                    selected_branch = None
                conflict = EnrichedDiffConflict(
                    uuid=conflict_uuid,
                    base_branch_action=base_element.action,
                    base_branch_value=base_property.new_value,
                    base_branch_changed_at=base_property.changed_at,
                    diff_branch_action=branch_element.action,
                    diff_branch_value=branch_property.new_value,
                    diff_branch_changed_at=branch_property.changed_at,
                    selected_branch=selected_branch,
                )
                branch_element.conflict = conflict
                continue
            if same_value or includes_unchanged:
                branch_property.conflict = None
                continue
            if branch_property.conflict:
                conflict_uuid = branch_property.conflict.uuid
                selected_branch = branch_property.conflict.selected_branch
            else:
                conflict_uuid = str(uuid4())
                selected_branch = None
            branch_property.conflict = EnrichedDiffConflict(
                uuid=conflict_uuid,
                base_branch_action=base_property.action,
                base_branch_value=base_property.new_value,
                base_branch_changed_at=base_property.changed_at,
                diff_branch_action=branch_property.action,
                diff_branch_value=branch_property.new_value,
                diff_branch_changed_at=branch_property.changed_at,
                selected_branch=selected_branch,
            )

    def _add_property_conflict(
        self,
        base_property: EnrichedDiffProperty,
        branch_property: EnrichedDiffProperty,
    ) -> None:
        if branch_property.conflict:
            conflict_uuid = branch_property.conflict.uuid
            selected_branch = branch_property.conflict.selected_branch
        else:
            conflict_uuid = str(uuid4())
            selected_branch = None
        branch_property.conflict = EnrichedDiffConflict(
            uuid=conflict_uuid,
            base_branch_action=base_property.action,
            base_branch_value=base_property.new_value,
            base_branch_changed_at=base_property.changed_at,
            diff_branch_action=branch_property.action,
            diff_branch_value=branch_property.new_value,
            diff_branch_changed_at=branch_property.changed_at,
            selected_branch=selected_branch,
        )

    def _have_same_value(
        self,
        base_property: EnrichedDiffProperty,
        branch_property: EnrichedDiffProperty,
        ignore_order: bool = False,
    ) -> bool:
        if base_property.new_value == branch_property.new_value:
            return True
        if ignore_order and self._same_unordered_list(base_property.new_value, branch_property.new_value):
            return True
        if {base_property.new_value, branch_property.new_value} <= {NULL_VALUE, None}:
            return True
        if (
            base_property.action is DiffAction.UNCHANGED
            and base_property.previous_value == branch_property.previous_value
        ):
            return True
        return False

    def _same_unordered_list(self, base_value: str | None, branch_value: str | None) -> bool:
        """True only when both values parse to JSON arrays holding the same elements, ignoring order.

        Element multiplicity is preserved (multiset comparison) and dict/list elements are canonicalized,
        so ``["a","b"]`` matches ``["b","a"]`` but ``["a","a"]`` does not match ``["a"]``. Any value that
        is not a JSON array (a dict, a scalar, malformed JSON) yields False so the caller falls back to
        exact comparison.
        """
        base_canonical = self._canonical_list_signature(base_value)
        if base_canonical is None:
            return False
        branch_canonical = self._canonical_list_signature(branch_value)
        if branch_canonical is None:
            return False
        return base_canonical == branch_canonical

    def _canonical_list_signature(self, value: str | None) -> list[str] | None:
        if value is None or value == NULL_VALUE:
            return None
        parsed = value
        if isinstance(parsed, str):
            try:
                parsed = ujson.loads(parsed)
            except (ValueError, TypeError):
                return None
        if not isinstance(parsed, list):
            return None
        try:
            return sorted(ujson.dumps(element, sort_keys=True) for element in parsed)
        except (ValueError, TypeError):
            return None
