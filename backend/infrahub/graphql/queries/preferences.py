from __future__ import annotations

from typing import TYPE_CHECKING

from graphene import Field

from infrahub.core.preferences import MANAGE_GLOBAL_PREFERENCES_PERMISSION, Preference, global_owner_id
from infrahub.graphql.types.preferences import (
    EffectivePreferencesType,
    PreferenceSource,
    RawPreferencesType,
)

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext


async def resolve_effective_preferences(root: dict, info: GraphQLResolveInfo) -> dict:  # noqa: ARG001
    """Resolve the caller's effective preferences (user override → global default → DEFAULT).

    Per field: the USER override if set, else the GLOBAL default, else DEFAULT (value null → the
    client applies its built-in default). Open to any authenticated caller; the global row is read
    internally, never exposed as raw org values.
    """
    graphql_context: GraphqlContext = info.context
    account_id = graphql_context.active_account_session.account_id
    global_id = global_owner_id()

    # Account row + global row in ONE query; a missing row simply isn't in the map (reads never
    # create). StandardNode reads carry no branch filter, so this is branch-agnostic.
    preferences = await Preference.get_for_owners(db=graphql_context.db, owner_ids=[account_id, global_id])
    user = preferences.get(account_id)
    global_ = preferences.get(global_id)

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
    account_id = graphql_context.active_account_session.account_id

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
    graphql_context.active_permissions.raise_for_permission(permission=MANAGE_GLOBAL_PREFERENCES_PERMISSION)

    global_ = await Preference.get_for_owner(db=graphql_context.db, owner_id=global_owner_id())
    return {
        "date_format": global_.date_format if global_ else None,
        "timezone": global_.timezone if global_ else None,
    }


# Three distinct root fields (registered in graphql/schema.py): each scope has its own typed shape and
# permission, rather than one query whose meaning varies by a `scope` argument.
InfrahubEffectivePreferences = Field(EffectivePreferencesType, resolver=resolve_effective_preferences, required=True)
InfrahubUserPreferences = Field(RawPreferencesType, resolver=resolve_user_preferences, required=True)
InfrahubGlobalPreferences = Field(RawPreferencesType, resolver=resolve_global_preferences, required=True)
