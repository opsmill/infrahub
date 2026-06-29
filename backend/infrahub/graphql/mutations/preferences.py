from __future__ import annotations

from typing import TYPE_CHECKING

from graphene import Boolean, Mutation, String
from typing_extensions import Self

from infrahub.core.account import GlobalPermission
from infrahub.core.constants import GlobalPermissions, PermissionDecision
from infrahub.core.preferences import GlobalPreference, UserPreference
from infrahub.database import retry_db_transaction
from infrahub.exceptions import PermissionDeniedError

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from ..initialization import GraphqlContext

MANAGE_GLOBAL_PREFERENCES_PERMISSION = GlobalPermission(
    action=GlobalPermissions.MANAGE_GLOBAL_PREFERENCES.value,
    decision=PermissionDecision.ALLOW_ALL.value,
)

# Sentinel distinguishing "argument not provided" (leave field unchanged) from an explicit
# `null` (reset the field). Graphene passes the GraphQL argument only when it is present.
_UNSET = object()


class InfrahubUserPreferenceUpsert(Mutation):
    """Upsert the calling account's own UserPreference row.

    The mutation never accepts an account/target argument: it always operates on the row owned by
    `account_session.account_id`, so there is no path to write another user's preferences. The row
    is lazily created on first write. A field passed as explicit `null` resets it.
    """

    class Arguments:
        date_format = String(required=False)
        timezone = String(required=False)

    ok = Boolean()
    date_format = String(required=False)
    timezone = String(required=False)

    @classmethod
    @retry_db_transaction(name="user_preference_upsert")
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        date_format: str | None = _UNSET,  # type: ignore[assignment]
        timezone: str | None = _UNSET,  # type: ignore[assignment]
    ) -> Self:
        graphql_context: GraphqlContext = info.context

        if not graphql_context.account_session or not graphql_context.account_session.authenticated:
            raise PermissionDeniedError("This operation requires an authenticated account")

        account_id = graphql_context.account_session.account_id

        async with graphql_context.db.start_transaction() as db:
            obj = await UserPreference.get_for_account(db=db, account_id=account_id)
            if obj is None:
                obj = UserPreference(account_id=account_id)

            if date_format is not _UNSET:
                obj.date_format = date_format
            if timezone is not _UNSET:
                obj.timezone = timezone

            await obj.save(db=db, user_id=account_id)

        return cls(ok=True, date_format=obj.date_format, timezone=obj.timezone)  # type: ignore[call-arg]


class InfrahubGlobalPreferenceUpdate(Mutation):
    """Update the GlobalPreference singleton.

    Gated on `manage_global_preferences` (super admins bypass via the permission manager), checked
    imperatively before any write. The singleton is lazily materialised by `get_global`.
    """

    class Arguments:
        date_format = String(required=False)
        timezone = String(required=False)

    ok = Boolean()
    date_format = String(required=False)
    timezone = String(required=False)

    @classmethod
    @retry_db_transaction(name="global_preference_update")
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        date_format: str | None = _UNSET,  # type: ignore[assignment]
        timezone: str | None = _UNSET,  # type: ignore[assignment]
    ) -> Self:
        graphql_context: GraphqlContext = info.context

        if not graphql_context.account_session or not graphql_context.account_session.authenticated:
            raise PermissionDeniedError("This operation requires an authenticated account")

        graphql_context.active_permissions.raise_for_permission(permission=MANAGE_GLOBAL_PREFERENCES_PERMISSION)

        async with graphql_context.db.start_transaction() as db:
            obj = await GlobalPreference.get_global(db=db)

            if date_format is not _UNSET:
                obj.date_format = date_format
            if timezone is not _UNSET:
                obj.timezone = timezone

            await obj.save(db=db, user_id=graphql_context.account_session.account_id)

        return cls(ok=True, date_format=obj.date_format, timezone=obj.timezone)  # type: ignore[call-arg]
