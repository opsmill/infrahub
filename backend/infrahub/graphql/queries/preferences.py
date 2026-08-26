from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Field

from infrahub.core.preferences.constants import GLOBAL_OWNER_ID
from infrahub.core.preferences.models import EffectivePreferences, ResolvedPreference
from infrahub.core.preferences.permissions import MANAGE_GLOBAL_PREFERENCES_PERMISSION
from infrahub.core.preferences.repository import PreferenceRepository
from infrahub.graphql.types.preferences import (
    EffectivePreferencesType,
    RawPreferencesType,
)

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext


def _effective_field(*, resolved: ResolvedPreference[Any], inherited: ResolvedPreference[Any]) -> dict[str, Any]:
    """Plain dicts, not ResolvedPreference: the frozen dataclass has no `inherited` attribute for graphene to find.

    Keyword-only on purpose: both arguments have the same type, so transposing them would type-check
    while reporting a USER-sourced value as the inherited layer, which `inherited` promises never to do.
    """
    return {
        "value": resolved.value,
        "source": resolved.source,
        "inherited": {"value": inherited.value, "source": inherited.source},
    }


async def resolve_effective_preferences(root: dict, info: GraphQLResolveInfo) -> dict:  # noqa: ARG001
    """Resolve the caller's effective preferences (user override → global default → DEFAULT).

    Open to any authenticated caller. The global layer's values ARE reported here — labelled GLOBAL
    when nothing shadows them, and as the `inherited` layer when a user override does. Since
    `inherited` is returned for every field, this query now discloses the same two org values that
    the gated `InfrahubGlobalPreferences` returns. That is deliberate:
    MANAGE_GLOBAL_PREFERENCES_PERMISSION gates the *management* surface — the ability to read the org
    row as an editable scope and write it — not the confidentiality of two display settings a caller
    could already see by clearing their own override.
    """
    graphql_context: GraphqlContext = info.context
    account_id = graphql_context.active_account_session.account_id
    global_id = GLOBAL_OWNER_ID

    # StandardNode reads carry no branch filter, so this is branch-agnostic.
    repository = PreferenceRepository(db=graphql_context.db)
    preferences = await repository.get_for_owners(owner_ids={account_id, global_id})
    effective = EffectivePreferences(user=preferences.get(account_id), global_=preferences.get(global_id))
    return {
        "date_format": _effective_field(
            resolved=effective.resolved_date_format(), inherited=effective.inherited_date_format()
        ),
        "timezone": _effective_field(resolved=effective.resolved_timezone(), inherited=effective.inherited_timezone()),
    }


async def resolve_user_preferences(root: dict, info: GraphQLResolveInfo) -> dict:  # noqa: ARG001
    """Return the caller's OWN raw preferences (fields null where unset).

    Bound to account_session.account_id — there is no account argument, so account B can never read
    account A's row.
    """
    graphql_context: GraphqlContext = info.context
    account_id = graphql_context.active_account_session.account_id

    user = await PreferenceRepository(db=graphql_context.db).get_for_owner(owner_id=account_id)
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

    global_ = await PreferenceRepository(db=graphql_context.db).get_for_owner(owner_id=GLOBAL_OWNER_ID)
    return {
        "date_format": global_.date_format if global_ else None,
        "timezone": global_.timezone if global_ else None,
    }


InfrahubEffectivePreferences = Field(EffectivePreferencesType, resolver=resolve_effective_preferences, required=True)
InfrahubUserPreferences = Field(RawPreferencesType, resolver=resolve_user_preferences, required=True)
InfrahubGlobalPreferences = Field(RawPreferencesType, resolver=resolve_global_preferences, required=True)
