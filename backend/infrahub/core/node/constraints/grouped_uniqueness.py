from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.constants import NULL_VALUE
from infrahub.core.schema.basenode_schema import (
    UniquenessConstraintType,
    UniquenessConstraintViolation,
)
from infrahub.core.validators.uniqueness.model import (
    NodeUniquenessQueryRequestValued,
    QueryAttributePathValued,
    QueryRelationshipPathValued,
)
from infrahub.core.validators.uniqueness.query import UniquenessValidationQuery
from infrahub.exceptions import HFIDViolatedError, ValidationError

from .interface import NodeConstraintInterface

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.relationship.model import RelationshipManager
    from infrahub.core.schema import (
        MainSchemaTypes,
        SchemaAttributePath,
    )
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class NodeGroupedUniquenessConstraint(NodeConstraintInterface):
    def __init__(self, db: InfrahubDatabase, branch: Branch) -> None:
        self.db = db
        self.branch = branch
        self.schema_branch = registry.schema.get_schema_branch(branch.name)

    async def _get_unique_valued_paths(
        self,
        updated_node: Node,
        path_group: list[SchemaAttributePath],
        filters: list[str],
    ) -> list[QueryAttributePathValued | QueryRelationshipPathValued]:
        # if filters are provided, we need to check if the path group is relevant to the filters
        if filters:
            field_names: list[str] = []
            for schema_attribute_path in path_group:
                if schema_attribute_path.relationship_schema:
                    field_names.append(schema_attribute_path.relationship_schema.name)
                elif schema_attribute_path.attribute_schema:
                    field_names.append(schema_attribute_path.attribute_schema.name)

            if not set(field_names) & set(filters):
                return []

        valued_paths: list[QueryAttributePathValued | QueryRelationshipPathValued] = []
        for schema_attribute_path in path_group:
            if schema_attribute_path.relationship_schema:
                relationship_name = schema_attribute_path.relationship_schema.name
                relationship_manager: RelationshipManager = getattr(updated_node, relationship_name)
                related_node = await relationship_manager.get_peer(db=self.db)
                related_node_id = related_node.get_id() if related_node else None
                valued_paths.append(
                    QueryRelationshipPathValued(
                        relationship_schema=schema_attribute_path.relationship_schema,
                        peer_id=related_node_id,
                        attribute_name=None,
                        attribute_value=None,
                    )
                )
            elif schema_attribute_path.attribute_schema:
                attribute_name = schema_attribute_path.attribute_schema.name
                attribute_field = getattr(updated_node, attribute_name)
                attribute_value = getattr(attribute_field, schema_attribute_path.attribute_property_name or "value")
                if attribute_field.is_enum and attribute_value:
                    attribute_value = attribute_value.value
                elif attribute_value is None:
                    attribute_value = NULL_VALUE
                valued_paths.append(
                    QueryAttributePathValued(
                        attribute_name=attribute_name,
                        value=attribute_value,
                    )
                )
        return valued_paths

    async def _get_single_schema_violations(
        self,
        node: Node,
        node_schema: MainSchemaTypes,
        filters: list[str],
        at: Timestamp | None = None,
    ) -> list[UniquenessConstraintViolation]:
        schema_branch = self.db.schema.get_schema_branch(name=self.branch.name)

        uniqueness_constraint_paths = node_schema.get_unique_constraint_schema_attribute_paths(
            schema_branch=schema_branch
        )

        violations: list[UniquenessConstraintViolation] = []
        for uniqueness_constraint_path in uniqueness_constraint_paths:
            valued_paths = await self._get_unique_valued_paths(
                updated_node=node,
                path_group=uniqueness_constraint_path.attributes_paths,
                filters=filters,
            )

            if not valued_paths:
                continue

            # Create the valued query request for this constraint
            valued_query_request = NodeUniquenessQueryRequestValued(
                kind=node_schema.kind,
                unique_valued_paths=valued_paths,
            )

            # Execute the query
            query = await UniquenessValidationQuery.init(
                db=self.db,
                branch=self.branch,
                at=at,
                query_request=valued_query_request,
                node_ids_to_exclude=[node.get_id()],
            )
            await query.execute(db=self.db)

            # Get violation nodes from the query results
            violation_nodes = query.get_violation_nodes()
            if not violation_nodes:
                continue

            # Create violation object
            uniqueness_constraint_fields = []
            for valued_path in valued_paths:
                if isinstance(valued_path, QueryRelationshipPathValued):
                    uniqueness_constraint_fields.append(valued_path.relationship_schema.name)
                elif isinstance(valued_path, QueryAttributePathValued):
                    uniqueness_constraint_fields.append(valued_path.attribute_name)

            matching_node_ids = {node_id for node_id, _ in violation_nodes}
            if matching_node_ids:
                violations.append(
                    UniquenessConstraintViolation(
                        nodes_ids=matching_node_ids,
                        fields=uniqueness_constraint_fields,
                        typ=uniqueness_constraint_path.typ,
                    )
                )

        return violations

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

        violations: list[UniquenessConstraintViolation] = []

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
