from typing import Optional, Union

from pydantic import BaseModel

from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema


class SchemaAttributePath(BaseModel):
    node_schema: Union[NodeSchema, GenericSchema]
    relationship_schema: Optional[RelationshipSchema]
    related_schema: Optional[Union[NodeSchema, GenericSchema]]
    attribute_schema: AttributeSchema
    attribute_property_name: Optional[str]
