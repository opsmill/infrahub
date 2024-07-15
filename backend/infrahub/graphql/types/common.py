from __future__ import annotations

from graphene import InputObjectType, String


class IdentifierInput(InputObjectType):
    id = String(required=True, description="The ID of the requested object")
