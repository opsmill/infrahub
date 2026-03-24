from __future__ import annotations

from typing import Any

from infrahub.core.constants import MetadataOptions
from infrahub.core.metadata.model import MetadataQueryOptions


def get_metadata_options_from_fields(fields: dict[str, Any]) -> MetadataOptions:
    """Convert a dict of requested metadata fields to MetadataOptions flags."""
    options = MetadataOptions.NONE
    if "created_at" in fields:
        options |= MetadataOptions.CREATED_AT
    if "created_by" in fields:
        options |= MetadataOptions.CREATED_BY
    if "updated_at" in fields or "_updated_at" in fields:
        options |= MetadataOptions.UPDATED_AT
    if "updated_by" in fields:
        options |= MetadataOptions.UPDATED_BY
    if "source" in fields or "_relation__source" in fields:
        options |= MetadataOptions.SOURCE
    if "owner" in fields or "_relation__owner" in fields:
        options |= MetadataOptions.OWNER
    if "is_protected" in fields:
        options |= MetadataOptions.IS_PROTECTED
    return options


def _extract_attribute_metadata_from_node_fields(node_fields: dict[str, Any]) -> MetadataOptions:
    """Extract attribute-level metadata options from nested node fields.

    This handles GraphQL query structures like:
        name {
            value
            updated_by { id }
            updated_at
        }

    Where `updated_by` and `updated_at` are attribute-level metadata.
    """
    attribute_metadata_options = MetadataOptions.NONE

    for field_properties_dict in node_fields.values():
        if not field_properties_dict or not isinstance(field_properties_dict, dict):
            continue

        # For attributes, metadata fields are at the same level as 'value'
        # Check if this looks like an attribute (has metadata fields directly)
        metadata_properties_dict = field_properties_dict

        # Extract metadata from attribute fields
        if "updated_at" in metadata_properties_dict or "_updated_at" in metadata_properties_dict:
            attribute_metadata_options |= MetadataOptions.UPDATED_AT
        if "updated_by" in metadata_properties_dict:
            attribute_metadata_options |= MetadataOptions.UPDATED_BY
        if "created_at" in metadata_properties_dict:
            attribute_metadata_options |= MetadataOptions.CREATED_AT
        if "created_by" in metadata_properties_dict:
            attribute_metadata_options |= MetadataOptions.CREATED_BY
        if "source" in metadata_properties_dict or "_relation__source" in metadata_properties_dict:
            attribute_metadata_options |= MetadataOptions.SOURCE
        if "owner" in metadata_properties_dict or "_relation__owner" in metadata_properties_dict:
            attribute_metadata_options |= MetadataOptions.OWNER

    return attribute_metadata_options


def build_metadata_query_options(
    node_metadata_fields: dict[str, Any] | None = None,
    relationship_metadata_fields: dict[str, Any] | None = None,
    node_fields: dict[str, Any] | None = None,
) -> MetadataQueryOptions:
    """Build MetadataQueryOptions from GraphQL extracted fields.

    Args:
        node_metadata_fields: Fields from the node_metadata section of a GraphQL query.
        relationship_metadata_fields: Fields from the relationship_metadata section.
        node_fields: The node fields dict to extract attribute-level metadata from.

    Returns:
        MetadataQueryOptions with appropriate flags set for each level.
    """
    node_level = get_metadata_options_from_fields(node_metadata_fields or {})
    relationship_level = get_metadata_options_from_fields(relationship_metadata_fields or {})
    attribute_level = _extract_attribute_metadata_from_node_fields(node_fields or {})

    return MetadataQueryOptions(
        node_level=node_level,
        attribute_level=attribute_level,
        relationship_level=relationship_level,
    )
