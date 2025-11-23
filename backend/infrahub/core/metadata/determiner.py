from typing import Any

from infrahub.core.constants import MetadataOptions
from infrahub.core.metadata.model import MetadataQueryOptions
from infrahub.core.schema import GenericSchema, MainSchemaTypes
from infrahub.core.schema.schema_branch import SchemaBranch


class MetadataDeterminer:
    def __init__(self, schema_branch: SchemaBranch) -> None:
        self.schema_branch = schema_branch

    async def determine_metadata_for_schema(
        self,
        schema: MainSchemaTypes,
        node_fields: dict[str, Any],
    ) -> MetadataQueryOptions:
        """Determine metadata query options for node, attribute, and relationship levels based on requested fields."""
        # node-level metadata
        node_metadata_options = MetadataOptions.NONE
        if "_updated_at" in node_fields or "updated_at" in node_fields:
            node_metadata_options |= MetadataOptions.UPDATED_AT
        if "updated_by" in node_fields:
            node_metadata_options |= MetadataOptions.UPDATED_BY
        if "created_at" in node_fields:
            node_metadata_options |= MetadataOptions.CREATED_AT
        if "created_by" in node_fields:
            node_metadata_options |= MetadataOptions.CREATED_BY

        all_attribute_names = set(schema.attribute_names)
        all_relationship_names = set(schema.relationship_names)
        if isinstance(schema, GenericSchema):
            for inheriting_schema_kind in schema.used_by:
                inheriting_schema = self.schema_branch.get(name=inheriting_schema_kind, duplicate=False)
                all_attribute_names.update(inheriting_schema.attribute_names)
                all_relationship_names.update(inheriting_schema.relationship_names)

        attribute_metadata_options = MetadataOptions.NONE
        for attribute_name in all_attribute_names:
            if not node_fields or attribute_name not in node_fields:
                continue
            attr_fields = node_fields[attribute_name]
            if not (attribute_metadata_options & MetadataOptions.UPDATED_AT) and (
                "updated_at" in attr_fields or "_updated_at" in attr_fields
            ):
                attribute_metadata_options |= MetadataOptions.UPDATED_AT
            if not (attribute_metadata_options & MetadataOptions.UPDATED_BY) and "updated_by" in attr_fields:
                attribute_metadata_options |= MetadataOptions.UPDATED_BY
            if not (attribute_metadata_options & MetadataOptions.CREATED_AT) and "created_at" in attr_fields:
                attribute_metadata_options |= MetadataOptions.CREATED_AT
            if not (attribute_metadata_options & MetadataOptions.CREATED_BY) and "created_by" in attr_fields:
                attribute_metadata_options |= MetadataOptions.CREATED_BY
            if not (attribute_metadata_options & MetadataOptions.SOURCE) and "source" in attr_fields:
                attribute_metadata_options |= MetadataOptions.SOURCE
            if not (attribute_metadata_options & MetadataOptions.OWNER) and "owner" in attr_fields:
                attribute_metadata_options |= MetadataOptions.OWNER

        relationship_metadata_options = MetadataOptions.NONE
        for relationship_name in all_relationship_names:
            if not node_fields or relationship_name not in node_fields:
                continue
            rel_fields = node_fields[relationship_name]
            rel_property_fields = rel_fields.get("edges", {}).get("properties", [])
            if not (relationship_metadata_options & MetadataOptions.UPDATED_AT) and (
                "updated_at" in rel_property_fields or "_updated_at" in rel_property_fields
            ):
                relationship_metadata_options |= MetadataOptions.UPDATED_AT
            if not (relationship_metadata_options & MetadataOptions.UPDATED_BY) and "updated_by" in rel_property_fields:
                relationship_metadata_options |= MetadataOptions.UPDATED_BY
            if not (relationship_metadata_options & MetadataOptions.CREATED_AT) and "created_at" in rel_property_fields:
                relationship_metadata_options |= MetadataOptions.CREATED_AT
            if not (relationship_metadata_options & MetadataOptions.CREATED_BY) and "created_by" in rel_property_fields:
                relationship_metadata_options |= MetadataOptions.CREATED_BY
            if not (relationship_metadata_options & MetadataOptions.SOURCE) and "source" in rel_property_fields:
                relationship_metadata_options |= MetadataOptions.SOURCE
            if not (relationship_metadata_options & MetadataOptions.OWNER) and "owner" in rel_property_fields:
                relationship_metadata_options |= MetadataOptions.OWNER

        return MetadataQueryOptions(
            node_level=node_metadata_options,
            attribute_level=attribute_metadata_options,
            relationship_level=relationship_metadata_options,
        )

    async def determine_metadata_for_fields(self, node_fields: dict[str, Any]) -> MetadataQueryOptions:
        node_metadata_options = MetadataOptions.NONE
        if "_updated_at" in node_fields or "updated_at" in node_fields:
            node_metadata_options |= MetadataOptions.UPDATED_AT
        if "updated_by" in node_fields:
            node_metadata_options |= MetadataOptions.UPDATED_BY
        if "created_at" in node_fields:
            node_metadata_options |= MetadataOptions.CREATED_AT
        if "created_by" in node_fields:
            node_metadata_options |= MetadataOptions.CREATED_BY

        field_metadata_options = MetadataOptions.NONE
        for field_properties_dict in node_fields.values():
            if not field_properties_dict or not isinstance(field_properties_dict, dict):
                continue
            try:
                # try the cardinality-one relationship structure
                field_properties_dict = field_properties_dict["properties"]
            except (KeyError, TypeError):
                pass
            try:
                # try the cardinality-many relationship structure
                field_properties_dict = field_properties_dict["edges"]["properties"]
            except (KeyError, TypeError):
                pass
            if not (field_metadata_options & MetadataOptions.UPDATED_AT) and (
                "updated_at" in field_properties_dict or "_updated_at" in field_properties_dict
            ):
                field_metadata_options |= MetadataOptions.UPDATED_AT
            if not (field_metadata_options & MetadataOptions.UPDATED_BY) and "updated_by" in field_properties_dict:
                field_metadata_options |= MetadataOptions.UPDATED_BY
            if not (field_metadata_options & MetadataOptions.CREATED_AT) and "created_at" in field_properties_dict:
                field_metadata_options |= MetadataOptions.CREATED_AT
            if not (field_metadata_options & MetadataOptions.CREATED_BY) and "created_by" in field_properties_dict:
                field_metadata_options |= MetadataOptions.CREATED_BY
            if not (field_metadata_options & MetadataOptions.SOURCE) and "source" in field_properties_dict:
                field_metadata_options |= MetadataOptions.SOURCE
            if not (field_metadata_options & MetadataOptions.OWNER) and "owner" in field_properties_dict:
                field_metadata_options |= MetadataOptions.OWNER

        return MetadataQueryOptions(
            node_level=node_metadata_options,
            attribute_level=field_metadata_options,
            relationship_level=field_metadata_options,
        )
