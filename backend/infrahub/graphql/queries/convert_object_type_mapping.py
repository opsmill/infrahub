from graphene import Field, ObjectType, String
from graphene.types.generic import GenericScalar
from graphql import GraphQLResolveInfo

from infrahub.core import registry
from infrahub.core.convert_object_type.schema_mapping import get_schema_mapping


class FieldsMapping(ObjectType):
    mapping = GenericScalar(required=True)


async def fields_mapping_type_conversion_resolver(
    root: dict,  # noqa: ARG001
    info: GraphQLResolveInfo,  # noqa: ARG001
    source_kind: str,
    target_kind: str,
    branch: str,
) -> dict:
    source_schema = registry.get_node_schema(name=source_kind, branch=branch)
    target_schema = registry.get_node_schema(name=target_kind, branch=branch)

    mapping = get_schema_mapping(source_schema=source_schema, target_schema=target_schema)
    mapping_dict = {field_name: model.model_dump(mode="json") for field_name, model in mapping.items()}
    return {"mapping": mapping_dict}


FieldsMappingTypeConversion = Field(
    FieldsMapping,
    source_kind=String(),
    target_kind=String(),
    branch=String(),
    description="Retrieve fields mapping for converting object type",
    resolver=fields_mapping_type_conversion_resolver,
    required=True,
)
