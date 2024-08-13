from __future__ import annotations

from typing import TYPE_CHECKING, Any, Counter, Optional, Union

from graphene import Boolean, DateTime, Field, Int, List, ObjectType, String
from graphene import Enum as GrapheneEnum
from infrahub_sdk.utils import extract_fields

from infrahub.core import registry
from infrahub.core.constants import DiffAction
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.timestamp import Timestamp
from infrahub.dependencies.registry import get_component_registry

if TYPE_CHECKING:
    from datetime import datetime

    from graphql import GraphQLResolveInfo

    from infrahub.core.diff.model.path import (
        EnrichedDiffAttribute,
        EnrichedDiffNode,
        EnrichedDiffProperty,
        EnrichedDiffRelationship,
        EnrichedDiffRoot,
        EnrichedDiffSingleRelationship,
    )
    from infrahub.graphql import GraphqlContext

GrapheneDiffActionEnum = GrapheneEnum.from_enum(DiffAction)


class ConflictSelection(GrapheneEnum):
    BASE_BRANCH = "base"
    DIFF_BRANCH = "diff"


class ConflictDetails(ObjectType):
    uuid = String(required=True)
    base_branch_action = Field(GrapheneDiffActionEnum, required=True)
    base_branch_value = String()
    base_branch_changed_at = DateTime(required=True)
    diff_branch_action = Field(GrapheneDiffActionEnum, required=True)
    diff_branch_value = String()
    diff_branch_changed_at = DateTime(required=True)
    selected_branch = Field(ConflictSelection)


class DiffSummaryCounts(ObjectType):
    num_added = Int(required=False)
    num_updated = Int(required=False)
    num_removed = Int(required=False)
    num_conflicts = Int(required=False)


class DiffProperty(ObjectType):
    property_type = String(required=True)
    last_changed_at = DateTime(required=True)
    previous_value = String(required=False)
    new_value = String(required=False)
    status = Field(GrapheneDiffActionEnum, required=True)
    conflict = Field(ConflictDetails, required=False)


class DiffAttribute(DiffSummaryCounts):
    name = String(required=True)
    last_changed_at = DateTime(required=True)
    status = Field(GrapheneDiffActionEnum, required=True)
    properties = List(DiffProperty)
    contains_conflict = Boolean(required=True)


class DiffSingleRelationship(DiffSummaryCounts):
    last_changed_at = DateTime(required=False)
    status = Field(GrapheneDiffActionEnum, required=True)
    peer_id = String(required=True)
    contains_conflict = Boolean(required=True)
    conflict = Field(ConflictDetails, required=False)
    properties = List(DiffProperty)


class DiffRelationship(DiffSummaryCounts):
    name = String(required=True)
    label = String(required=False)
    last_changed_at = DateTime(required=False)
    status = Field(GrapheneDiffActionEnum, required=True)
    elements = List(DiffSingleRelationship, required=True)
    node_uuids = List(String, required=True)
    contains_conflict = Boolean(required=True)


class DiffNode(DiffSummaryCounts):
    uuid = String(required=True)
    kind = String(required=True)
    label = String(required=True)
    status = Field(GrapheneDiffActionEnum, required=True)
    contains_conflict = Boolean(required=True)
    last_changed_at = DateTime(required=False)
    attributes = List(DiffAttribute, required=True)
    relationships = List(DiffRelationship, required=True)


class DiffTree(DiffSummaryCounts):
    base_branch = String(required=True)
    diff_branch = String(required=True)
    from_time = DateTime(required=True)
    to_time = DateTime(required=True)
    nodes = List(DiffNode)


class DiffTreeResolver:
    def to_diff_tree(self, enriched_diff_root: EnrichedDiffRoot) -> DiffTree:
        all_nodes = list(enriched_diff_root.nodes)
        for e_node in enriched_diff_root.nodes:
            all_nodes += list(e_node.get_all_child_nodes())
        tree_nodes = [self.to_diff_node(enriched_node=e_node) for e_node in all_nodes]
        summary_counter = Counter((n.status for n in tree_nodes))
        return DiffTree(
            base_branch=enriched_diff_root.base_branch_name,
            diff_branch=enriched_diff_root.diff_branch_name,
            from_time=enriched_diff_root.from_time.to_graphql(),
            to_time=enriched_diff_root.to_time.to_graphql(),
            nodes=tree_nodes,
            num_added=summary_counter[DiffAction.ADDED],
            num_updated=summary_counter[DiffAction.UPDATED],
            num_removed=summary_counter[DiffAction.REMOVED],
            num_conflicts=0,
        )

    def to_diff_node(self, enriched_node: EnrichedDiffNode) -> DiffNode:
        diff_attributes = [self.to_diff_attribute(e_attr) for e_attr in enriched_node.attributes]
        diff_relationships = [self.to_diff_relationship(e_rel) for e_rel in enriched_node.relationships]
        summary_counter = Counter((field.action for field in (enriched_node.attributes | enriched_node.relationships)))
        num_conflicts = 0
        contains_conflict = any(a.contains_conflict for a in diff_attributes)
        contains_conflict |= any(r.contains_conflict for r in diff_relationships)
        return DiffNode(
            uuid=enriched_node.uuid,
            kind=enriched_node.kind,
            label=enriched_node.label,
            status=enriched_node.action,
            last_changed_at=enriched_node.changed_at.obj,
            attributes=diff_attributes,
            relationships=diff_relationships,
            contains_conflict=contains_conflict,
            num_added=summary_counter[DiffAction.ADDED],
            num_updated=summary_counter[DiffAction.UPDATED],
            num_removed=summary_counter[DiffAction.REMOVED],
            num_conflicts=num_conflicts,
        )

    def to_diff_attribute(self, enriched_attribute: EnrichedDiffAttribute) -> DiffAttribute:
        diff_properties = [self.to_diff_property(e_prop) for e_prop in enriched_attribute.properties]
        summary_counter = Counter((prop.action for prop in enriched_attribute.properties))
        num_conflicts = 0
        contains_conflict = any(p.conflict is not None for p in diff_properties)
        return DiffAttribute(
            name=enriched_attribute.name,
            last_changed_at=enriched_attribute.changed_at.obj,
            status=enriched_attribute.action,
            properties=diff_properties,
            contains_conflict=contains_conflict,
            num_added=summary_counter[DiffAction.ADDED],
            num_updated=summary_counter[DiffAction.UPDATED],
            num_removed=summary_counter[DiffAction.REMOVED],
            num_conflicts=num_conflicts,
        )

    def to_diff_relationship(self, enriched_relationship: EnrichedDiffRelationship) -> DiffRelationship:
        diff_elements = [self.to_diff_relationship_element(element) for element in enriched_relationship.relationships]
        node_uuids = [n.uuid for n in enriched_relationship.nodes]
        num_conflicts = 0
        contains_conflict = any(element.contains_conflict for element in diff_elements)
        summary_counter = Counter(
            (element.action for element in (enriched_relationship.relationships | enriched_relationship.nodes))
        )
        return DiffRelationship(
            name=enriched_relationship.name,
            label=enriched_relationship.label,
            last_changed_at=enriched_relationship.changed_at.obj,
            status=enriched_relationship.action,
            elements=diff_elements,
            node_uuids=node_uuids,
            contains_conflict=contains_conflict,
            num_added=summary_counter[DiffAction.ADDED],
            num_updated=summary_counter[DiffAction.UPDATED],
            num_removed=summary_counter[DiffAction.REMOVED],
            num_conflicts=num_conflicts,
        )

    def to_diff_relationship_element(self, enriched_element: EnrichedDiffSingleRelationship) -> DiffSingleRelationship:
        diff_properties = [self.to_diff_property(e_prop) for e_prop in enriched_element.properties]
        num_conflicts = 0
        contains_conflict = any(p.conflict is not None for p in diff_properties)
        summary_counter = Counter((prop.action for prop in enriched_element.properties))
        return DiffSingleRelationship(
            last_changed_at=enriched_element.changed_at.obj,
            status=enriched_element.action,
            peer_id=enriched_element.peer_id,
            contains_conflict=contains_conflict,
            conflict=None,
            properties=diff_properties,
            num_added=summary_counter[DiffAction.ADDED],
            num_updated=summary_counter[DiffAction.UPDATED],
            num_removed=summary_counter[DiffAction.REMOVED],
            num_conflicts=num_conflicts,
        )

    def to_diff_property(self, enriched_property: EnrichedDiffProperty) -> DiffProperty:
        return DiffProperty(
            property_type=enriched_property.property_type.value,
            last_changed_at=enriched_property.changed_at.obj,
            previous_value=enriched_property.previous_value,
            new_value=enriched_property.new_value,
            status=enriched_property.action,
            conflict=None,
        )

    def to_graphql(
        self, fields: dict[str, dict], diff_object: Optional[Any]
    ) -> Optional[Union[list[dict[str, Any]], dict[str, Any]]]:
        if diff_object is None:
            return None
        if isinstance(diff_object, list):
            list_response = True
            diff_elements = diff_object
        else:
            list_response = False
            diff_elements = [diff_object]

        response_list = []
        for diff_object_element in diff_elements:
            element_response = {}
            for field_name, sub_fields in fields.items():
                if sub_fields is None:
                    element_response[field_name] = getattr(diff_object_element, field_name, None)
                elif hasattr(diff_object_element, field_name):
                    element_response[field_name] = self.to_graphql(sub_fields, getattr(diff_object_element, field_name))
                else:
                    continue
            response_list.append(element_response)
        if list_response:
            return response_list
        return response_list[0]

    async def resolve(  # pylint: disable=unused-argument
        self,
        root: dict,
        info: GraphQLResolveInfo,
        branch: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        root_node_uuids: list[str] | None = None,
        max_depth: int | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Optional[Union[list[dict[str, Any]], dict[str, Any]]]:
        component_registry = get_component_registry()
        context: GraphqlContext = info.context
        base_branch = await registry.get_branch(db=context.db, branch=registry.default_branch)
        diff_branch = await registry.get_branch(db=context.db, branch=branch)
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=context.db, branch=diff_branch)
        if from_time:
            from_timestamp = Timestamp(from_time.isoformat())
        else:
            from_timestamp = Timestamp(diff_branch.get_created_at())
        if to_time:
            to_timestamp = Timestamp(to_time.isoformat())
        else:
            to_timestamp = context.at or Timestamp()

        enriched_diff = await diff_coordinator.get_diff(
            base_branch=base_branch,
            diff_branch=diff_branch,
            from_time=from_timestamp,
            to_time=to_timestamp,
            root_node_uuids=root_node_uuids,
            max_depth=max_depth,
            limit=limit,
            offset=offset,
        )

        full_fields = await extract_fields(info.field_nodes[0].selection_set)
        diff_tree = self.to_diff_tree(enriched_diff_root=enriched_diff)
        return self.to_graphql(fields=full_fields, diff_object=diff_tree)


DiffTreeQuery = Field(
    DiffTree,
    name=String(),
    resolver=DiffTreeResolver().resolve,
    branch=String(),
    from_time=DateTime(),
    to_time=DateTime(),
    root_node_uuids=List(String),
    max_depth=Int(),
    limit=Int(),
    offset=Int(),
)
