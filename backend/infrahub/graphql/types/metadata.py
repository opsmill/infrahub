from __future__ import annotations

from graphene import Boolean, DateTime, Field, InputField, InputObjectType, List, NonNull, ObjectType, String

from infrahub.constants.enums import OrderDirection
from infrahub.graphql.types.enums import InfrahubOrderDirection


class InfrahubNodeMetadataOrder(InputObjectType):
    created_at = Field(InfrahubOrderDirection, required=False, description="Order by creation timestamp")
    updated_at = Field(InfrahubOrderDirection, required=False, description="Order by updated timestamp")


_ORDER_BY_FIELD_DESCRIPTION = (
    "Field to order by: an attribute (`name__value`), a relationship attribute "
    "(`owner__name__value`), or node metadata (`node_metadata__created_at`). "
    "The field carries no direction suffix; use `direction` for that."
)

_ORDER_BY_DESCRIPTION = (
    "Ordered list of fields to order results by. When provided, fully replaces the schema's "
    "`order_by`. Cannot be combined with the deprecated `node_metadata` in the same input."
)

_NODE_METADATA_DEPRECATION = (
    "Use `by` with the `node_metadata__created_at` / `node_metadata__updated_at` fields instead."
)


class OrderByItem(InputObjectType):
    field = String(required=True, description=_ORDER_BY_FIELD_DESCRIPTION)
    direction = InfrahubOrderDirection(
        required=False, default_value=OrderDirection.ASC.value, description="Sort direction (default ASC)"
    )


class MetadataOrderInput(InputObjectType):
    """Order input restricted to node metadata fields.

    Used by GraphQL queries backed by StandardNode (e.g. Branch) where the underlying ordering
    surface is limited to `created_at` / `updated_at` and does not accept the broader `by`
    field grammar or a `disable` toggle.
    """

    node_metadata = Field(InfrahubNodeMetadataOrder, required=False, description="Order settings for branch metadata")


class OrderInput(InputObjectType):
    disable = Boolean(required=False)
    node_metadata = InputField(
        InfrahubNodeMetadataOrder,
        required=False,
        description="Order settings for node metadata",
        deprecation_reason=_NODE_METADATA_DEPRECATION,
    )
    by = List(NonNull(OrderByItem), required=False, description=_ORDER_BY_DESCRIPTION)


class InfrahubStandardNodeMetaData(ObjectType):
    """Base metadata type for standard nodes.

    Note: created_by and updated_by fields are added dynamically by
    GraphQLSchemaManager._patch_static_types() to use the GenericAccount interface.
    """

    created_at = DateTime(required=False, description="Date/Time the object has been created")
    updated_at = DateTime(
        required=False, description="Date/Time when the object was last modified by a user or a system task"
    )
