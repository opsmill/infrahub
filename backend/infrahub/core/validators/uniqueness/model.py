from typing import List, Optional, Union

from pydantic import BaseModel

from infrahub.core.node import Node
from infrahub.core.schema import GenericSchema, NodeSchema


class SchemaUniquenessCheckRequest(BaseModel):
    schema: Union[NodeSchema, GenericSchema]
    attributes: Optional[List[str]] = None


class NonUniqueNodeAttribute(BaseModel):
    nodes: List[Node]
    attribute_name: str
    attribute_value: str

    class Config:
        arbitrary_types_allowed = True
