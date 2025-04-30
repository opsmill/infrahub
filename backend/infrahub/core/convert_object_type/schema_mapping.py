from pydantic import BaseModel

from infrahub.core import registry
from infrahub.core.constants import RelationshipCardinality


class SchemaMappingValue(BaseModel):
    is_mandatory: bool
    source_field_name: str | None = None  # None means there is no corresponding source field name
    relationship_cardinality: RelationshipCardinality | None = None


SchemaMapping = dict[str, SchemaMappingValue]


def get_schema_mapping(source_kind: str, target_kind: str, branch: str) -> SchemaMapping:
    """
    Return fields mapping meant to be used for converting a node from `source_kind` to `target_kind`.
    For any field of the target kind, field of the source kind with identical name and type will be matched.
    If there is no match, the mapping will only indicate whether the field is mandatory or not.
    Same apply for relationships.
    """

    source_schema = registry.get_node_schema(name=source_kind, branch=branch)
    target_schema = registry.get_node_schema(name=target_kind, branch=branch)

    target_field_to_source_field = {}
    for target_attr in target_schema.attributes:
        for source_attr in source_schema.attributes:
            if source_attr.name == target_attr.name and source_attr.kind == target_attr.kind:
                target_field_to_source_field[target_attr.name] = SchemaMappingValue(
                    source_field_name=source_attr.name, is_mandatory=not target_attr.optional
                )
                break
        else:
            target_field_to_source_field[target_attr.name] = SchemaMappingValue(is_mandatory=not target_attr.optional)

    for target_rel in target_schema.relationships:
        for source_rel in source_schema.relationships:
            if (
                source_rel.name == target_rel.name
                and source_rel.peer == target_rel.peer
                and source_rel.cardinality == target_rel.cardinality
            ):
                target_field_to_source_field[target_rel.name] = SchemaMappingValue(
                    source_field_name=source_rel.name,
                    is_mandatory=not target_rel.optional,
                    relationship_cardinality=target_rel.cardinality,
                )
                break
        else:
            target_field_to_source_field[target_rel.name] = SchemaMappingValue(
                is_mandatory=not target_rel.optional,
                relationship_cardinality=target_rel.cardinality,
            )

    return target_field_to_source_field
