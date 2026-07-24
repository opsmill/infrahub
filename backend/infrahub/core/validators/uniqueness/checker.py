from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from infrahub.core.constants import PathType
from infrahub.core.path import DataPath, GroupedDataPaths
from infrahub.core.schema import AttributeSchema, MainSchemaTypes, RelationshipSchema
from infrahub.core.validators.uniqueness.index import UniquenessQueryResultsIndex
from infrahub.utilities.chunks import chunked

from ..enum import ConstraintIdentifier
from ..interface import ConstraintCheckerInterface
from .model import (
    NodeUniquenessQueryRequest,
    NonUniqueAttribute,
    NonUniqueNode,
    NonUniqueRelatedAttribute,
    QueryAttributePath,
    QueryRelationshipAttributePath,
)
from .query import NodeUniqueAttributeConstraintQuery, TargetedUniquenessValidationQuery

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.query import QueryResult
    from infrahub.core.schema.basenode_schema import SchemaAttributePath
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

    from ..model import SchemaConstraintValidatorRequest
    from .query import TargetedUniquenessViolation


def get_attribute_path_from_string(
    path: str, schema: MainSchemaTypes
) -> tuple[AttributeSchema | RelationshipSchema, str | None]:
    if "__" in path:
        name, property_name = path.split("__")
    else:
        name, property_name = path, None
    attribute_schema = schema.get_attribute_or_none(name=name)
    relationship_schema = schema.get_relationship_or_none(name=name)
    if attribute_schema:
        return attribute_schema, property_name
    if relationship_schema:
        return relationship_schema, property_name
    raise ValueError(f"{path} is not valid on {schema.kind}")


class UniquenessChecker(ConstraintCheckerInterface):
    def __init__(
        self,
        db: InfrahubDatabase,
        max_concurrent_execution: int = 5,
        # default to 500 as we commonly do with CALL IN TRANSACTIONS OF 500 ROWS in cypher
        query_batch_size: int = 500,
    ) -> None:
        self.db = db
        self.semaphore = asyncio.Semaphore(max_concurrent_execution)
        self.query_batch_size = query_batch_size

    @property
    def name(self) -> str:
        return ConstraintIdentifier.NODE_UNIQUENESS_CONSTRAINTS_UPDATE.value

    def supports(self, request: SchemaConstraintValidatorRequest) -> bool:
        return request.constraint_name == self.name

    async def check(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]:
        if request.node_uuids is None or not self._supports_targeted(
            schema=request.node_schema, schema_branch=request.schema_branch
        ):
            non_unique_nodes = await self.check_one_schema(
                schema=request.node_schema, branch=request.branch, schema_branch=request.schema_branch
            )
            grouped_data_paths = GroupedDataPaths()
            for non_unique_node in non_unique_nodes:
                self.generate_data_paths(non_unique_node, grouped_data_paths)
            return [grouped_data_paths]

        return [
            await self._check_targeted(
                schema=request.node_schema,
                node_uuids=request.node_uuids,
                branch=request.branch,
                schema_branch=request.schema_branch,
            )
        ]

    def _supports_targeted(self, schema: MainSchemaTypes, schema_branch: SchemaBranch) -> bool:
        """Whether every uniqueness constraint of the schema can be checked by the targeted query.

        The targeted query compares node attributes by value and cardinality-one relationships by
        peer id, but cannot read an attribute of a related peer (a constraint element such as
        "owner__name"). A schema with any such element falls back to full-population validation,
        which does support it, rather than being scoped to the changed nodes.
        """
        for constraint_path in schema.get_unique_constraint_schema_attribute_paths(schema_branch=schema_branch):
            for element in constraint_path.attributes_paths:
                if element.relationship_schema is not None and element.attribute_schema is not None:
                    return False
        return True

    async def _check_targeted(
        self,
        schema: MainSchemaTypes,
        node_uuids: list[str],
        branch: Branch,
        schema_branch: SchemaBranch,
    ) -> GroupedDataPaths:
        """Validate uniqueness for only the changed nodes, one batched query per constraint group.

        Each query resolves the changed nodes' current constraint values and probes the whole
        population for other nodes sharing the full value tuple, so a collision with an untouched
        peer still surfaces. Only the changed nodes are queried, so the work is bounded by the size
        of the change rather than the kind's population, and the changed set is paged so a very
        large change does not travel in a single query.

        All queries run in one read-only session so reads route to a replica and the session is
        opened once for the whole change rather than per query.
        """
        constraint_paths = schema.get_unique_constraint_schema_attribute_paths(schema_branch=schema_branch)

        grouped_data_paths = GroupedDataPaths()
        if not constraint_paths:
            return grouped_data_paths

        seen_data_paths: set[DataPath] = set()
        async with self.db.start_session(read_only=True) as session_db:
            for constraint_path in constraint_paths:
                constraint_elements = constraint_path.attributes_paths
                for window in chunked(node_uuids, self.query_batch_size):
                    data_paths = await self._query_group_violations(
                        session_db=session_db,
                        schema=schema,
                        branch=branch,
                        constraint_elements=constraint_elements,
                        node_uuids=window,
                    )
                    for data_path in data_paths:
                        if data_path in seen_data_paths:
                            continue
                        seen_data_paths.add(data_path)
                        grouped_data_paths.add_data_path(
                            data_path, grouping_key=f"{schema.kind}/{data_path.field_name}/{data_path.value}"
                        )
        return grouped_data_paths

    async def _query_group_violations(
        self,
        session_db: InfrahubDatabase,
        schema: MainSchemaTypes,
        branch: Branch,
        constraint_elements: list[SchemaAttributePath],
        node_uuids: list[str],
    ) -> list[DataPath]:
        """Run one constraint group's targeted query for a window of changed nodes and expand it."""
        query = await TargetedUniquenessValidationQuery.init(
            db=session_db,
            branch=branch,
            kind=schema.kind,
            constraint_elements=constraint_elements,
            node_uuids=node_uuids,
        )
        await query.execute(db=session_db)

        data_paths: list[DataPath] = []
        for violation in query.get_data():
            data_paths.extend(
                self._violation_to_data_paths(
                    schema=schema,
                    constraint_elements=constraint_elements,
                    violation=violation,
                    branch_name=branch.name,
                )
            )
        return data_paths

    def _violation_to_data_paths(
        self,
        schema: MainSchemaTypes,
        constraint_elements: list[SchemaAttributePath],
        violation: TargetedUniquenessViolation,
        branch_name: str,
    ) -> list[DataPath]:
        """Expand one violation into a data path per involved node and constraint element.

        The changed node and every partner share the full value tuple, so each element's value is
        emitted for the changed node and all its partners. A relationship element carries the shared
        peer's id; an attribute element carries the shared attribute value.
        """
        involved_node_ids = [violation.changed_uuid, *violation.partner_uuids]
        data_paths: list[DataPath] = []
        for element, value in zip(constraint_elements, violation.element_values, strict=True):
            if element.relationship_schema is not None:
                field_name: str | None = element.relationship_schema.name
                property_name = "id"
                path_type = PathType.RELATIONSHIP_ONE
                peer_id: str | None = value
                path_value: str | None = value
            else:
                field_name = element.active_attribute_schema.name
                property_name = "value"
                path_type = PathType.ATTRIBUTE
                peer_id = None
                # value is always a str
                path_value = None if value is None else str(value)
            for node_id in involved_node_ids:
                data_paths.append(
                    DataPath(
                        branch=branch_name,
                        path_type=path_type,
                        node_id=node_id,
                        kind=schema.kind,
                        field_name=field_name,
                        property_name=property_name,
                        value=path_value,
                        peer_id=peer_id,
                    )
                )
        return data_paths

    async def build_query_request(self, schema: MainSchemaTypes) -> NodeUniquenessQueryRequest:
        unique_attr_paths = {
            QueryAttributePath(attribute_name=attr_schema.name, attribute_kind=attr_schema.kind, property_name="value")
            for attr_schema in schema.unique_attributes
        }
        relationship_attr_paths = set()

        if not schema.uniqueness_constraints:
            return NodeUniquenessQueryRequest(
                kind=schema.kind,
                unique_attribute_paths=unique_attr_paths,
                relationship_attribute_paths=set(),
            )

        for uniqueness_constraint in schema.uniqueness_constraints:
            for path in uniqueness_constraint:
                sub_schema, property_name = get_attribute_path_from_string(path, schema)
                if isinstance(sub_schema, AttributeSchema):
                    unique_attr_paths.add(
                        QueryAttributePath(
                            attribute_name=sub_schema.name, attribute_kind=sub_schema.kind, property_name=property_name
                        )
                    )
                elif isinstance(sub_schema, RelationshipSchema):
                    relationship_attr_paths.add(
                        QueryRelationshipAttributePath(
                            identifier=sub_schema.get_identifier(), attribute_name=property_name
                        )
                    )

        return NodeUniquenessQueryRequest(
            kind=schema.kind,
            unique_attribute_paths=unique_attr_paths,
            relationship_attribute_paths=relationship_attr_paths,
        )

    async def check_one_schema(
        self,
        schema: MainSchemaTypes,
        branch: Branch,
        schema_branch: SchemaBranch,
    ) -> list[NonUniqueNode]:
        query_request = await self.build_query_request(schema)

        if not query_request:
            return []

        query = await NodeUniqueAttributeConstraintQuery.init(db=self.db, branch=branch, query_request=query_request)
        async with self.semaphore:
            async with self.db.start_session(read_only=True) as db:
                query_results = await query.execute(db=db)

        return await self._parse_results(
            schema=schema, query_results=query_results.results, schema_branch=schema_branch
        )

    async def _parse_results(
        self, schema: MainSchemaTypes, query_results: list[QueryResult], schema_branch: SchemaBranch
    ) -> list[NonUniqueNode]:
        relationship_schema_by_identifier = {rel.identifier: rel for rel in schema.relationships}
        all_non_unique_nodes: list[NonUniqueNode] = []
        results_index = UniquenessQueryResultsIndex(query_results=query_results)

        uniqueness_constraint_paths = schema.get_unique_constraint_schema_attribute_paths(schema_branch=schema_branch)
        for uniqueness_constraint_path in uniqueness_constraint_paths:
            non_unique_nodes_by_id: dict[str, NonUniqueNode] = {}
            constraint_group_relationship_identifiers = [
                schema_attribute_path.relationship_schema.get_identifier()
                for schema_attribute_path in uniqueness_constraint_path.attributes_paths
                if schema_attribute_path.relationship_schema
            ]
            constraint_group_attribute_names = [
                schema_attribute_path.attribute_schema.name
                for schema_attribute_path in uniqueness_constraint_path.attributes_paths
                if schema_attribute_path.attribute_schema
            ]
            node_ids_in_violation = results_index.get_node_ids_for_path_group(
                path_group=uniqueness_constraint_path.attributes_paths
            )
            for result in query_results:
                node_id = str(result.get("node_id"))
                if node_id not in node_ids_in_violation:
                    continue
                if node_id not in non_unique_nodes_by_id:
                    non_unique_nodes_by_id[node_id] = NonUniqueNode(node_schema=schema, node_id=node_id)
                non_unique_node = non_unique_nodes_by_id[node_id]

                relationship_identifier = result.get("relationship_identifier")
                attribute_name = str(result.get("attr_name"))
                attribute_value = str(result.get("attr_value"))
                deepest_branch_name = str(result.get("deepest_branch_name"))
                if relationship_identifier:
                    if relationship_identifier not in constraint_group_relationship_identifiers:
                        continue
                    relationship_schema = relationship_schema_by_identifier[str(relationship_identifier)]
                    non_unique_node.non_unique_related_attributes.append(
                        NonUniqueRelatedAttribute(
                            relationship=relationship_schema,
                            attribute_name=attribute_name,
                            attribute_value=attribute_value,
                            deepest_branch_name=deepest_branch_name,
                        )
                    )
                    continue
                if not attribute_name:
                    continue
                if attribute_name not in constraint_group_attribute_names:
                    continue
                non_unique_node.non_unique_attributes.append(
                    NonUniqueAttribute(
                        attribute=schema.get_attribute(attribute_name),
                        attribute_name=attribute_name,
                        attribute_value=attribute_value,
                        deepest_branch_name=deepest_branch_name,
                    )
                )
            all_non_unique_nodes.extend(non_unique_nodes_by_id.values())

        return all_non_unique_nodes

    def get_uniqueness_violations(
        self, non_unique_node: NonUniqueNode
    ) -> set[NonUniqueAttribute | NonUniqueRelatedAttribute]:
        constraint_violations: set[NonUniqueAttribute | NonUniqueRelatedAttribute] = set()
        for attribute_schema in non_unique_node.node_schema.unique_attributes:
            violation = non_unique_node.get_attribute_violation(attribute_schema.name)
            if violation:
                constraint_violations.add(violation)
        for uniqueness_constraint in non_unique_node.node_schema.uniqueness_constraints or []:
            constraint_spec: list[tuple[AttributeSchema | RelationshipSchema, str | None]] = []
            for element in uniqueness_constraint:
                sub_schema, property_name = get_attribute_path_from_string(element, non_unique_node.node_schema)
                constraint_spec.append((sub_schema, property_name))
            violations = non_unique_node.get_constraint_violation(constraint_spec)
            if violations:
                constraint_violations |= set(violations)
        return constraint_violations

    def generate_data_paths(self, non_unique_node: NonUniqueNode, grouped_data_paths: GroupedDataPaths) -> None:
        constraint_violations = self.get_uniqueness_violations(non_unique_node)
        schema_kind = non_unique_node.node_schema.kind
        for violation in constraint_violations:
            grouping_key = f"{schema_kind}/{violation.grouping_key}"
            grouped_data_paths.add_data_path(
                DataPath(
                    branch=violation.deepest_branch_name,
                    path_type=violation.path_type,
                    node_id=non_unique_node.node_id,
                    kind=schema_kind,
                    field_name=violation.field_name,
                    property_name=violation.property_name,
                    value=violation.attribute_value,
                ),
                grouping_key=grouping_key,
            )
