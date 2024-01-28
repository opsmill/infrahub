from typing import List, Union

from pydantic import BaseModel

from infrahub.core.schema import GenericSchema, NodeSchema


class NonUniqueNodeAttribute(BaseModel):
    schema: Union[NodeSchema, GenericSchema]
    node_ids: List[str]
    attribute_name: str
    attribute_value: str
