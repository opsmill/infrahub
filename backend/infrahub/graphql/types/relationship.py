from __future__ import annotations

from graphene import Field, List, NonNull, ObjectType, String


class RelationshipPeer(ObjectType):
    id = String(required=False)
    kind = String(required=False)


class InfrahubRelationshipMetaObject(ObjectType):
    updated_by = String(required=False, description="UUID of the user that last modified the attribute or relationship")
    updated_at = String(
        required=False,
        description="Date/Time when the attribute or relationship was last modified by a user or a system task",
    )


class InfrahubRelationshipMeta(ObjectType):
    meta = Field(InfrahubRelationshipMetaObject, required=False)


class Relationship(InfrahubRelationshipMeta):
    id = String(required=False)
    identifier = String(required=False)
    peers = List(NonNull(RelationshipPeer))


class RelationshipNode(ObjectType):
    node = Field(Relationship, required=True)
