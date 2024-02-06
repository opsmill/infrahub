from typing import List, Optional

from pydantic import BaseModel, Field


class QueryRelationshipAttributePath(BaseModel):
    identifier: str
    attribute_name: Optional[str]


class QueryAttributePath(BaseModel):
    attribute_name: str
    property_name: str


class NodeUniquenessQueryRequest(BaseModel):
    kind: str
    unique_attribute_paths: List[QueryAttributePath] = Field(default_factory=list)
    relationship_attribute_paths: List[QueryRelationshipAttributePath] = Field(default_factory=list)
