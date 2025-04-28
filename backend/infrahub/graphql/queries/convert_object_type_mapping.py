import json

from graphene import Field, JSONString, ObjectType, String
from graphql import GraphQLResolveInfo

from infrahub.core.convert_object_type.schema_mapping import get_schema_mapping


class FieldsMapping(ObjectType):
    # TODO use GenericScalar instead?
    mapping = JSONString(required=True)


async def fields_mapping_type_conversion_resolver(
    root: dict,  # noqa: ARG001
    info: GraphQLResolveInfo,  # noqa: ARG001
    source_kind: str,
    target_kind: str,
    branch: str,
) -> dict:
    mapping = get_schema_mapping(source_kind=source_kind, target_kind=target_kind, branch=branch)
    mapping_dict = {field_name: model.model_dump(mode="json") for field_name, model in mapping.items()}
    return {"mapping": json.dumps(mapping_dict)}


FieldMappingTypeConversion = Field(
    FieldsMapping,
    source_kind=String(),
    target_kind=String(),
    branch=String(),
    description="Retrieve fields mapping for converting object type",
    resolver=fields_mapping_type_conversion_resolver,
    required=True,
)
