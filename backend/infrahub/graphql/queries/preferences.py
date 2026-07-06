from __future__ import annotations

from typing import TYPE_CHECKING

from graphene import Field

from infrahub.core import registry
from infrahub.core.preferences import MANAGE_GLOBAL_PREFERENCES_PERMISSION, Preference
from infrahub.exceptions import PermissionDeniedError
from infrahub.graphql.types.preferences import (
    EffectivePreferencesType,
    PreferenceSource,
    RawPreferencesType,
)

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext


def _require_authenticated(graphql_context: GraphqlContext) -> str:
    """Reject anonymous/unauthenticated sessions (fail-closed) and return the caller's account id.

    Raises:
        PermissionDeniedError: if there is no authenticated account session.

    """
    if not graphql_context.account_session or not graphql_context.account_session.authenticated:
        raise PermissionDeniedError("This operation requires an authenticated account")
    return graphql_context.account_session.account_id


def _global_owner_id() -> str:
    # Global preferences are the Preference row owned by the Root node; registry.id is the Root uuid
    # string — the same identifier space as an account id.
    return registry.id


async def resolve_effective_preferences(root: dict, info: GraphQLResolveInfo) -> dict:  # noqa: ARG001
    """Resolve the caller's effective preferences (user override → global default → DEFAULT).

    Per field: the USER override if set, else the GLOBAL default, else DEFAULT (value null → the
    client applies its built-in default). Open to any authenticated caller; the global row is read
    internally, never exposed as raw org values.
    """
    graphql_context: GraphqlContext = info.context
    account_id = _require_authenticated(graphql_context)

    # Account row + global row in ONE query; a missing row simply isn't in the map (reads never
    # create). StandardNode reads carry no branch filter, so this is branch-agnostic.
    preferences = await Preference.get_for_owners(db=graphql_context.db, owner_ids=[account_id, _global_owner_id()])
    user = preferences.get(account_id)
    global_ = preferences.get(_global_owner_id())

    def resolve(attribute_name: str) -> dict:
        user_value = getattr(user, attribute_name) if user else None
        if user_value is not None:
            return {"value": user_value, "source": PreferenceSource.USER}
        global_value = getattr(global_, attribute_name) if global_ else None
        if global_value is not None:
            return {"value": global_value, "source": PreferenceSource.GLOBAL}
        return {"value": None, "source": PreferenceSource.DEFAULT}

    return {"date_format": resolve("date_format"), "timezone": resolve("timezone")}


async def resolve_user_preferences(root: dict, info: GraphQLResolveInfo) -> dict:  # noqa: ARG001
    """Return the caller's OWN raw preferences (fields null where unset).

    Bound to account_session.account_id — there is no account argument, so account B can never read
    account A's row.
    """
    graphql_context: GraphqlContext = info.context
    account_id = _require_authenticated(graphql_context)

    user = await Preference.get_for_owner(db=graphql_context.db, owner_id=account_id)
    return {
        "date_format": user.date_format if user else None,
        "timezone": user.timezone if user else None,
    }


async def resolve_global_preferences(root: dict, info: GraphQLResolveInfo) -> dict:  # noqa: ARG001
    """Return the organisation-wide raw preferences (gated on manage_global_preferences).

    Super admins bypass via the permission manager; the gate raises BEFORE any read (fail-closed).
    """
    graphql_context: GraphqlContext = info.context
    _require_authenticated(graphql_context)
    graphql_context.active_permissions.raise_for_permission(permission=MANAGE_GLOBAL_PREFERENCES_PERMISSION)

    global_ = await Preference.get_for_owner(db=graphql_context.db, owner_id=_global_owner_id())
    return {
        "date_format": global_.date_format if global_ else None,
        "timezone": global_.timezone if global_ else None,
    }


# Three distinct root fields (registered in graphql/schema.py): each scope has its own typed shape and
# permission, rather than one query whose meaning varies by a `scope` argument.
InfrahubEffectivePreferences = Field(EffectivePreferencesType, resolver=resolve_effective_preferences, required=True)
InfrahubUserPreferences = Field(RawPreferencesType, resolver=resolve_user_preferences, required=True)
InfrahubGlobalPreferences = Field(RawPreferencesType, resolver=resolve_global_preferences, required=True)
