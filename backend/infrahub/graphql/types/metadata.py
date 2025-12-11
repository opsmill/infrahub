from __future__ import annotations

from graphene import DateTime, Field, ObjectType, String


class InfrahubStandardNodeMetaAccount(ObjectType):
    id = String(required=True)
    display_name = String(required=False)


class InfrahubStandardNodeMetaData(ObjectType):
    created_at = DateTime(required=False, description="Date/Time the object has been created")
    created_by = Field(InfrahubStandardNodeMetaAccount, required=False)
    updated_at = DateTime(
        required=False, description="Date/Time when the object was last modified by a user or a system task"
    )
    updated_by = Field(InfrahubStandardNodeMetaAccount, required=False)
