import json

from graphene import Field, JSONString, ObjectType, String
from graphql import GraphQLResolveInfo
from pydantic import BaseModel

from infrahub.core import registry
from infrahub.core.constants import RelationshipCardinality

# None key means field is mandatory and no matching input field was found (and should be filled by user)


class SchemaMappingValue(BaseModel):
    source_field_name: str | None = None  # None means there is no corresponding source field name
    # Boolean value means source_field_name is None and we indicate whether field is mandatory or optional
    is_mandatory: bool | None = None
    relationship_cardinality: RelationshipCardinality | None = None


SchemaMapping = dict[str, SchemaMappingValue]


def get_schema_mapping(source_kind: str, target_kind: str, branch: str) -> SchemaMapping:
    source_schema = registry.get_node_schema(name=source_kind, branch=branch)
    target_schema = registry.get_node_schema(name=target_kind, branch=branch)

    target_field_to_source_field = {}
    for target_attr in target_schema.attributes:
        for source_attr in source_schema.attributes:
            if source_attr.name == target_attr.name and source_attr.kind == target_attr.kind:
                target_field_to_source_field[target_attr.name] = SchemaMappingValue(source_field_name=source_attr.name)
                break
        else:
            target_field_to_source_field[target_attr.name] = SchemaMappingValue(is_mandatory=not target_attr.optional)

    for target_rel in target_schema.relationships:
        for source_rel in source_schema.relationships:
            if source_rel.name == target_rel.name and source_rel.cardinality == target_rel.cardinality:
                target_field_to_source_field[target_rel.name] = SchemaMappingValue(
                    source_field_name=source_rel.name,
                    relationship_cardinality=target_rel.cardinality,
                )
                break
        else:
            target_field_to_source_field[target_rel.name] = SchemaMappingValue(
                is_mandatory=not target_rel.optional,
                relationship_cardinality=target_rel.cardinality,
            )

    return target_field_to_source_field


class FieldsMapping(ObjectType):
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
