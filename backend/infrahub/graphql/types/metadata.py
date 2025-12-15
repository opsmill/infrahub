from __future__ import annotations

from graphene import DateTime, ObjectType


class InfrahubStandardNodeMetaData(ObjectType):
    """Base metadata type for standard nodes.

    Note: created_by and updated_by fields are added dynamically by
    GraphQLSchemaManager._patch_static_types() to use the GenericAccount interface.
    """

    created_at = DateTime(required=False, description="Date/Time the object has been created")
    updated_at = DateTime(
        required=False, description="Date/Time when the object was last modified by a user or a system task"
    )
