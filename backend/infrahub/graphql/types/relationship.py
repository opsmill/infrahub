from __future__ import annotations

from graphene import Field, List, NonNull, ObjectType, String


class RelationshipPeer(ObjectType):
    id = String(required=False)
    kind = String(required=False)


class Relationship(ObjectType):
    id = String(required=False)
    identifier = String(required=False)
    peers = List(NonNull(RelationshipPeer))


class RelationshipNode(ObjectType):
    node = Field(Relationship, required=True)
