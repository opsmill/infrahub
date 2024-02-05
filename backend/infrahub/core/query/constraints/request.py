from typing import List, Optional

from pydantic import BaseModel, Field


class QueryRelationshipAttributePath(BaseModel):
    identifier: str
    attribute_name: Optional[str]


class NodeUniquenessQueryRequest(BaseModel):
    kind: str
    unique_attribute_names: List[str] = Field(default_factory=list)
    relationship_attribute_paths: List[QueryRelationshipAttributePath] = Field(default_factory=list)
