from __future__ import annotations

from typing import TYPE_CHECKING

from graphene import Field, ObjectType, String

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.node import Node
    from infrahub.graphql.initialization import GraphqlContext

PREFERENCE_ATTRIBUTES = ("date_format", "timezone")


class EffectivePreferencesType(ObjectType):
    """Computed view merging the CoreGlobalPreference singleton with the caller's CoreUserPreference.

    Scalar fields on purpose: this is not a node, null means "no opinion stored" and the
    client applies its own built-in default.
    """

    date_format = Field(String, required=False)
    timezone = Field(String, required=False)


async def resolve_effective_preferences(
    root: dict,  # noqa: ARG001
    info: GraphQLResolveInfo,
) -> dict:
    graphql_context: GraphqlContext = info.context

    if not graphql_context.account_session:
        raise ValueError("An account_session is mandatory to execute this query")

    db = graphql_context.db
    branch = graphql_context.branch

    global_results = await NodeManager.query(db=db, schema=InfrahubKind.GLOBALPREFERENCE, branch=branch, limit=1)
    global_preference: Node | None = global_results[0] if global_results else None

    user_results = await NodeManager.query(
        db=db,
        schema=InfrahubKind.USERPREFERENCE,
        filters={"account__ids": [graphql_context.account_session.account_id]},
        branch=branch,
        limit=1,
    )
    user_preference: Node | None = user_results[0] if user_results else None

    response: dict[str, str | None] = {}
    for attribute_name in PREFERENCE_ATTRIBUTES:
        value: str | None = None
        if user_preference is not None and getattr(user_preference, attribute_name).value is not None:
            value = getattr(user_preference, attribute_name).value
        elif global_preference is not None:
            value = getattr(global_preference, attribute_name).value
        response[attribute_name] = value

    return response


EffectivePreferences = Field(
    EffectivePreferencesType,
    resolver=resolve_effective_preferences,
    required=True,
)
