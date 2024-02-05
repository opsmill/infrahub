import asyncio
from itertools import chain
from typing import Dict, Iterable, List, Optional, Set, Tuple, Union

from pydantic import BaseModel, Field

from infrahub.core import registry
from infrahub.core.branch import Branch, ObjectConflict
from infrahub.core.constants import PathType
from infrahub.core.query.constraints.node_unique_attributes import NodeUniqueAttributeConstraintQuery
from infrahub.core.query.constraints.request import NodeUniquenessQueryRequest, QueryRelationshipAttributePath
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema
from infrahub.database import InfrahubDatabase


class NonUniqueRelatedAttribute(BaseModel):
    relationship: RelationshipSchema
    attribute_name: str
    attribute_value: str
    deepest_branch_name: str

    def __hash__(self) -> int:
        return hash(self.relationship.name + self.attribute_name + self.attribute_value)


class NonUniqueAttribute(BaseModel):
    attribute: AttributeSchema
    attribute_name: str
    attribute_value: str
    deepest_branch_name: str

    def __hash__(self) -> int:
        return hash(self.attribute.name + self.attribute_name + self.attribute_value)


class NonUniqueNode(BaseModel):
    node_schema: Union[NodeSchema, GenericSchema]
    node_id: str
    non_unique_attributes: List[NonUniqueAttribute] = Field(default_factory=list)
    non_unique_related_attributes: List[NonUniqueRelatedAttribute] = Field(default_factory=list)

    def get_relationship_violation(
        self, relationship_name: str, attribute_name: str
    ) -> Optional[NonUniqueRelatedAttribute]:
        for nura in self.non_unique_related_attributes:
            if nura.relationship.name == relationship_name and nura.attribute_name == attribute_name:
                return nura
        return None

    def get_attribute_violation(self, attribute_name: str) -> Optional[NonUniqueAttribute]:
        for nua in self.non_unique_attributes:
            if nua.attribute_name == attribute_name:
                return nua
        return None

    def get_constraint_violation(
        self, constraint_specifications: List[Tuple[Optional[str], str]]
    ) -> Optional[List[Union[NonUniqueAttribute, NonUniqueRelatedAttribute]]]:
        violations: List[Union[NonUniqueAttribute, NonUniqueRelatedAttribute]] = []
        for constraint_spec in constraint_specifications:
            relationship_name, attribute_name = constraint_spec
            if not relationship_name:
                attribute_violation = self.get_attribute_violation(attribute_name)
                if not attribute_violation:
                    return None
                violations.append(attribute_violation)
            else:
                relationship_violation = self.get_relationship_violation(relationship_name, attribute_name)
                if not relationship_violation:
                    return None
                violations.append(relationship_violation)
        return violations


class UniquenessChecker:
    def __init__(self, db: InfrahubDatabase, max_concurrent_execution: int = 5):
        self.db = db
        self.semaphore = asyncio.Semaphore(max_concurrent_execution)

    async def get_conflicts(
        self,
        schemas: Iterable[Union[NodeSchema, GenericSchema, str]],
        source_branch: Union[str, Branch],
    ) -> List[ObjectConflict]:
        if isinstance(source_branch, str):
            source_branch = await registry.get_branch(db=self.db, branch=source_branch)
        schema_objects = [
            schema
            if isinstance(schema, (NodeSchema, GenericSchema))
            else registry.schema.get(schema, branch=source_branch)
            for schema in schemas
        ]

        non_unique_nodes_lists = await asyncio.gather(
            *[self.check_one_schema(schema, source_branch) for schema in schema_objects]
        )

        conflicts = []
        for non_unique_node in chain(*non_unique_nodes_lists):
            conflicts.extend(self.generate_object_conflicts(non_unique_node))
        return conflicts

    async def build_query_request(self, schema: Union[NodeSchema, GenericSchema]) -> NodeUniquenessQueryRequest:
        unique_attr_names = {attr_schema.name for attr_schema in schema.unique_attributes}
        relationship_attr_paths = []

        if schema.uniqueness_constraints:
            for uniqueness_constraint in schema.uniqueness_constraints:
                for path in uniqueness_constraint:
                    if "__" in path:
                        relationship_name, attribute_name = path.split("__")
                    else:
                        relationship_name, attribute_name = None, path
                    if not relationship_name:
                        unique_attr_names.add(attribute_name)
                        continue
                    relationship = schema.get_relationship(relationship_name)
                    relationship_attr_paths.append(
                        QueryRelationshipAttributePath(
                            identifier=relationship.get_identifier(), attribute_name=attribute_name
                        )
                    )
        return NodeUniquenessQueryRequest(
            kind=schema.kind,
            unique_attribute_names=list(unique_attr_names),
            relationship_attribute_paths=relationship_attr_paths,
        )

    async def check_one_schema(
        self,
        schema: Union[NodeSchema, GenericSchema],
        branch: Branch,
    ) -> List[NonUniqueNode]:
        query_request = await self.build_query_request(schema)

        relationship_schema_by_identifier = {rel.identifier: rel for rel in schema.relationships}

        query = await NodeUniqueAttributeConstraintQuery.init(db=self.db, branch=branch, query_request=query_request)
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
            constraint_spec: List[Tuple[Optional[str], str]] = []
            for element in uniqueness_constraint:
                if "__" in element:
                    relationship_name, attribute_name = element.split("__")
                    constraint_spec.append((relationship_name, attribute_name))
                else:
                    constraint_spec.append((None, element))
            violations = non_unique_node.get_constraint_violation(constraint_spec)
            if violations:
                constraint_violations |= set(violations)
        return constraint_violations

    def generate_object_conflicts(self, non_unique_node: NonUniqueNode) -> List[ObjectConflict]:
        constraint_violations = self.get_uniqueness_violations(non_unique_node)
        conflicts = []
        for violation in constraint_violations:
            if isinstance(violation, NonUniqueRelatedAttribute):
                path = f"{non_unique_node.node_schema.kind}/{violation.relationship.name}/{violation.attribute_name}"
            else:
                path = f"{non_unique_node.node_schema.kind}/{violation.attribute_name}"
            conflicts.append(
                ObjectConflict(
                    name=path,
                    type="uniqueness-violation",
                    kind=non_unique_node.node_schema.kind,
                    id=non_unique_node.node_id,
                    conflict_path=path,
                    path=path,
                    path_type=PathType.ATTRIBUTE,
                    change_type="attribute_value",
                    value=violation.attribute_value,
                    branch=violation.deepest_branch_name,
                )
            )
        return conflicts
