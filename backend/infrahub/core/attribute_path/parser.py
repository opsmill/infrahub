from typing import Optional, Union

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.schema import GenericSchema, NodeSchema

from .exception import AttributePathParsingError
from .model import SchemaAttributePath


class AttributePathParser:
    def parse(
        self, schema: Union[NodeSchema, GenericSchema], attribute_path: str, branch: Optional[Union[Branch, str]]
    ) -> SchemaAttributePath:
        path_parts = attribute_path.split("__")
        if len(path_parts) == 3:
            relationship_name, attribute_name, attribute_property_name = path_parts
        elif len(path_parts) == 2:
            relationship_name = None
            attribute_name, attribute_property_name = path_parts
        else:
            raise AttributePathParsingError(
                "Attribute path must be of the format [<relationship_name>__]<attribute_name>[__<property>], the separator is two underscores"
            )

        relationship_schema, related_schema = None, None
        schema_to_check = schema
        if relationship_name:
            relationship_schema = schema.get_relationship(relationship_name, raise_on_error=False)
            if not relationship_schema:
                raise AttributePathParsingError(
                    f"{relationship_name} is not the name of a relationship attribute o {schema.kind}"
                )
            related_schema = registry.schema.get(relationship_schema.peer, branch=branch)
            schema_to_check = related_schema

        attribute_schema = schema_to_check.get_attribute(attribute_name, raise_on_error=False)
        if not attribute_schema:
            raise AttributePathParsingError(f"{attribute_name} is not an attribute of {schema_to_check.kind}")
        return SchemaAttributePath(
            node_schema=schema,
            relationship_schema=relationship_schema,
            related_schema=related_schema,
            attribute_schema=attribute_schema,
            attribute_property_name=attribute_property_name,
        )
