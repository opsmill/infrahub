from __future__ import annotations

from typing import TYPE_CHECKING

from graphene import Argument, Boolean, Enum, Field, List, NonNull, ObjectType, String

from infrahub.core.preferences import (
    DATE_FORMAT_KEYS,
    MANAGE_GLOBAL_PREFERENCES_PERMISSION,
    GlobalPreference,
    UserPreference,
)
from infrahub.exceptions import PermissionDeniedError

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext

PREFERENCE_ATTRIBUTES = ("date_format", "timezone")


# Scope string values. Kept as plain constants (not read off the graphene Enum members via
# `.value`) because graphene's Enum metaclass makes static type-checkers treat members as `str`,
# which breaks `.value`. Graphene passes these string values to the resolver/mutation at runtime.
SCOPE_EFFECTIVE = "effective"
SCOPE_GLOBAL = "global"
SCOPE_USER = "user"


class PreferenceScope(Enum):
    """Which axis of the preferences store a read/write operates on.

    EFFECTIVE = the caller's resolved view (user-else-global-else-default), read-only.
    GLOBAL    = the org-wide GlobalPreference singleton's raw values (manage_global_preferences).
    USER      = the caller's OWN raw UserPreference values (account-bound, never another account).
    """

    EFFECTIVE = SCOPE_EFFECTIVE
    GLOBAL = SCOPE_GLOBAL
    USER = SCOPE_USER


# The stored `date_format` is a SEMANTIC key (e.g. ISO_DATETIME), not a rendering pattern: each
# client maps the key to its own formatter (web -> date-fns, backend -> strftime). Typing the write
# arg as this enum validates the value at the GraphQL layer for free — an unknown key is rejected
# before the resolver runs. Built from the canonical key list so the enum and the render map (see
# core.preferences.formats) can never drift. The READ side returns the key as a plain String in the
# generic key/value entry list, since `timezone` shares that field and is free-form.
DateFormat = Enum("DateFormat", [(key, key) for key in DATE_FORMAT_KEYS])


class PreferenceSource(Enum):
    """Where a resolved preference value came from.

    USER    = the caller's OWN override (or a raw USER-scope read).
    GLOBAL  = the org-wide GlobalPreference singleton (or a raw GLOBAL-scope read).
    DEFAULT = nothing is stored anywhere; the client applies its built-in default.
    """

    USER = "user"
    GLOBAL = "global"
    DEFAULT = "default"


class PreferenceEntryType(ObjectType):
    """A single preference: its key, the value, and where it came from.

    For EFFECTIVE reads `value` is null only when `source` is DEFAULT. For raw USER/GLOBAL reads
    `value` may be null (nothing stored for that key) while `source` still reports the scope.
    """

    key = Field(String, required=True)
    value = Field(String, required=False)
    source = Field(PreferenceSource, required=True)


class PreferencesType(ObjectType):
    """Per-key preference entries for the requested scope plus the org-defaults edit gate.

    Privacy: EFFECTIVE and USER entries are account-bound (the resolver reads only
    account_session.account_id), so no account ever sees another account's user preferences.
    GLOBAL entries are org-wide and returned only after the manage_global_preferences gate.
    """

    preferences = Field(List(of_type=NonNull(PreferenceEntryType), required=True), required=True)
    can_edit_global_preferences = Field(Boolean, required=True)


def _entry(key: str, value: str | None, source: object) -> dict:
    # `source` is a PreferenceSource member; graphene serialises it to the GraphQL enum name.
    return {"key": key, "value": value, "source": source}


async def resolve_preferences(
    root: dict,  # noqa: ARG001
    info: GraphQLResolveInfo,
    scope: str = SCOPE_EFFECTIVE,
) -> dict:
    graphql_context: GraphqlContext = info.context

    # Fail-closed: reject anonymous/unauthenticated sessions before any scope-specific logic.
    # Their account_id is empty/untrusted. Stays open to API-token sessions (trusted account_id),
    # matching the effective read's original guard.
    if not graphql_context.account_session or not graphql_context.account_session.authenticated:
        raise PermissionDeniedError("This operation requires an authenticated account")

    db = graphql_context.db
    account_id = graphql_context.account_session.account_id

    # Computed for every scope so the client can gate the org-defaults editor regardless of which
    # view it just read.
    can_edit_global_preferences = graphql_context.active_permissions.has_permission(
        permission=MANAGE_GLOBAL_PREFERENCES_PERMISSION
    )

    preferences: list[dict]

    if scope == SCOPE_EFFECTIVE:
        # Any authenticated caller. The global singleton is read INTERNALLY (no permission gate):
        # the caller only ever gets their own resolved view, never the raw org values as such.
        # StandardNode reads carry no branch filter, so these lookups are branch-agnostic.
        global_preference = await GlobalPreference.get_global(db=db)
        user_preference = await UserPreference.get_for_account(db=db, account_id=account_id)
        preferences = []
        for attribute_name in PREFERENCE_ATTRIBUTES:
            user_value: str | None = getattr(user_preference, attribute_name) if user_preference else None
            global_value: str | None = getattr(global_preference, attribute_name)
            if user_value is not None:
                preferences.append(_entry(attribute_name, user_value, PreferenceSource.USER))
            elif global_value is not None:
                preferences.append(_entry(attribute_name, global_value, PreferenceSource.GLOBAL))
            else:
                preferences.append(_entry(attribute_name, None, PreferenceSource.DEFAULT))

    elif scope == SCOPE_USER:
        # The caller's OWN raw values only, bound to account_session.account_id via get_for_account.
        # There is no account argument, so account B can never read account A's row. A missing row
        # yields null values (source still USER).
        user_preference = await UserPreference.get_for_account(db=db, account_id=account_id)
        preferences = [
            _entry(
                attribute_name,
                getattr(user_preference, attribute_name) if user_preference else None,
                PreferenceSource.USER,
            )
            for attribute_name in PREFERENCE_ATTRIBUTES
        ]

    elif scope == SCOPE_GLOBAL:
        # Gated: raise BEFORE reading/returning any raw org value (fail-closed). Super admins bypass
        # via the permission manager.
        graphql_context.active_permissions.raise_for_permission(permission=MANAGE_GLOBAL_PREFERENCES_PERMISSION)
        global_preference = await GlobalPreference.get_global(db=db)
        preferences = [
            _entry(attribute_name, getattr(global_preference, attribute_name), PreferenceSource.GLOBAL)
            for attribute_name in PREFERENCE_ATTRIBUTES
        ]

    else:  # pragma: no cover - graphene enum coercion guarantees a known member.
        raise PermissionDeniedError(f"Unsupported preference scope: {scope}")

    return {"preferences": preferences, "can_edit_global_preferences": can_edit_global_preferences}


Preferences = Field(
    PreferencesType,
    scope=Argument(PreferenceScope, default_value=SCOPE_EFFECTIVE),
    resolver=resolve_preferences,
    required=True,
)
