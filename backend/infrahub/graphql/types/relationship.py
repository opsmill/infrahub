from __future__ import annotations

from graphene import DateTime, Field, List, NonNull, ObjectType, String


class RelationshipPeer(ObjectType):
    id = String(required=False)
    kind = String(required=False)


class InfrahubRelationshipMetaObject(ObjectType):
    updated_by = String(required=False, description="User that last modified the relationship")
    updated_at = DateTime(
        required=False,
        description="Date/Time when the relationship was last modified by a user or a system task",
    )


class Relationship(InfrahubRelationshipMetaObject):
    id = String(required=False)
    identifier = String(required=False)
    peers = List(NonNull(RelationshipPeer))


class RelationshipNode(ObjectType):
    node = Field(Relationship, required=True)
