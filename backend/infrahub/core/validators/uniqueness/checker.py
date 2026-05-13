from __future__ import annotations

import asyncio
from itertools import chain
from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.path import DataPath, GroupedDataPaths
from infrahub.core.schema import AttributeSchema, MainSchemaTypes, RelationshipSchema
from infrahub.core.validators.uniqueness.index import UniquenessQueryResultsIndex

from ..interface import ConstraintCheckerInterface
from .model import (
    NodeUniquenessQueryRequest,
    NonUniqueAttribute,
    NonUniqueNode,
    NonUniqueRelatedAttribute,
    QueryAttributePath,
    QueryRelationshipAttributePath,
)
from .query import NodeUniqueAttributeConstraintQuery

if TYPE_CHECKING:
    from infrahub.core.node import Node
    from infrahub.core.query import QueryResult
    from infrahub.database import InfrahubDatabase

    from ..model import SchemaConstraintValidatorRequest


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
        self, db: InfrahubDatabase, branch: Branch | str | None = None, max_concurrent_execution: int = 5
    ) -> None:
        self.db = db
        self.branch = branch
        self.semaphore = asyncio.Semaphore(max_concurrent_execution)

    @property
    def name(self) -> str:
        return "node.uniqueness_constraints.update"

    def supports(self, request: SchemaConstraintValidatorRequest) -> bool:
        return request.constraint_name == self.name

    async def get_branch(self) -> Branch:
        if not isinstance(self.branch, Branch):
            self.branch = await registry.get_branch(db=self.db, branch=self.branch)
        return self.branch

    async def check(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]:
        schema_objects = [request.node_schema]
        non_unique_nodes_lists = await asyncio.gather(
            *[self.check_one_schema(schema, node_uuids=request.node_uuids) for schema in schema_objects]
        )

        grouped_data_paths = GroupedDataPaths()
        for non_unique_node in chain(*non_unique_nodes_lists):
            self.generate_data_paths(non_unique_node, grouped_data_paths)
        return [grouped_data_paths]

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
        node_uuids: set[str] | None = None,
    ) -> list[NonUniqueNode]:
        if node_uuids:
            query_request = await self.build_scoped_query_request(schema=schema, node_uuids=node_uuids)
        else:
            query_request = await self.build_query_request(schema)

        if not query_request:
            return []

        query = await NodeUniqueAttributeConstraintQuery.init(
            db=self.db, branch=await self.get_branch(), query_request=query_request
        )
        async with self.semaphore:
            async with self.db.start_session(read_only=True) as db:
                query_results = await query.execute(db=db)

        return await self._parse_results(schema=schema, query_results=query_results.results)

    async def build_scoped_query_request(
        self, schema: MainSchemaTypes, node_uuids: set[str]
    ) -> NodeUniquenessQueryRequest:
        """Build a value-anchored query request for a known set of node UUIDs.

        Pre-fetches the current values of every attribute/relationship referenced
        by any uniqueness constraint on the schema, then emits
        QueryAttributePath/QueryRelationshipAttributePath entries with `value`
        set. The existing query routes these through its `_with_value` subqueries,
        which can use the :AttributeValueIndexed(value) index instead of doing a
        kind-wide label scan.

        Why pre-fetch every constraint field (not just the diffed ones): a
        constraint like (name, location) requires both values even if only `name`
        diffed. We must look up `location` so the resulting valued query can find
        peers sharing the full (name, location) tuple.
        """
        attr_schemas_in_constraints: dict[str, tuple[AttributeSchema, str | None]] = {}
        rel_paths_in_constraints: list[tuple[RelationshipSchema, str | None]] = []

        for attr_schema in schema.unique_attributes:
            attr_schemas_in_constraints[f"{attr_schema.name}|value"] = (attr_schema, "value")

        if schema.uniqueness_constraints:
            for uniqueness_constraint in schema.uniqueness_constraints:
                for path in uniqueness_constraint:
                    sub_schema, property_name = get_attribute_path_from_string(path, schema)
                    if isinstance(sub_schema, AttributeSchema):
                        key = f"{sub_schema.name}|{property_name or 'value'}"
                        attr_schemas_in_constraints[key] = (sub_schema, property_name)
                    elif isinstance(sub_schema, RelationshipSchema):
                        rel_paths_in_constraints.append((sub_schema, property_name))

        if not attr_schemas_in_constraints and not rel_paths_in_constraints:
            return NodeUniquenessQueryRequest(kind=schema.kind)

        fields_filter: dict[str, dict] = {}
        for attr_schema, _ in attr_schemas_in_constraints.values():
            fields_filter[attr_schema.name] = {}
        for rel_schema, _ in rel_paths_in_constraints:
            fields_filter[rel_schema.name] = {}

        branch = await self.get_branch()
        nodes = await NodeManager.get_many(
            db=self.db,
            ids=list(node_uuids),
            fields=fields_filter,
            branch=branch,
        )

        unique_attr_paths: set[QueryAttributePath] = set()
        relationship_attr_paths: set[QueryRelationshipAttributePath] = set()

        for node in nodes.values():
            for attr_schema, property_name in attr_schemas_in_constraints.values():
                self._extract_attribute_path(
                    node=node,
                    attr_schema=attr_schema,
                    property_name=property_name,
                    paths=unique_attr_paths,
                )
            for rel_schema, property_name in rel_paths_in_constraints:
                await self._extract_relationship_path(
                    node=node,
                    rel_schema=rel_schema,
                    property_name=property_name,
                    paths=relationship_attr_paths,
                )

        return NodeUniquenessQueryRequest(
            kind=schema.kind,
            unique_attribute_paths=unique_attr_paths,
            relationship_attribute_paths=relationship_attr_paths,
        )

    @staticmethod
    def _extract_attribute_path(
        node: Node,
        attr_schema: AttributeSchema,
        property_name: str | None,
        paths: set[QueryAttributePath],
    ) -> None:
        attr = getattr(node, attr_schema.name, None)
        if attr is None:
            return
        attr_value = getattr(attr, property_name or "value", None)
        if attr_value is None:
            return
        paths.add(
            QueryAttributePath(
                attribute_name=attr_schema.name,
                attribute_kind=attr_schema.kind,
                property_name=property_name,
                value=attr_value,
            )
        )

    async def _extract_relationship_path(
        self,
        node: Node,
        rel_schema: RelationshipSchema,
        property_name: str | None,
        paths: set[QueryRelationshipAttributePath],
    ) -> None:
        rel_manager = getattr(node, rel_schema.name, None)
        if rel_manager is None or rel_schema.cardinality != "one":
            # Cardinality-many relationships in uniqueness constraints are
            # uncommon and don't translate cleanly to a single peer value —
            # emit an unvalued path so the existing query still exercises the
            # constraint (it just won't be value-scoped).
            paths.add(
                QueryRelationshipAttributePath(
                    identifier=rel_schema.get_identifier(),
                    attribute_name=property_name,
                )
            )
            return
        relationships = await rel_manager.get_relationships(db=self.db)
        if not relationships:
            return
        peer_id = relationships[0].peer_id
        if peer_id is None:
            return
        if property_name is None:
            # Relationship-only path: value is the peer UUID.
            paths.add(
                QueryRelationshipAttributePath(
                    identifier=rel_schema.get_identifier(),
                    attribute_name=None,
                    value=peer_id,
                )
            )
            return
        # Relationship + peer-attribute path: value is the peer's attribute value.
        peer = await rel_manager.get_peer(db=self.db)
        if peer is None:
            return
        peer_attr = getattr(peer, property_name, None)
        if peer_attr is None or peer_attr.value is None:
            return
        paths.add(
            QueryRelationshipAttributePath(
                identifier=rel_schema.get_identifier(),
                attribute_name=property_name,
                value=peer_attr.value,
            )
        )

    async def _parse_results(self, schema: MainSchemaTypes, query_results: list[QueryResult]) -> list[NonUniqueNode]:
        relationship_schema_by_identifier = {rel.identifier: rel for rel in schema.relationships}
        all_non_unique_nodes: list[NonUniqueNode] = []
        results_index = UniquenessQueryResultsIndex(query_results=query_results)

        branch = await self.get_branch()
        schema_branch = self.db.schema.get_schema_branch(name=branch.name)
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
