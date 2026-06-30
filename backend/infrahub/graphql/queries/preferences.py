from __future__ import annotations

from typing import TYPE_CHECKING

from graphene import Boolean, Field, ObjectType, String

from infrahub.core.preferences import MANAGE_GLOBAL_PREFERENCES_PERMISSION, GlobalPreference, UserPreference
from infrahub.exceptions import PermissionDeniedError

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext

PREFERENCE_ATTRIBUTES = ("date_format", "timezone")


class EffectivePreferencesType(ObjectType):
    """Computed view merging the GlobalPreference singleton with the caller's UserPreference.

    Scalar fields on purpose: this is not a node, `null` means "no opinion stored" and the
    client applies its own built-in default. `can_edit_global_preferences` drives the
    "Organisation defaults" tab; the backend remains the source of truth.

    The raw `user_*` / `global_*` values are exposed alongside the merged values so the
    frontend can render inherited-value hints and edit the right thing: the "Organisation
    defaults" editor edits `global_*` (not the merged value, which an admin's own override
    would otherwise corrupt), and the user "Preferences" tab uses `global_*` as the inherited
    placeholder while `user_*` populates the form with the caller's own override.

    Privacy: `global_*` is org-wide and safe to expose to any authenticated account; `user_*`
    is the caller's OWN override only (the query is account-bound to account_session.account_id),
    so no account ever sees another account's user preferences.
    """

    date_format = Field(String, required=False)
    timezone = Field(String, required=False)
    user_date_format = Field(String, required=False)
    user_timezone = Field(String, required=False)
    global_date_format = Field(String, required=False)
    global_timezone = Field(String, required=False)
    can_edit_global_preferences = Field(Boolean, required=True)


async def resolve_effective_preferences(
    root: dict,  # noqa: ARG001
    info: GraphQLResolveInfo,
) -> dict:
    graphql_context: GraphqlContext = info.context

    # Account-scoped view: reject anonymous sessions, whose account_id is empty/untrusted.
    # Unlike resolve_account_tokens this stays open to API-token sessions (their account_id is
    # trusted); the JWT-only guard there exists to keep token management off API tokens.
    if not graphql_context.account_session or not graphql_context.account_session.authenticated:
        raise PermissionDeniedError("This operation requires an authenticated account")

    db = graphql_context.db

    # StandardNode reads (GetList/GetItem) carry no branch filter, so these lookups are global /
    # branch-agnostic regardless of the request branch on graphql_context.db (same as Branch's own
    # resolver). Preferences intentionally have no per-branch semantics.
    global_preference = await GlobalPreference.get_global(db=db)
    user_preference = await UserPreference.get_for_account(db=db, account_id=graphql_context.account_session.account_id)

    response: dict[str, str | bool | None] = {}
    for attribute_name in PREFERENCE_ATTRIBUTES:
        # user_* = caller's OWN override (or null); global_* = the org-wide singleton's value
        # (or null); the merged value is user-else-global. global_* is fine to expose to any
        # authenticated account; user_* is account-bound so privacy is preserved.
        user_value: str | None = getattr(user_preference, attribute_name) if user_preference else None
        global_value: str | None = getattr(global_preference, attribute_name)
        response[attribute_name] = user_value if user_value is not None else global_value
        response[f"user_{attribute_name}"] = user_value
        response[f"global_{attribute_name}"] = global_value

    response["can_edit_global_preferences"] = graphql_context.active_permissions.has_permission(
        permission=MANAGE_GLOBAL_PREFERENCES_PERMISSION
    )

    return response


EffectivePreferences = Field(
    EffectivePreferencesType,
    resolver=resolve_effective_preferences,
    required=True,
)
