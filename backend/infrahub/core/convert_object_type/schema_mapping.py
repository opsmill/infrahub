from pydantic import BaseModel

from infrahub.core.constants import RelationshipCardinality
from infrahub.core.schema import NodeSchema


class SchemaMappingValue(BaseModel):
    is_mandatory: bool
    source_field_name: str | None = None  # None means there is no corresponding source field name
    relationship_cardinality: RelationshipCardinality | None = None


SchemaMapping = dict[str, SchemaMappingValue]


def get_schema_mapping(source_schema: NodeSchema, target_schema: NodeSchema) -> SchemaMapping:
    """
    Return fields mapping meant to be used for converting a node from `source_kind` to `target_kind`.
    For any field of the target kind, field of the source kind will be matched if:
    - It's an attribute with identical name and type.
    - It's a relationship with identical peer kind and cardinality.
    If there is no match, the mapping will only indicate whether the field is mandatory or not.
    """

    target_field_to_source_field = {}

    # Create lookup dictionaries for source attributes and relationships
    source_attrs = {attr.name: attr for attr in source_schema.attributes}
    source_rels = {rel.name: rel for rel in source_schema.relationships}

    # Process attributes
    for target_attr in target_schema.attributes:
        source_attr = source_attrs.get(target_attr.name)
        if source_attr and source_attr.kind == target_attr.kind:
            target_field_to_source_field[target_attr.name] = SchemaMappingValue(
                source_field_name=source_attr.name, is_mandatory=not target_attr.optional
            )
        else:
            target_field_to_source_field[target_attr.name] = SchemaMappingValue(is_mandatory=not target_attr.optional)

    # Process relationships
    for target_rel in target_schema.relationships:
        source_rel = source_rels.get(target_rel.name)
        if source_rel and source_rel.peer == target_rel.peer and source_rel.cardinality == target_rel.cardinality:
            target_field_to_source_field[target_rel.name] = SchemaMappingValue(
                source_field_name=source_rel.name,
                is_mandatory=not target_rel.optional,
                relationship_cardinality=target_rel.cardinality,
            )
        else:
            target_field_to_source_field[target_rel.name] = SchemaMappingValue(
                is_mandatory=not target_rel.optional,
                relationship_cardinality=target_rel.cardinality,
            )

    return target_field_to_source_field
