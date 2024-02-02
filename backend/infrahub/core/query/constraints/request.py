from typing import List

from pydantic import BaseModel, Field


class QueryRelationshipAttributePath(BaseModel):
    identifier: str
    attribute_name: str


class NodeUniquenessQueryRequest(BaseModel):
    kind: str
    unique_attribute_names: List[str]
    relationship_attribute_paths: List[QueryRelationshipAttributePath] = Field(default_factory=list)
