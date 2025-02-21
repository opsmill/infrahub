from __future__ import annotations

from graphene import InputObjectType, ObjectType, String


class IdentifierInput(InputObjectType):
    id = String(required=True, description="The ID of the requested object")


class RelatedNode(ObjectType):
    id = String(required=True, description="The ID of the requested object")
    kind = String(required=True, description="The ID of the requested object")
    display_label = String(required=False, description="The display label of the node if present")
