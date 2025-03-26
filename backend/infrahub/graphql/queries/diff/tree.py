from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Argument, Boolean, DateTime, Field, InputObjectType, Int, List, NonNull, ObjectType, String
from graphene import Enum as GrapheneEnum
from infrahub_sdk.utils import extract_fields

from infrahub.core import registry
from infrahub.core.constants import DiffAction, RelationshipCardinality
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.model.path import NameTrackingId
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.query.diff import DiffCountChanges
from infrahub.core.timestamp import Timestamp
from infrahub.dependencies.registry import get_component_registry
from infrahub.graphql.enums import ConflictSelection as GraphQLConflictSelection

if TYPE_CHECKING:
    from datetime import datetime

    from graphql import GraphQLResolveInfo

    from infrahub.core.diff.model.path import (
        EnrichedDiffAttribute,
        EnrichedDiffConflict,
        EnrichedDiffNode,
        EnrichedDiffProperty,
        EnrichedDiffRelationship,
        EnrichedDiffRoot,
        EnrichedDiffSingleRelationship,
    )
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.initialization import GraphqlContext

GrapheneDiffActionEnum = GrapheneEnum.from_enum(DiffAction)
GrapheneCardinalityEnum = GrapheneEnum.from_enum(RelationshipCardinality)


class ConflictDetails(ObjectType):
    uuid = String(required=True)
    base_branch_action = Field(GrapheneDiffActionEnum, required=True)
    base_branch_value = String()
    base_branch_changed_at = DateTime(required=True)
    base_branch_label = String()
    diff_branch_action = Field(GrapheneDiffActionEnum, required=True)
    diff_branch_value = String()
    diff_branch_changed_at = DateTime(required=True)
    diff_branch_label = String()
    selected_branch = Field(GraphQLConflictSelection)
    resolvable = Boolean()


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
    previous_label = String(required=False)
    new_label = String(required=False)
    status = Field(GrapheneDiffActionEnum, required=True)
    path_identifier = String(required=True)
    conflict = Field(ConflictDetails, required=False)


class DiffAttribute(DiffSummaryCounts):
    name = String(required=True)
    last_changed_at = DateTime(required=True)
    status = Field(GrapheneDiffActionEnum, required=True)
    path_identifier = String(required=True)
    properties = List(NonNull(DiffProperty))
    contains_conflict = Boolean(required=True)
    conflict = Field(ConflictDetails, required=False)


class DiffSingleRelationship(DiffSummaryCounts):
    last_changed_at = DateTime(required=False)
    status = Field(GrapheneDiffActionEnum, required=True)
    peer_id = String(required=True)
    peer_label = String(required=False)
    path_identifier = String(required=True)
    contains_conflict = Boolean(required=True)
    conflict = Field(ConflictDetails, required=False)
    properties = List(NonNull(DiffProperty))


class DiffRelationship(DiffSummaryCounts):
    name = String(required=True)
    label = String(required=False)
    last_changed_at = DateTime(required=False)
    cardinality = Field(GrapheneCardinalityEnum, required=True)
    status = Field(GrapheneDiffActionEnum, required=True)
    path_identifier = String(required=True)
    elements = List(NonNull(DiffSingleRelationship), required=True)
    contains_conflict = Boolean(required=True)


class DiffNodeParent(ObjectType):
    uuid = String(required=True)
    kind = String(required=False)
    relationship_name = String(required=False)


class DiffNode(DiffSummaryCounts):
    uuid = String(required=True)
    kind = String(required=True)
    label = String(required=True)
    status = Field(GrapheneDiffActionEnum, required=True)
    path_identifier = String(required=True)
    conflict = Field(ConflictDetails, required=False)
    contains_conflict = Boolean(required=True)
    last_changed_at = DateTime(required=False)
    parent = Field(DiffNodeParent, required=False)
    attributes = List(NonNull(DiffAttribute), required=True)
    relationships = List(NonNull(DiffRelationship), required=True)


class DiffTree(DiffSummaryCounts):
    base_branch = String(required=True)
    diff_branch = String(required=True)
    from_time = DateTime(required=True)
    to_time = DateTime(required=True)
    num_untracked_base_changes = Int(required=False)
    num_untracked_diff_changes = Int(required=False)
    name = String(required=False)
    nodes = List(NonNull(DiffNode))


class DiffTreeSummary(DiffSummaryCounts):
    base_branch = String(required=True)
    diff_branch = String(required=True)
    from_time = DateTime(required=True)
    to_time = DateTime(required=True)
    num_unchanged = Int(required=False)
    num_untracked_base_changes = Int(required=False)
    num_untracked_diff_changes = Int(required=False)


class DiffTreeResolver:
    async def to_diff_tree(
        self, enriched_diff_root: EnrichedDiffRoot, graphql_context: GraphqlContext | None = None
    ) -> DiffTree:
        all_nodes = list(enriched_diff_root.nodes)
        tree_nodes = [self.to_diff_node(enriched_node=e_node, graphql_context=graphql_context) for e_node in all_nodes]
        name = None
        if enriched_diff_root.tracking_id and isinstance(enriched_diff_root.tracking_id, NameTrackingId):
            name = enriched_diff_root.tracking_id.name
        return DiffTree(
            base_branch=enriched_diff_root.base_branch_name,
            diff_branch=enriched_diff_root.diff_branch_name,
            from_time=await enriched_diff_root.from_time.to_graphql(),
            to_time=await enriched_diff_root.to_time.to_graphql(),
            name=name,
            nodes=tree_nodes,
            num_added=enriched_diff_root.num_added,
            num_updated=enriched_diff_root.num_updated,
            num_removed=enriched_diff_root.num_removed,
            num_conflicts=enriched_diff_root.num_conflicts,
        )

    def to_diff_node(self, enriched_node: EnrichedDiffNode, graphql_context: GraphqlContext | None = None) -> DiffNode:
        diff_attributes = [
            self.to_diff_attribute(enriched_attribute=e_attr, graphql_context=graphql_context)
            for e_attr in enriched_node.attributes
        ]
        diff_relationships = [
            self.to_diff_relationship(enriched_relationship=e_rel, graphql_context=graphql_context)
            for e_rel in enriched_node.relationships
            if e_rel.include_in_response
        ]
        conflict = None
        if enriched_node.conflict:
            conflict = self.to_diff_conflict(enriched_conflict=enriched_node.conflict, graphql_context=graphql_context)

        parent = None
        if parent_info := enriched_node.get_parent_info(graphql_context=graphql_context):
            parent = DiffNodeParent(
                uuid=parent_info.node.uuid,
                kind=parent_info.node.kind,
                relationship_name=parent_info.relationship_name,
            )

        return DiffNode(
            uuid=enriched_node.uuid,
            kind=enriched_node.kind,
            label=enriched_node.label,
            status=enriched_node.action,
            parent=parent,
            last_changed_at=enriched_node.changed_at.to_datetime() if enriched_node.changed_at else None,
            path_identifier=enriched_node.path_identifier,
            attributes=diff_attributes,
            relationships=diff_relationships,
            contains_conflict=enriched_node.contains_conflict,
            conflict=conflict,
            num_added=enriched_node.num_added,
            num_updated=enriched_node.num_updated,
            num_removed=enriched_node.num_removed,
            num_conflicts=enriched_node.num_conflicts,
        )

    def to_diff_attribute(
        self, enriched_attribute: EnrichedDiffAttribute, graphql_context: GraphqlContext | None = None
    ) -> DiffAttribute:
        diff_properties = [
            self.to_diff_property(enriched_property=e_prop, graphql_context=graphql_context)
            for e_prop in enriched_attribute.properties
        ]
        conflict = None
        for diff_prop in diff_properties:
            if diff_prop.property_type == DatabaseEdgeType.HAS_VALUE.value and diff_prop.conflict:
                conflict = diff_prop.conflict
                diff_prop.conflict = None
        return DiffAttribute(
            name=enriched_attribute.name,
            last_changed_at=enriched_attribute.changed_at.to_datetime(),
            status=enriched_attribute.action,
            path_identifier=enriched_attribute.path_identifier,
            properties=diff_properties,
            contains_conflict=enriched_attribute.contains_conflict,
            conflict=conflict,
            num_added=enriched_attribute.num_added,
            num_updated=enriched_attribute.num_updated,
            num_removed=enriched_attribute.num_removed,
            num_conflicts=enriched_attribute.num_conflicts,
        )

    def to_diff_relationship(
        self, enriched_relationship: EnrichedDiffRelationship, graphql_context: GraphqlContext | None = None
    ) -> DiffRelationship:
        diff_elements = [
            self.to_diff_relationship_element(enriched_element=element, graphql_context=graphql_context)
            for element in enriched_relationship.relationships
        ]
        return DiffRelationship(
            name=enriched_relationship.name,
            label=enriched_relationship.label,
            last_changed_at=enriched_relationship.changed_at.to_datetime()
            if enriched_relationship.changed_at
            else None,
            status=enriched_relationship.action,
            cardinality=enriched_relationship.cardinality,
            path_identifier=enriched_relationship.path_identifier,
            elements=diff_elements,
            contains_conflict=enriched_relationship.contains_conflict,
            num_added=enriched_relationship.num_added,
            num_updated=enriched_relationship.num_updated,
            num_removed=enriched_relationship.num_removed,
            num_conflicts=enriched_relationship.num_conflicts,
        )

    def to_diff_relationship_element(
        self, enriched_element: EnrichedDiffSingleRelationship, graphql_context: GraphqlContext | None = None
    ) -> DiffSingleRelationship:
        diff_properties = [self.to_diff_property(e_prop) for e_prop in enriched_element.properties]
        conflict = None
        if enriched_element.conflict:
            conflict = self.to_diff_conflict(
                enriched_conflict=enriched_element.conflict, graphql_context=graphql_context
            )
        return DiffSingleRelationship(
            last_changed_at=enriched_element.changed_at.to_datetime(),
            status=enriched_element.action,
            peer_id=enriched_element.peer_id,
            peer_label=enriched_element.peer_label,
            path_identifier=enriched_element.path_identifier,
            conflict=conflict,
            properties=diff_properties,
            contains_conflict=enriched_element.contains_conflict,
            num_added=enriched_element.num_added,
            num_updated=enriched_element.num_updated,
            num_removed=enriched_element.num_removed,
            num_conflicts=enriched_element.num_conflicts,
        )

    def to_diff_property(
        self, enriched_property: EnrichedDiffProperty, graphql_context: GraphqlContext | None = None
    ) -> DiffProperty:
        conflict = None
        if enriched_property.conflict:
            conflict = self.to_diff_conflict(
                enriched_conflict=enriched_property.conflict, graphql_context=graphql_context
            )
        return DiffProperty(
            property_type=enriched_property.property_type.value,
            last_changed_at=enriched_property.changed_at.to_datetime(),
            previous_value=enriched_property.previous_value,
            new_value=enriched_property.new_value,
            previous_label=enriched_property.previous_label,
            new_label=enriched_property.new_label,
            status=enriched_property.action,
            path_identifier=enriched_property.path_identifier,
            conflict=conflict,
        )

    def to_diff_conflict(
        self,
        enriched_conflict: EnrichedDiffConflict,
        graphql_context: GraphqlContext | None = None,  # noqa: ARG002
    ) -> ConflictDetails:
        return ConflictDetails(
            uuid=enriched_conflict.uuid,
            base_branch_action=enriched_conflict.base_branch_action,
            base_branch_value=enriched_conflict.base_branch_value,
            base_branch_changed_at=enriched_conflict.base_branch_changed_at.to_datetime()
            if enriched_conflict.base_branch_changed_at
            else None,
            base_branch_label=enriched_conflict.base_branch_label,
            diff_branch_action=enriched_conflict.diff_branch_action,
            diff_branch_value=enriched_conflict.diff_branch_value,
            diff_branch_changed_at=enriched_conflict.diff_branch_changed_at.to_datetime()
            if enriched_conflict.diff_branch_changed_at
            else None,
            diff_branch_label=enriched_conflict.diff_branch_label,
            selected_branch=enriched_conflict.selected_branch.value if enriched_conflict.selected_branch else None,
            resolvable=enriched_conflict.resolvable,
        )

    async def to_graphql(
        self, fields: dict[str, dict], diff_object: Any | None
    ) -> list[dict[str, Any]] | dict[str, Any] | None:
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
                    element_response[field_name] = await self.to_graphql(
                        sub_fields, getattr(diff_object_element, field_name)
                    )
                else:
                    continue
            response_list.append(element_response)
        if list_response:
            return response_list
        return response_list[0]

    async def _add_untracked_fields(
        self,
        db: InfrahubDatabase,
        diff_response: DiffTreeSummary | DiffTree,
        from_time: Timestamp,
        base_branch_name: str | None = None,
        diff_branch_name: str | None = None,
    ) -> None:
        if not (base_branch_name or diff_branch_name):
            return
        branch_names = []
        if base_branch_name:
            branch_names.append(base_branch_name)
        if diff_branch_name:
            branch_names.append(diff_branch_name)
        query = await DiffCountChanges.init(db=db, branch_names=branch_names, diff_from=from_time, diff_to=Timestamp())
        await query.execute(db=db)
        branch_change_map = query.get_num_changes_by_branch()
        if base_branch_name:
            diff_response.num_untracked_base_changes = branch_change_map.get(base_branch_name, 0)
        if diff_branch_name:
            diff_response.num_untracked_diff_changes = branch_change_map.get(diff_branch_name, 0)

    async def resolve(
        self,
        root: dict,  # noqa: ARG002
        info: GraphQLResolveInfo,
        branch: str | None = None,
        name: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        filters: dict | None = None,
        include_parents: bool = True,
        root_node_uuids: list[str] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict[str, Any]] | dict[str, Any] | None:
        component_registry = get_component_registry()
        graphql_context: GraphqlContext = info.context
        base_branch = await registry.get_branch(db=graphql_context.db, branch=registry.default_branch)
        diff_branch = await registry.get_branch(db=graphql_context.db, branch=branch)
        diff_repo = await component_registry.get_component(DiffRepository, db=graphql_context.db, branch=diff_branch)
        branch_start_timestamp = Timestamp(diff_branch.get_branched_from())
        if from_time:
            from_timestamp = Timestamp(from_time.isoformat())
        else:
            from_timestamp = branch_start_timestamp
        if to_time:
            to_timestamp = Timestamp(to_time.isoformat())
        else:
            to_timestamp = graphql_context.at or Timestamp()

        # Convert filters to dict and merge root_node_uuids for compatibility
        filters_dict = dict(filters or {})
        if root_node_uuids and "ids" in filters_dict and isinstance(filters_dict["ids"], list):
            filters_dict["ids"].extend(root_node_uuids)
        elif root_node_uuids:
            filters_dict["ids"] = root_node_uuids

        enriched_diffs = await diff_repo.get(
            base_branch_name=base_branch.name,
            diff_branch_names=[diff_branch.name],
            from_time=from_timestamp,
            to_time=to_timestamp,
            filters=filters_dict,
            include_parents=include_parents,
            limit=limit,
            offset=offset,
            tracking_id=NameTrackingId(name) if name else None,
            include_empty=True,
        )
        if not enriched_diffs:
            return None
        if len(enriched_diffs) > 0:
            # take the one with the longest duration that covers multiple branches
            enriched_diff = sorted(
                enriched_diffs,
                key=lambda d: (
                    d.base_branch_name != d.diff_branch_name,
                    d.to_time.to_datetime() - d.from_time.to_datetime(),
                ),
                reverse=True,
            )[0]
        else:
            enriched_diff = enriched_diffs[0]

        full_fields = await extract_fields(info.field_nodes[0].selection_set)
        diff_tree = await self.to_diff_tree(enriched_diff_root=enriched_diff, graphql_context=graphql_context)
        need_base_changes = "num_untracked_base_changes" in full_fields
        need_branch_changes = "num_untracked_diff_changes" in full_fields
        if need_base_changes or need_branch_changes:
            await self._add_untracked_fields(
                db=graphql_context.db,
                diff_response=diff_tree,
                from_time=enriched_diff.to_time,
                base_branch_name=base_branch.name if need_base_changes else None,
                diff_branch_name=diff_branch.name if need_branch_changes else None,
            )
        return await self.to_graphql(fields=full_fields, diff_object=diff_tree)

    async def summary(
        self,
        root: dict,  # noqa: ARG002
        info: GraphQLResolveInfo,
        branch: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        filters: dict | None = None,
    ) -> list[dict[str, Any]] | dict[str, Any] | None:
        component_registry = get_component_registry()
        graphql_context: GraphqlContext = info.context
        base_branch = await registry.get_branch(db=graphql_context.db, branch=registry.default_branch)
        diff_branch = await registry.get_branch(db=graphql_context.db, branch=branch)
        diff_repo = await component_registry.get_component(DiffRepository, db=graphql_context.db, branch=diff_branch)
        branch_start_timestamp = Timestamp(diff_branch.get_branched_from())
        if from_time:
            from_timestamp = Timestamp(from_time.isoformat())
        else:
            from_timestamp = branch_start_timestamp
        if to_time:
            to_timestamp = Timestamp(to_time.isoformat())
        else:
            to_timestamp = graphql_context.at or Timestamp()

        filters_dict = dict(filters or {})

        summary = await diff_repo.summary(
            base_branch_name=base_branch.name,
            diff_branch_names=[diff_branch.name],
            from_time=from_timestamp,
            to_time=to_timestamp,
            filters=filters_dict,
        )
        if summary is None:
            return None

        diff_tree_summary = DiffTreeSummary(
            base_branch=base_branch.name,
            diff_branch=diff_branch.name,
            from_time=summary.from_time.to_datetime(),
            to_time=summary.to_time.to_datetime(),
            **summary.model_dump(exclude={"from_time", "to_time"}),
        )
        full_fields = await extract_fields(info.field_nodes[0].selection_set)
        need_base_changes = "num_untracked_base_changes" in full_fields
        need_branch_changes = "num_untracked_diff_changes" in full_fields
        if need_base_changes or need_branch_changes:
            await self._add_untracked_fields(
                db=graphql_context.db,
                diff_response=diff_tree_summary,
                from_time=summary.to_time,
                base_branch_name=base_branch.name if need_base_changes else None,
                diff_branch_name=diff_branch.name if need_branch_changes else None,
            )
        return diff_tree_summary


class IncExclFilterOptions(InputObjectType):
    includes = List(String)
    excludes = List(String)


class IncExclFilterStatusOptions(InputObjectType):
    includes = List(GrapheneDiffActionEnum)
    excludes = List(GrapheneDiffActionEnum)


class DiffTreeQueryFilters(InputObjectType):
    ids = List(String)
    status = IncExclFilterStatusOptions()
    kind = IncExclFilterOptions()
    namespace = IncExclFilterOptions()


DiffTreeQuery = Field(
    DiffTree,
    name=String(),
    branch=String(),
    from_time=DateTime(),
    to_time=DateTime(),
    root_node_uuids=Argument(List(String), deprecation_reason="replaced by filters"),
    include_parents=Boolean(),
    filters=DiffTreeQueryFilters(),
    limit=Int(),
    offset=Int(),
    resolver=DiffTreeResolver().resolve,
    required=False,
)

DiffTreeSummaryQuery = Field(
    DiffTreeSummary,
    name=String(),
    branch=String(),
    from_time=DateTime(),
    to_time=DateTime(),
    filters=DiffTreeQueryFilters(),
    resolver=DiffTreeResolver().summary,
    required=False,
)
