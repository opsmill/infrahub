from typing import Any

from pydantic import BaseModel, Field

from infrahub.core.constants import PathType
from infrahub.core.schema import AttributeSchema, MainSchemaTypes, RelationshipSchema


class QueryRelationshipAttributePath(BaseModel):
    identifier: str
    attribute_name: str | None = Field(default=None)
    value: Any | None = Field(default=None)

    def __hash__(self) -> int:
        to_hash = self.identifier
        if self.attribute_name:
            to_hash += self.attribute_name
        if self.value:
            to_hash += str(self.value)
        return hash(to_hash)


class QueryAttributePath(BaseModel):
    attribute_name: str
    property_name: str | None = Field(default=None)
    value: Any | None = Field(default=None)

    def __hash__(self) -> int:
        to_hash = self.attribute_name
        if self.property_name:
            to_hash += self.property_name
        if self.value:
            to_hash += str(self.value)
        return hash(to_hash)


class NodeUniquenessQueryRequest(BaseModel):
    kind: str
    unique_attribute_paths: set[QueryAttributePath] = Field(default_factory=set)
    relationship_attribute_paths: set[QueryRelationshipAttributePath] = Field(default_factory=set)

    def __bool__(self) -> bool:
        if self.unique_attribute_paths or self.relationship_attribute_paths:
            return True
        return False

    def __str__(self) -> str:
        return (
            "ATTRS: "
            + "; ".join(
                q.attribute_name + " " + str(q.property_name) + " " + (str(q.value) if q.value is not None else "")
                for q in self.unique_attribute_paths
            )
            + " RELS: "
            + "; ".join(
                q.identifier + " " + str(q.attribute_name) + " " + (str(q.value) if q.value is not None else "")
                for q in self.relationship_attribute_paths
            )
        )


class NonUniqueRelatedAttribute(BaseModel):
    relationship: RelationshipSchema
    attribute_name: str
    attribute_value: str
    deepest_branch_name: str

    def __hash__(self) -> int:
        return hash(self.relationship.name + self.attribute_name + self.attribute_value)

    @property
    def grouping_key(self) -> str:
        return f"{self.relationship.name}/{self.attribute_name}/{self.attribute_value}"

    @property
    def path_type(self) -> PathType:
        return PathType.RELATIONSHIP_ONE

    @property
    def field_name(self) -> str:
        return self.relationship.name

    @property
    def property_name(self) -> str:
        return self.attribute_name


class NonUniqueAttribute(BaseModel):
    attribute: AttributeSchema
    attribute_name: str
    attribute_value: str
    deepest_branch_name: str

    def __hash__(self) -> int:
        return hash(self.attribute.name + self.attribute_name + self.attribute_value)

    @property
    def grouping_key(self) -> str:
        return f"{self.attribute_name}/{self.attribute_value}"

    @property
    def path_type(self) -> PathType:
        return PathType.ATTRIBUTE

    @property
    def field_name(self) -> str:
        return self.attribute_name

    @property
    def property_name(self) -> str:
        return "value"


class NonUniqueNode(BaseModel):
    node_schema: MainSchemaTypes
    node_id: str
    non_unique_attributes: list[NonUniqueAttribute] = Field(default_factory=list)
    non_unique_related_attributes: list[NonUniqueRelatedAttribute] = Field(default_factory=list)

    def get_relationship_violation(
        self, relationship_name: str, attribute_name: str | None
    ) -> NonUniqueRelatedAttribute | None:
        attribute_names = {attribute_name}
        if attribute_name is None:
            attribute_names.add("id")
        for nura in self.non_unique_related_attributes:
            if nura.relationship.name == relationship_name and nura.attribute_name in attribute_names:
                return nura
        return None

    def get_attribute_violation(self, attribute_name: str) -> NonUniqueAttribute | None:
        for nua in self.non_unique_attributes:
            if nua.attribute_name == attribute_name:
                return nua
        return None

    def get_constraint_violation(
        self, constraint_specifications: list[tuple[AttributeSchema | RelationshipSchema, str | None]]
    ) -> list[NonUniqueAttribute | NonUniqueRelatedAttribute] | None:
        violations: list[NonUniqueAttribute | NonUniqueRelatedAttribute] = []
        for sub_schema, property_name in constraint_specifications:
            if isinstance(sub_schema, AttributeSchema):
                attribute_violation = self.get_attribute_violation(sub_schema.name)
                if not attribute_violation:
                    return None
                violations.append(attribute_violation)
            elif isinstance(sub_schema, RelationshipSchema):
                relationship_violation = self.get_relationship_violation(sub_schema.name, property_name)
                if not relationship_violation:
                    return None
                violations.append(relationship_violation)
        return violations
