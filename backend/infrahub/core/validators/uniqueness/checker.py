import asyncio
from itertools import chain
from typing import Dict, List, Optional, Set, Tuple, Union

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.path import DataPath, GroupedDataPaths
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema
from infrahub.database import InfrahubDatabase

from ..interface import ConstraintCheckerInterface
from ..model import SchemaConstraintValidatorRequest
from .model import (
    NodeUniquenessQueryRequest,
    NonUniqueAttribute,
    NonUniqueNode,
    NonUniqueRelatedAttribute,
    QueryAttributePath,
    QueryRelationshipAttributePath,
)
from .query import NodeUniqueAttributeConstraintQuery


def get_attribute_path_from_string(
    path: str, schema: Union[NodeSchema, GenericSchema]
) -> Tuple[Union[AttributeSchema, RelationshipSchema], Optional[str]]:
    if "__" in path:
        name, property_name = path.split("__")
    else:
        name, property_name = path, None
    attribute_schema = schema.get_attribute(name, raise_on_error=False)
    relationship_schema = schema.get_relationship(name, raise_on_error=False)
    if not (attribute_schema or relationship_schema):
        raise ValueError(f"{path} is not valid on {schema.kind}")
    return attribute_schema or relationship_schema, property_name


class UniquenessChecker(ConstraintCheckerInterface):
    def __init__(
        self, db: InfrahubDatabase, branch: Optional[Union[Branch, str]] = None, max_concurrent_execution: int = 5
    ):
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

    async def check(self, request: SchemaConstraintValidatorRequest) -> List[GroupedDataPaths]:
        schema_objects = [request.node_schema]

        non_unique_nodes_lists = await asyncio.gather(*[self.check_one_schema(schema) for schema in schema_objects])

        grouped_data_paths = GroupedDataPaths()
        for non_unique_node in chain(*non_unique_nodes_lists):
            self.generate_data_paths(non_unique_node, grouped_data_paths)
        return [grouped_data_paths]

    async def build_query_request(self, schema: Union[NodeSchema, GenericSchema]) -> NodeUniquenessQueryRequest:
        unique_attr_paths = [
            QueryAttributePath(attribute_name=attr_schema.name, property_name="value")
            for attr_schema in schema.unique_attributes
        ]
        relationship_attr_paths = []

        if not schema.uniqueness_constraints:
            return NodeUniquenessQueryRequest(
                kind=schema.kind,
                unique_attribute_paths=unique_attr_paths,
                relationship_attribute_paths=[],
            )

        for uniqueness_constraint in schema.uniqueness_constraints:
            for path in uniqueness_constraint:
                sub_schema, property_name = get_attribute_path_from_string(path, schema)
                if isinstance(sub_schema, AttributeSchema):
                    unique_attr_paths.append(
                        QueryAttributePath(attribute_name=sub_schema.name, property_name=property_name)
                    )
                elif isinstance(sub_schema, RelationshipSchema):
                    relationship_attr_paths.append(
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
        schema: Union[NodeSchema, GenericSchema],
    ) -> List[NonUniqueNode]:
        query_request = await self.build_query_request(schema)

        relationship_schema_by_identifier = {rel.identifier: rel for rel in schema.relationships}

        query = await NodeUniqueAttributeConstraintQuery.init(
            db=self.db, branch=await self.get_branch(), query_request=query_request
        )
        async with self.semaphore:
            query_results = await query.execute(db=self.db.start_session(read_only=True))

        non_unique_nodes_by_id: Dict[str, NonUniqueNode] = {}
        for result in query_results.results:
            node_id = str(result.get("node_id"))
            if node_id not in non_unique_nodes_by_id:
                non_unique_nodes_by_id[node_id] = NonUniqueNode(node_schema=schema, node_id=node_id)
            non_unique_node = non_unique_nodes_by_id[node_id]
            relationship_identifier = result.get("relationship_identifier")
            attribute_name = str(result.get("attr_name"))
            attribute_value = str(result.get("attr_value"))
            deepest_branch_name = str(result.get("deepest_branch_name"))
            if relationship_identifier:
                relationship_schema = relationship_schema_by_identifier[str(relationship_identifier)]
                non_unique_node.non_unique_related_attributes.append(
                    NonUniqueRelatedAttribute(
                        relationship=relationship_schema,
                        attribute_name=attribute_name,
                        attribute_value=attribute_value,
                        deepest_branch_name=deepest_branch_name,
                    )
                )
            else:
                non_unique_node.non_unique_attributes.append(
                    NonUniqueAttribute(
                        attribute=schema.get_attribute(attribute_name),
                        attribute_name=attribute_name,
                        attribute_value=attribute_value,
                        deepest_branch_name=deepest_branch_name,
                    )
                )
        return list(non_unique_nodes_by_id.values())

    def get_uniqueness_violations(
        self, non_unique_node: NonUniqueNode
    ) -> Set[Union[NonUniqueAttribute, NonUniqueRelatedAttribute]]:
        constraint_violations: Set[Union[NonUniqueAttribute, NonUniqueRelatedAttribute]] = set()
        for attribute_schema in non_unique_node.node_schema.unique_attributes:
            violation = non_unique_node.get_attribute_violation(attribute_schema.name)
            if violation:
                constraint_violations.add(violation)
        for uniqueness_constraint in non_unique_node.node_schema.uniqueness_constraints or []:
            constraint_spec: List[Tuple[Union[AttributeSchema, RelationshipSchema], Optional[str]]] = []
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
