from __future__ import annotations

from graphene import Boolean, DateTime, Field, InputObjectType, List, NonNull, ObjectType, String

from infrahub.graphql.types.enums import InfrahubOrderDirection


class InfrahubNodeMetadataOrder(InputObjectType):
    created_at = Field(InfrahubOrderDirection, required=False, description="Order by creation timestamp")
    updated_at = Field(InfrahubOrderDirection, required=False, description="Order by updated timestamp")


_ORDER_BY_DESCRIPTION = (
    "Ordering overrides support attributes (`name__value__desc`), "
    "relationship attributes (`owner__name__value`), or "
    "node metadata (`node_metadata__created_at__desc`). The trailing "
    "`__asc`/`__desc` is optional (default is ascending). When provided, "
    "fully replaces the schema's `order_by`. Cannot be combined with "
    "`node_metadata` in the same input."
)


class MetadataOrderInput(InputObjectType):
    """Order input restricted to node metadata fields.

    Used by GraphQL queries backed by StandardNode (e.g. Branch) where the underlying ordering
    surface is limited to `created_at` / `updated_at` and does not accept the broader `order_by`
    string grammar or a `disable` toggle.
    """

    node_metadata = Field(InfrahubNodeMetadataOrder, required=False, description="Order settings for branch metadata")


class OrderInput(InputObjectType):
    disable = Boolean(required=False)
    node_metadata = Field(InfrahubNodeMetadataOrder, required=False, description="Order settings for branch metadata")
    order_by = List(NonNull(String), required=False, description=_ORDER_BY_DESCRIPTION)


class InfrahubStandardNodeMetaData(ObjectType):
    """Base metadata type for standard nodes.

    Note: created_by and updated_by fields are added dynamically by
    GraphQLSchemaManager._patch_static_types() to use the GenericAccount interface.
    """

    created_at = DateTime(required=False, description="Date/Time the object has been created")
    updated_at = DateTime(
        required=False, description="Date/Time when the object was last modified by a user or a system task"
    )
