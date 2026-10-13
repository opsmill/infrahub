from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import POOL_TRACKED_ATTRIBUTE_KINDS, MetadataOptions
from infrahub.core.metadata.model import MetadataQueryOptions
from infrahub.core.schema import GenericSchema

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch


def get_metadata_options_from_fields(fields: dict[str, Any]) -> MetadataOptions:
    """Convert a dict of requested metadata fields to MetadataOptions flags."""
    options = MetadataOptions.NONE
    if "created_at" in fields:
        options |= MetadataOptions.CREATED_AT
    if "created_by" in fields:
        options |= MetadataOptions.CREATED_BY
    if "updated_at" in fields:
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


def _extract_attribute_metadata_from_node_fields(
    node_fields: dict[str, Any], schema: MainSchemaTypes | None = None, schema_branch: SchemaBranch | None = None
) -> MetadataOptions:
    """Extract attribute-level metadata options from nested node fields.

    This handles GraphQL query structures like:
        name {
            value
            updated_by { id }
            updated_at
        }

    Where `updated_by` and `updated_at` are attribute-level metadata. A `source` selection on an attribute a
    number pool can track also asks for the tracking pool. A field a generic does not declare is looked up on
    its implementers through the schema branch; without a schema, any `source` selection asks for the pool.
    """
    attribute_metadata_options = MetadataOptions.NONE

    for field_name, field_properties_dict in node_fields.items():
        if not field_properties_dict or not isinstance(field_properties_dict, dict):
            continue

        # For attributes, metadata fields are at the same level as 'value'
        # Check if this looks like an attribute (has metadata fields directly)
        metadata_properties_dict = field_properties_dict

        # Extract metadata from attribute fields
        if "updated_at" in metadata_properties_dict:
            attribute_metadata_options |= MetadataOptions.UPDATED_AT
        if "updated_by" in metadata_properties_dict:
            attribute_metadata_options |= MetadataOptions.UPDATED_BY
        if "created_at" in metadata_properties_dict:
            attribute_metadata_options |= MetadataOptions.CREATED_AT
        if "created_by" in metadata_properties_dict:
            attribute_metadata_options |= MetadataOptions.CREATED_BY
        if "source" in metadata_properties_dict or "_relation__source" in metadata_properties_dict:
            attribute_metadata_options |= MetadataOptions.SOURCE
            if _may_be_pool_tracked(field_name=field_name, schema=schema, schema_branch=schema_branch):
                attribute_metadata_options |= MetadataOptions.TRACKING_POOL
        if "owner" in metadata_properties_dict or "_relation__owner" in metadata_properties_dict:
            attribute_metadata_options |= MetadataOptions.OWNER

    return attribute_metadata_options


def _may_be_pool_tracked(field_name: str, schema: MainSchemaTypes | None, schema_branch: SchemaBranch | None) -> bool:
    """Whether the field is an attribute a number pool can track, on the schema or on an implementer of it.

    Inline fragments are flattened before the node's kind is known, so a field a generic does not declare
    is looked up on the generic's implementers; without the schema branch to find them it is taken as
    trackable.
    """
    if schema is None:
        return True
    attribute = schema.get_attribute_or_none(name=field_name)
    if attribute is not None:
        return attribute.kind in POOL_TRACKED_ATTRIBUTE_KINDS
    if not isinstance(schema, GenericSchema):
        return False
    if schema_branch is None:
        return True
    for implementer_kind in schema.used_by:
        implementer_attribute = schema_branch.get(name=implementer_kind, duplicate=False).get_attribute_or_none(
            name=field_name
        )
        if implementer_attribute is not None and implementer_attribute.kind in POOL_TRACKED_ATTRIBUTE_KINDS:
            return True
    return False


def build_metadata_query_options(
    node_metadata_fields: dict[str, Any] | None = None,
    relationship_metadata_fields: dict[str, Any] | None = None,
    node_fields: dict[str, Any] | None = None,
    schema: MainSchemaTypes | None = None,
    schema_branch: SchemaBranch | None = None,
) -> MetadataQueryOptions:
    """Build MetadataQueryOptions from GraphQL extracted fields.

    Args:
        node_metadata_fields: Fields from the node_metadata section of a GraphQL query.
        relationship_metadata_fields: Fields from the relationship_metadata section.
        node_fields: The node fields dict to extract attribute-level metadata from.
        schema: The schema of the nodes the fields are read on, which scopes the tracking pool read to the
            attributes a number pool can track.
        schema_branch: The schema branch the schema belongs to, used to find the implementers of a generic.

    Returns:
        MetadataQueryOptions with appropriate flags set for each level.

    """
    node_level = get_metadata_options_from_fields(node_metadata_fields or {})
    relationship_level = get_metadata_options_from_fields(relationship_metadata_fields or {})
    attribute_level = _extract_attribute_metadata_from_node_fields(
        node_fields or {}, schema=schema, schema_branch=schema_branch
    )

    return MetadataQueryOptions(
        node_level=node_level,
        attribute_level=attribute_level,
        relationship_level=relationship_level,
    )
