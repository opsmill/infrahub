from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from infrahub.core import registry
from infrahub.core.constants import NULL_VALUE
from infrahub.core.schema import (
    MainSchemaTypes,
    SchemaAttributePath,
    SchemaAttributePathValue,
)
from infrahub.core.schema.basenode_schema import (
    SchemaUniquenessConstraintPath,
    UniquenessConstraintType,
    UniquenessConstraintViolation,
)
from infrahub.core.validators.uniqueness.index import UniquenessQueryResultsIndex
from infrahub.core.validators.uniqueness.model import (
    NodeUniquenessQueryRequest,
    QueryAttributePath,
    QueryRelationshipAttributePath,
)
from infrahub.core.validators.uniqueness.query import NodeUniqueAttributeConstraintQuery
from infrahub.exceptions import HFIDViolatedError, ValidationError

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

    async def _build_query_request(
        self,
        updated_node: Node,
        node_schema: MainSchemaTypes,
        uniqueness_constraint_paths: list[SchemaUniquenessConstraintPath],
        filters: list[str] | None = None,
    ) -> NodeUniquenessQueryRequest:
        query_request = NodeUniquenessQueryRequest(kind=node_schema.kind)
        for uniqueness_constraint_path in uniqueness_constraint_paths:
            include_in_query = not filters
            query_relationship_paths: set[QueryRelationshipAttributePath] = set()
            query_attribute_paths: set[QueryAttributePath] = set()
            for attribute_path in uniqueness_constraint_path.attributes_paths:
                if attribute_path.related_schema and attribute_path.relationship_schema:
                    if filters and attribute_path.relationship_schema.name in filters:
                        include_in_query = True

                    relationship_manager: RelationshipManager = getattr(
                        updated_node, attribute_path.relationship_schema.name
                    )
                    related_node = await relationship_manager.get_peer(db=self.db)
                    related_node_id = related_node.get_id() if related_node else None
                    query_relationship_paths.add(
                        QueryRelationshipAttributePath(
                            identifier=attribute_path.relationship_schema.get_identifier(),
                            value=related_node_id,
                        )
                    )
                    continue
                if attribute_path.attribute_schema:
                    if filters and attribute_path.attribute_schema.name in filters:
                        include_in_query = True
                    attribute_name = attribute_path.attribute_schema.name
                    attribute = getattr(updated_node, attribute_name)
                    if attribute.is_enum and attribute.value:
                        attribute_value = attribute.value.value
                    else:
                        attribute_value = attribute.value
                    if attribute_value is None:
                        attribute_value = NULL_VALUE
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
        path_group: list[SchemaAttributePath],
    ) -> list[SchemaAttributePathValue]:
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
                if attribute_field.is_enum and attribute_value:
                    attribute_value = attribute_value.value
                elif attribute_value is None:
                    attribute_value = NULL_VALUE
                node_value_combination.append(
                    SchemaAttributePathValue.from_schema_attribute_path(
                        schema_attribute_path,
                        value=attribute_value,
                    )
                )
        return node_value_combination

    async def _get_violations(
        self,
        updated_node: Node,
        uniqueness_constraint_paths: list[SchemaUniquenessConstraintPath],
        query_results: Iterable[QueryResult],
    ) -> list[UniquenessConstraintViolation]:
        results_index = UniquenessQueryResultsIndex(
            query_results=query_results, exclude_node_ids={updated_node.get_id()}
        )
        violations = []
        for uniqueness_constraint_path in uniqueness_constraint_paths:
            # path_group = one constraint (that can contain multiple items)
            schema_attribute_path_values = await self._get_node_attribute_path_values(
                updated_node=updated_node, path_group=uniqueness_constraint_path.attributes_paths
            )

            # constraint cannot be violated if this node is missing any values
            if any(sapv.value is None for sapv in schema_attribute_path_values):
                continue

            matching_node_ids = results_index.get_node_ids_for_value_group(schema_attribute_path_values)
            if not matching_node_ids:
                continue

            uniqueness_constraint_fields = []
            for sapv in schema_attribute_path_values:
                if sapv.relationship_schema:
                    uniqueness_constraint_fields.append(sapv.relationship_schema.name)
                elif sapv.attribute_schema:
                    uniqueness_constraint_fields.append(sapv.attribute_schema.name)

            violations.append(
                UniquenessConstraintViolation(
                    nodes_ids=matching_node_ids,
                    fields=uniqueness_constraint_fields,
                    typ=uniqueness_constraint_path.typ,
                )
            )

        return violations

    async def _get_single_schema_violations(
        self,
        node: Node,
        node_schema: MainSchemaTypes,
        at: Timestamp | None = None,
        filters: list[str] | None = None,
    ) -> list[UniquenessConstraintViolation]:
        schema_branch = self.db.schema.get_schema_branch(name=self.branch.name)

        uniqueness_constraint_paths = node_schema.get_unique_constraint_schema_attribute_paths(
            schema_branch=schema_branch
        )
        query_request = await self._build_query_request(
            updated_node=node,
            node_schema=node_schema,
            uniqueness_constraint_paths=uniqueness_constraint_paths,
            filters=filters,
        )
        if not query_request:
            return []

        query = await NodeUniqueAttributeConstraintQuery.init(
            db=self.db, branch=self.branch, at=at, query_request=query_request, min_count_required=0
        )
        await query.execute(db=self.db)
        return await self._get_violations(
            updated_node=node,
            uniqueness_constraint_paths=uniqueness_constraint_paths,
            query_results=query.get_results(),
        )

    async def check(self, node: Node, at: Timestamp | None = None, filters: list[str] | None = None) -> None:
        def _frozen_constraints(schema: MainSchemaTypes) -> frozenset[frozenset[str]]:
            if not schema.uniqueness_constraints:
                return frozenset()
            return frozenset(frozenset(uc) for uc in schema.uniqueness_constraints)

        node_schema = node.get_schema()
        include_node_schema = True
        frozen_node_constraints = _frozen_constraints(node_schema)
        schemas_to_check: list[MainSchemaTypes] = []
        if node_schema.inherit_from:
            for parent_schema_name in node_schema.inherit_from:
                parent_schema = self.schema_branch.get(name=parent_schema_name, duplicate=False)
                if not parent_schema.uniqueness_constraints:
                    continue
                schemas_to_check.append(parent_schema)
                frozen_parent_constraints = _frozen_constraints(parent_schema)
                if frozen_node_constraints <= frozen_parent_constraints:
                    include_node_schema = False

        if include_node_schema:
            schemas_to_check.append(node_schema)

        violations = []
        for schema in schemas_to_check:
            schema_filters = list(filters) if filters is not None else []
            for attr_schema in schema.attributes:
                if attr_schema.optional and attr_schema.unique and attr_schema.name not in schema_filters:
                    schema_filters.append(attr_schema.name)

            schema_violations = await self._get_single_schema_violations(
                node=node, node_schema=schema, at=at, filters=schema_filters
            )
            violations.extend(schema_violations)

        hfid_violations = [violation for violation in violations if violation.typ == UniquenessConstraintType.HFID]
        hfid_violation = hfid_violations[0] if len(hfid_violations) > 0 else None

        # If there are both a hfid violation and another one, in case of an upsert, we still want to update the node in case other violations are:
        # - either on subset fields of hfid, which would be necessarily violated too
        # - or on uniqueness constraints with a matching node id being the id of the hfid violation

        for violation in violations:
            if violation.typ == UniquenessConstraintType.HFID:
                continue

            if hfid_violation:
                if violation.typ == UniquenessConstraintType.SUBSET_OF_HFID:
                    continue

                if (
                    violation.typ == UniquenessConstraintType.STANDARD
                    and len(violation.nodes_ids) == 1
                    and next(iter(violation.nodes_ids)) == next(iter(hfid_violation.nodes_ids))
                ):
                    continue

            error_msg = f"Violates uniqueness constraint '{'-'.join(violation.fields)}'"
            raise ValidationError(error_msg)

        if hfid_violation:
            error_msg = f"Violates uniqueness constraint '{'-'.join(hfid_violation.fields)}'"
            raise HFIDViolatedError(error_msg, matching_nodes_ids=hfid_violation.nodes_ids)
