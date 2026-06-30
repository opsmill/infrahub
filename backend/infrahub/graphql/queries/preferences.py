from __future__ import annotations

from typing import TYPE_CHECKING

from graphene import Boolean, Enum, Field, List, NonNull, ObjectType, String

from infrahub.core.preferences import MANAGE_GLOBAL_PREFERENCES_PERMISSION, GlobalPreference, UserPreference
from infrahub.exceptions import PermissionDeniedError

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext

PREFERENCE_ATTRIBUTES = ("date_format", "timezone")


class PreferenceSource(Enum):
    """Where a resolved preference value came from.

    USER    = the caller's OWN override.
    GLOBAL  = the org-wide GlobalPreference singleton.
    DEFAULT = nothing is stored anywhere; the client applies its built-in default.
    """

    USER = "user"
    GLOBAL = "global"
    DEFAULT = "default"


class PreferenceEntryType(ObjectType):
    """A single resolved preference: its key, the resolved value, and where it came from.

    `value` is null only when `source` is DEFAULT (nothing stored anywhere). Consumers read
    `value` + `source` directly and never compare user/global themselves.
    """

    key = Field(String, required=True)
    value = Field(String, required=False)
    source = Field(PreferenceSource, required=True)


class GlobalPreferencesType(ObjectType):
    """Raw org-wide defaults from the GlobalPreference singleton (admin-only org-defaults editor).

    Exposed separately from the resolved `preferences` so the "Organisation defaults" editor
    edits the org-wide default rather than an admin's personal override. Safe for any
    authenticated account: it is org-wide, never account-bound.
    """

    date_format = Field(String, required=False)
    timezone = Field(String, required=False)


class EffectivePreferencesType(ObjectType):
    """Computed view merging the GlobalPreference singleton with the caller's UserPreference.

    `preferences` is the authoritative per-key resolution (value + source); `global` exposes the
    raw org defaults for the admin editor; `can_edit_global_preferences` gates that editor.

    Privacy: `global` is org-wide and safe to expose to any authenticated account; the resolved
    `preferences` value is account-bound (the query reads account_session.account_id only), so no
    account ever sees another account's user preferences.
    """

    preferences = Field(List(of_type=NonNull(PreferenceEntryType), required=True), required=True)
    # `global` is a Python keyword, so the attribute is `global_values` and the GraphQL field
    # name is pinned to `global` via graphene's `name=`.
    global_values = Field(GlobalPreferencesType, required=True, name="global")
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

    preferences: list[dict[str, str | None]] = []
    for attribute_name in PREFERENCE_ATTRIBUTES:
        # user_value = caller's OWN override (or null); global_value = the org-wide singleton's
        # value (or null). The resolved value is user-else-global, with an explicit source so
        # consumers never compare the two themselves.
        user_value: str | None = getattr(user_preference, attribute_name) if user_preference else None
        global_value: str | None = getattr(global_preference, attribute_name)
        if user_value is not None:
            value, source = user_value, PreferenceSource.USER
        elif global_value is not None:
            value, source = global_value, PreferenceSource.GLOBAL
        else:
            value, source = None, PreferenceSource.DEFAULT
        preferences.append({"key": attribute_name, "value": value, "source": source})

    return {
        "preferences": preferences,
        # Raw org-wide defaults for the admin org-defaults editor (never account-bound).
        "global_values": {attr: getattr(global_preference, attr) for attr in PREFERENCE_ATTRIBUTES},
        "can_edit_global_preferences": graphql_context.active_permissions.has_permission(
            permission=MANAGE_GLOBAL_PREFERENCES_PERMISSION
        ),
    }


EffectivePreferences = Field(
    EffectivePreferencesType,
    resolver=resolve_effective_preferences,
    required=True,
)
