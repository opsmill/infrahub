from typing import Any

from infrahub.core.constants import MetadataOptions
from infrahub.core.manager import MetadataQueryOptions
from infrahub.core.schema import GenericSchema, MainSchemaTypes
from infrahub.core.schema.schema_branch import SchemaBranch


class MetadataDeterminer:
    def __init__(self, schema_branch: SchemaBranch) -> None:
        self.schema_branch = schema_branch

    async def determine_metadata(
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

        # attribute-level metadata
        all_attribute_names = set(schema.attribute_names)
        if isinstance(schema, GenericSchema):
            for inheriting_schema_kind in schema.used_by:
                inheriting_schema = self.schema_branch.get(name=inheriting_schema_kind, duplicate=False)
                all_attribute_names.update(inheriting_schema.attribute_names)

        attribute_metadata_options = MetadataOptions.NONE
        for attr_name in all_attribute_names:
            if not node_fields or attr_name not in node_fields:
                continue
            attr_fields = node_fields[attr_name]
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

        return MetadataQueryOptions(
            node_level=node_metadata_options,
            attribute_level=attribute_metadata_options,
            # TODO: will change when relationships are updated
            relationship_level=MetadataOptions.LINKED_NODES,
        )
