import contextlib
from typing import Any

from infrahub.core.constants import MetadataOptions
from infrahub.core.metadata.model import MetadataQueryOptions


class MetadataDeterminer:
    async def determine_metadata_for_fields(
        self, node_fields: dict[str, Any], metadata_fields: dict[str, Any] | None = None
    ) -> MetadataQueryOptions:
        """Determine metadata required based on fields requested.

        Args:
            node_fields: The node fields requested in the query.
            metadata_fields: The metadata fields requested for the node (e.g., created_at, updated_at).

        All attribute-level metadata is combined and all relationship-level metadata is combined.
        """
        node_metadata_options = MetadataOptions.NONE
        metadata_fields = metadata_fields or {}
        if "_updated_at" in metadata_fields or "updated_at" in metadata_fields:
            node_metadata_options |= MetadataOptions.UPDATED_AT
        if "updated_by" in metadata_fields:
            node_metadata_options |= MetadataOptions.UPDATED_BY
        if "created_at" in metadata_fields:
            node_metadata_options |= MetadataOptions.CREATED_AT
        if "created_by" in metadata_fields:
            node_metadata_options |= MetadataOptions.CREATED_BY

        attribute_metadata_options = MetadataOptions.NONE
        relationship_metadata_options = MetadataOptions.NONE
        for field_properties_dict in node_fields.values():
            if not field_properties_dict or not isinstance(field_properties_dict, dict):
                continue
            field_metadata_options = MetadataOptions.NONE
            is_relationship = False
            metadata_properties_dict = field_properties_dict
            with contextlib.suppress(KeyError, TypeError):
                # try the cardinality-one relationship structure
                metadata_properties_dict = field_properties_dict["properties"]
                if not metadata_properties_dict:
                    # try the cardinality-many relationship structure
                    metadata_properties_dict = field_properties_dict["edges"]["properties"]
                    is_relationship = True
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
            if not (field_metadata_options & MetadataOptions.SOURCE) and (
                "source" in metadata_properties_dict or "_relation__owner" in metadata_properties_dict
            ):
                field_metadata_options |= MetadataOptions.SOURCE
            if not (field_metadata_options & MetadataOptions.OWNER) and (
                "owner" in metadata_properties_dict or "_relation__source" in metadata_properties_dict
            ):
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
