from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, List, Optional, Set

from infrahub.core import registry
from infrahub.core.schema import (
    MainSchemaTypes,
    SchemaAttributePath,
    SchemaAttributePathValue,
)
from infrahub.core.validators.uniqueness.index import UniquenessQueryResultsIndex
from infrahub.core.validators.uniqueness.model import (
    NodeUniquenessQueryRequest,
    QueryAttributePath,
    QueryRelationshipAttributePath,
)
from infrahub.core.validators.uniqueness.query import NodeUniqueAttributeConstraintQuery
from infrahub.exceptions import ValidationError

from .interface import NodeConstraintInterface

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.query import QueryResult
    from infrahub.core.relationship.model import RelationshipManager
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class NodeGroupedUniquenessConstraint(NodeConstraintInterface):
    def __init__(self, db: InfrahubDatabase, branch: Branch) -> None:
        self.db = db
        self.branch = branch
        self.schema_branch = registry.schema.get_schema_branch(branch.name)

    def _build_query_request(
        self,
        updated_node: Node,
        node_schema: MainSchemaTypes,
        path_groups: List[List[SchemaAttributePath]],
        filters: Optional[List[str]] = None,
    ) -> NodeUniquenessQueryRequest:
        query_request = NodeUniquenessQueryRequest(kind=node_schema.kind)
        for path_group in path_groups:
            include_in_query = not filters
            query_relationship_paths: Set[QueryRelationshipAttributePath] = set()
            query_attribute_paths: Set[QueryAttributePath] = set()
            for attribute_path in path_group:
                if attribute_path.related_schema and attribute_path.relationship_schema:
                    if filters and attribute_path.relationship_schema.name in filters:
                        include_in_query = True
                    query_relationship_paths.add(
                        QueryRelationshipAttributePath(
                            identifier=attribute_path.relationship_schema.get_identifier(),
                        )
                    )
                    continue
                if attribute_path.attribute_schema:
                    if filters and attribute_path.attribute_schema.name in filters:
                        include_in_query = True
                    attribute_name = attribute_path.attribute_schema.name
                    attribute_value = getattr(updated_node, attribute_name).value
                    query_attribute_paths.add(
                        QueryAttributePath(
                            attribute_name=attribute_name,
                            property_name=attribute_path.attribute_property_name or "value",
                            value=attribute_value,
                        )
                    )
            if include_in_query:
                query_request.relationship_attribute_paths |= query_relationship_paths
                query_request.unique_attribute_paths |= query_attribute_paths
        return query_request

    async def _get_node_attribute_path_values(
        self,
        updated_node: Node,
        path_group: List[SchemaAttributePath],
    ) -> List[SchemaAttributePathValue]:
        node_value_combination = []
        for schema_attribute_path in path_group:
            if schema_attribute_path.relationship_schema:
                relationship_name = schema_attribute_path.relationship_schema.name
                relationship_manager: RelationshipManager = getattr(updated_node, relationship_name)
                related_node = await relationship_manager.get_peer(db=self.db)
                related_node_id = related_node.get_id() if related_node else None
                node_value_combination.append(
                    SchemaAttributePathValue.from_schema_attribute_path(schema_attribute_path, value=related_node_id)
                )
            elif schema_attribute_path.attribute_schema:
                attribute_name = schema_attribute_path.attribute_schema.name
                attribute_field = getattr(updated_node, attribute_name)
                attribute_value = getattr(attribute_field, schema_attribute_path.attribute_property_name or "value")
                node_value_combination.append(
                    SchemaAttributePathValue.from_schema_attribute_path(schema_attribute_path, value=attribute_value)
                )
        return node_value_combination

    def _check_one_constraint_group(
        self, schema_attribute_path_values: List[SchemaAttributePathValue], results_index: UniquenessQueryResultsIndex
    ) -> None:
        # constraint cannot be violated if this node is missing any values
        if any((sapv.value is None for sapv in schema_attribute_path_values)):
            return

        matching_node_ids = results_index.get_node_ids_for_value_group(schema_attribute_path_values)
        if not matching_node_ids:
            return
        uniqueness_constraint_fields = []
        for sapv in schema_attribute_path_values:
            if sapv.relationship_schema:
                uniqueness_constraint_fields.append(sapv.relationship_schema.name)
            elif sapv.attribute_schema:
                uniqueness_constraint_fields.append(sapv.attribute_schema.name)
        uniqueness_constraint_string = "-".join(uniqueness_constraint_fields)
        error_msg = f"Violates uniqueness constraint '{uniqueness_constraint_string}'"
        errors = [ValidationError({field_name: error_msg}) for field_name in uniqueness_constraint_fields]
        raise ValidationError(errors)

    async def _check_results(
        self,
        updated_node: Node,
        path_groups: List[List[SchemaAttributePath]],
        query_results: Iterable[QueryResult],
    ) -> None:
        results_index = UniquenessQueryResultsIndex(
            query_results=query_results, exclude_node_ids={updated_node.get_id()}
        )
        for path_group in path_groups:
            schema_attribute_path_values = await self._get_node_attribute_path_values(
                updated_node=updated_node, path_group=path_group
            )
            self._check_one_constraint_group(
                schema_attribute_path_values=schema_attribute_path_values, results_index=results_index
            )

    async def _check_one_schema(
        self,
        node: Node,
        node_schema: MainSchemaTypes,
        at: Optional[Timestamp] = None,
        filters: Optional[List[str]] = None,
    ) -> None:
        path_groups = node_schema.get_unique_constraint_schema_attribute_paths()
        query_request = self._build_query_request(
            updated_node=node, node_schema=node_schema, path_groups=path_groups, filters=filters
        )
        query = await NodeUniqueAttributeConstraintQuery.init(
            db=self.db, branch=self.branch, at=at, query_request=query_request, min_count_required=0
        )
        await query.execute(db=self.db)
        await self._check_results(updated_node=node, path_groups=path_groups, query_results=query.get_results())

    async def check(self, node: Node, at: Optional[Timestamp] = None, filters: Optional[List[str]] = None) -> None:
        node_schema = node.get_schema()
        schemas_to_check: List[MainSchemaTypes] = [node_schema]
        if node_schema.inherit_from:
            for parent_schema_name in node_schema.inherit_from:
                parent_schema = self.schema_branch.get(name=parent_schema_name, duplicate=False)
                if parent_schema.uniqueness_constraints:
                    schemas_to_check.append(parent_schema)
        for schema in schemas_to_check:
            await self._check_one_schema(node=node, node_schema=schema, at=at, filters=filters)
