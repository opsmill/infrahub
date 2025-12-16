from __future__ import annotations

from graphene import Boolean, DateTime, Field, InputObjectType, ObjectType

from infrahub.graphql.types.enums import InfrahubOrderDirection


class InfrahubNodeMetadataOrder(InputObjectType):
    created_at = Field(InfrahubOrderDirection, required=False, description="Order by creation timestamp")
    updated_at = Field(InfrahubOrderDirection, required=False, description="Order by updated timestamp")


class OrderInput(InputObjectType):
    disable = Boolean(required=False)
    node_metadata = Field(InfrahubNodeMetadataOrder, required=False, description="Order settings for branch metadata")


class InfrahubStandardNodeMetaData(ObjectType):
    """Base metadata type for standard nodes.

    Note: created_by and updated_by fields are added dynamically by
    GraphQLSchemaManager._patch_static_types() to use the GenericAccount interface.
    """

    created_at = DateTime(required=False, description="Date/Time the object has been created")
    updated_at = DateTime(
        required=False, description="Date/Time when the object was last modified by a user or a system task"
    )
