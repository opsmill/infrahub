from __future__ import annotations

from graphene import DateTime, ObjectType, String


class InfrahubNodeMetaData(ObjectType):
    created_at = DateTime(required=False, description="Date/Time the object has been created")
    created_by = String(
        required=False, description="UUID of the user that created the object, even if the user is later deleted"
    )
    updated_by = String(
        required=False, description="UUID of the user that last modified the object, even if the user is later deleted"
    )
    updated_at = DateTime(
        required=False, description="Date/Time when the object was last modified by a user or a system task"
    )


class InfrahubRelationshipMetaData(ObjectType):
    created_at = DateTime(required=False, description="Date/Time the object has been created")
    created_by = String(
        required=False, description="UUID of the user that created the object, even if the user is later deleted"
    )
    updated_by = String(
        required=False, description="UUID of the user that last modified the object, even if the user is later deleted"
    )
    updated_at = DateTime(
        required=False, description="Date/Time when the object was last modified by a user or a system task"
    )
