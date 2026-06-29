from __future__ import annotations

from typing import TYPE_CHECKING

from graphene import Boolean, Field, ObjectType, String

from infrahub.core.account import GlobalPermission
from infrahub.core.constants import GlobalPermissions, PermissionDecision
from infrahub.core.preferences import GlobalPreference, UserPreference
from infrahub.exceptions import PermissionDeniedError

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext

PREFERENCE_ATTRIBUTES = ("date_format", "timezone")

MANAGE_GLOBAL_PREFERENCES_PERMISSION = GlobalPermission(
    action=GlobalPermissions.MANAGE_GLOBAL_PREFERENCES.value,
    decision=PermissionDecision.ALLOW_ALL.value,
)


class EffectivePreferencesType(ObjectType):
    """Computed view merging the GlobalPreference singleton with the caller's UserPreference.

    Scalar fields on purpose: this is not a node, `null` means "no opinion stored" and the
    client applies its own built-in default. `can_edit_global_preferences` drives the
    "Organisation defaults" tab; the backend remains the source of truth.
    """

    date_format = Field(String, required=False)
    timezone = Field(String, required=False)
    can_edit_global_preferences = Field(Boolean, required=True)


async def resolve_effective_preferences(
    root: dict,  # noqa: ARG001
    info: GraphQLResolveInfo,
) -> dict:
    graphql_context: GraphqlContext = info.context

    if not graphql_context.account_session:
        raise PermissionDeniedError("This operation requires an authenticated account")

    # Account-scoped view: reject anonymous sessions, whose account_id is empty/untrusted.
    # Unlike resolve_account_tokens this stays open to API-token sessions (their account_id is
    # trusted); the JWT-only guard there exists to keep token management off API tokens.
    if not graphql_context.account_session.authenticated:
        raise PermissionDeniedError("This operation requires an authenticated account")

    db = graphql_context.db

    global_preference = await GlobalPreference.get_global(db=db)
    user_preference = await UserPreference.get_for_account(db=db, account_id=graphql_context.account_session.account_id)

    response: dict[str, str | bool | None] = {}
    for attribute_name in PREFERENCE_ATTRIBUTES:
        user_value: str | None = getattr(user_preference, attribute_name) if user_preference else None
        global_value: str | None = getattr(global_preference, attribute_name)
        response[attribute_name] = user_value if user_value is not None else global_value

    response["can_edit_global_preferences"] = graphql_context.active_permissions.has_permission(
        permission=MANAGE_GLOBAL_PREFERENCES_PERMISSION
    )

    return response


EffectivePreferences = Field(
    EffectivePreferencesType,
    resolver=resolve_effective_preferences,
    required=True,
)
