from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from graphene import Argument, Boolean, Mutation, String
from typing_extensions import Self

from infrahub import lock
from infrahub.core.preferences import (
    GLOBAL_PREFERENCE_LOCK_NAME,
    GLOBAL_PREFERENCE_LOCK_NAMESPACE,
    MANAGE_GLOBAL_PREFERENCES_PERMISSION,
    GlobalPreference,
    UserPreference,
)
from infrahub.database import retry_db_transaction
from infrahub.exceptions import PermissionDeniedError, ValidationError

from ..queries.preferences import SCOPE_EFFECTIVE, SCOPE_GLOBAL, SCOPE_USER, PreferenceScope

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from ..initialization import GraphqlContext

# Per-account distributed lock namespace for UserPreference upserts. Keyed on account_id so two
# accounts never contend, while concurrent upserts for the SAME account serialise — preventing both
# a duplicate first row and lost updates.
USER_PREFERENCE_LOCK_NAMESPACE = "user_preference"


class _Unset(Enum):
    """Typed sentinel for an omitted mutation argument.

    Distinguishes "argument not provided" (leave the field unchanged) from an explicit `null`
    (reset the field). Graphene passes the GraphQL argument only when it is present.
    """

    token = 0


_UNSET = _Unset.token


class InfrahubSetPreferences(Mutation):
    """Write preferences on a single axis — the requested `scope` — using typed StandardNode fields.

    scope=USER   → the calling account's OWN UserPreference row only (bound to
                   account_session.account_id, no account argument, so there is no path to write
                   another user's preferences). Lazily created on first write, per-account lock.
    scope=GLOBAL → the org-wide GlobalPreference singleton, gated on manage_global_preferences
                   (super admins bypass via the permission manager) checked BEFORE any read.
    scope=EFFECTIVE → not writable (the resolved view is read-only); rejected fail-closed.

    The _UNSET sentinel means an omitted argument leaves the field unchanged while an explicit
    `null` resets it.
    """

    class Arguments:
        scope = Argument(PreferenceScope, required=True)
        date_format = String(required=False)
        timezone = String(required=False)

    ok = Boolean()
    date_format = String(required=False)
    timezone = String(required=False)

    @classmethod
    @retry_db_transaction(name="set_preferences")
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        scope: str,
        date_format: str | _Unset | None = _UNSET,
        timezone: str | _Unset | None = _UNSET,
    ) -> Self:
        graphql_context: GraphqlContext = info.context

        # Fail-closed: reject anonymous/unauthenticated sessions before any scope-specific logic.
        if not graphql_context.account_session or not graphql_context.account_session.authenticated:
            raise PermissionDeniedError("This operation requires an authenticated account")

        account_id = graphql_context.account_session.account_id

        if scope == SCOPE_USER:
            return await cls._set_user(
                graphql_context, account_id=account_id, date_format=date_format, timezone=timezone
            )
        if scope == SCOPE_GLOBAL:
            return await cls._set_global(
                graphql_context, account_id=account_id, date_format=date_format, timezone=timezone
            )
        if scope == SCOPE_EFFECTIVE:
            # The resolved view is a read-only projection; there is nothing concrete to write.
            raise ValidationError("The EFFECTIVE scope is read-only; write to USER or GLOBAL instead")

        raise ValidationError(f"Unsupported preference scope: {scope}")  # pragma: no cover

    @classmethod
    async def _set_user(
        cls,
        graphql_context: GraphqlContext,
        account_id: str,
        date_format: str | _Unset | None,
        timezone: str | _Unset | None,
    ) -> Self:
        # account_id is the caller's own (account_session.account_id); there is no account argument,
        # so there is no path to write another user's preferences.
        # Per-account distributed lock: the read-create-or-update-save block below is not atomic on
        # its own, so concurrent first-upserts for the same account could otherwise each see "no row"
        # and create a duplicate (and concurrent updates could lose writes). Keyed on account_id so
        # distinct accounts never contend. The READ path (get_for_account) stays lock-free.
        async with lock.registry.get(name=account_id, namespace=USER_PREFERENCE_LOCK_NAMESPACE, local=False):
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

    @classmethod
    async def _set_global(
        cls,
        graphql_context: GraphqlContext,
        account_id: str,
        date_format: str | _Unset | None,
        timezone: str | _Unset | None,
    ) -> Self:
        # Gated: raise BEFORE any read-modify-write (fail-closed). Super admins bypass via the
        # permission manager.
        graphql_context.active_permissions.raise_for_permission(permission=MANAGE_GLOBAL_PREFERENCES_PERMISSION)

        # Serialise the singleton read-modify-write: GlobalPreference.save() rewrites the whole node,
        # so two concurrent updates of *different* fields would otherwise lose one writer's change
        # (last write wins). The same lock guards get_global()'s lazy create, so an update can never
        # race the initial materialisation either.
        async with lock.registry.get(
            name=GLOBAL_PREFERENCE_LOCK_NAME, namespace=GLOBAL_PREFERENCE_LOCK_NAMESPACE, local=False
        ):
            async with graphql_context.db.start_transaction() as db:
                obj = await GlobalPreference.get_global(db=db)

                if date_format is not _UNSET:
                    obj.date_format = date_format
                if timezone is not _UNSET:
                    obj.timezone = timezone

                await obj.save(db=db, user_id=account_id)

        return cls(ok=True, date_format=obj.date_format, timezone=obj.timezone)  # type: ignore[call-arg]
