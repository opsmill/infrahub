from typing import Any

from infrahub.core.constants import MetadataOptions
from infrahub.core.metadata.model import MetadataQueryOptions


class MetadataDeterminer:
    async def determine_metadata_for_fields(self, node_fields: dict[str, Any]) -> MetadataQueryOptions:
        """Determine metadata required based on fields requested

        All attribute-level metadata is combined and all relationship-level metadata is combined
        """
        node_metadata_options = MetadataOptions.NONE
        if "_updated_at" in node_fields or "updated_at" in node_fields:
            node_metadata_options |= MetadataOptions.UPDATED_AT
        if "updated_by" in node_fields:
            node_metadata_options |= MetadataOptions.UPDATED_BY
        if "created_at" in node_fields:
            node_metadata_options |= MetadataOptions.CREATED_AT
        if "created_by" in node_fields:
            node_metadata_options |= MetadataOptions.CREATED_BY

        attribute_metadata_options = MetadataOptions.NONE
        relationship_metadata_options = MetadataOptions.NONE
        for field_properties_dict in node_fields.values():
            if not field_properties_dict or not isinstance(field_properties_dict, dict):
                continue
            field_metadata_options = MetadataOptions.NONE
            is_relationship = False
            metadata_properties_dict = field_properties_dict
            try:
                # try the cardinality-one relationship structure
                metadata_properties_dict = field_properties_dict["properties"]
            except (KeyError, TypeError):
                pass
            try:
                # try the cardinality-many relationship structure
                metadata_properties_dict = field_properties_dict["edges"]["properties"]
                is_relationship = True
            except (KeyError, TypeError):
                pass
            if not (field_metadata_options & MetadataOptions.UPDATED_AT) and (
                "updated_at" in metadata_properties_dict or "_updated_at" in metadata_properties_dict
            ):
                field_metadata_options |= MetadataOptions.UPDATED_AT
            if not (field_metadata_options & MetadataOptions.UPDATED_BY) and "updated_by" in metadata_properties_dict:
                field_metadata_options |= MetadataOptions.UPDATED_BY
            if not (field_metadata_options & MetadataOptions.CREATED_AT) and "created_at" in metadata_properties_dict:
                field_metadata_options |= MetadataOptions.CREATED_AT
            if not (field_metadata_options & MetadataOptions.CREATED_BY) and "created_by" in metadata_properties_dict:
                field_metadata_options |= MetadataOptions.CREATED_BY
            if not (field_metadata_options & MetadataOptions.SOURCE) and "source" in metadata_properties_dict:
                field_metadata_options |= MetadataOptions.SOURCE
            if not (field_metadata_options & MetadataOptions.OWNER) and "owner" in metadata_properties_dict:
                field_metadata_options |= MetadataOptions.OWNER
            if is_relationship:
                relationship_metadata_options |= field_metadata_options
            else:
                attribute_metadata_options |= field_metadata_options

        return MetadataQueryOptions(
            node_level=node_metadata_options,
            attribute_level=attribute_metadata_options,
            relationship_level=relationship_metadata_options,
        )
