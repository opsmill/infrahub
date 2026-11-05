from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Self

from graphene import Argument, Boolean, Field, Mutation, String

from infrahub import lock
from infrahub.core.preferences.constants import GLOBAL_OWNER_ID, PREFERENCE_LOCK_NAMESPACE
from infrahub.core.preferences.constants import DateFormat as DateFormatEnum
from infrahub.core.preferences.constants import InstanceColor as InstanceColorEnum
from infrahub.core.preferences.models import Preference
from infrahub.core.preferences.permissions import MANAGE_GLOBAL_PREFERENCES_PERMISSION
from infrahub.core.preferences.repository import PreferenceRepository
from infrahub.core.preferences.validation import validate_instance_label, validate_timezone
from infrahub.database import retry_db_transaction
from infrahub.exceptions import ValidationError
from infrahub.graphql.types.preferences import (
    DateFormat,
    InstanceColor,
    PreferenceWriteScope,
    PreferenceWriteScopeType,
)

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from ..initialization import GraphqlContext


class _Unset(Enum):
    """Typed sentinel for an omitted mutation argument.

    Distinguishes "argument not provided" (leave the field unchanged) from an explicit `null` (reset
    the field). Graphene passes the GraphQL argument only when it is present.
    """

    token = 0


_UNSET = _Unset.token


class InfrahubSetPreferences(Mutation):
    """Write preferences for one writable scope, USER or GLOBAL.

    scope=USER   → the calling account's OWN Preference row (owner_id = account_session.account_id;
                   no account argument, so there is no path to write another user's preferences).
    scope=GLOBAL → the organisation-wide row (owner_id = a fixed sentinel), gated on
                   manage_global_preferences (super admins bypass) checked BEFORE any read.

    The _UNSET sentinel leaves an omitted field unchanged while an explicit `null` resets it. The row
    is lazily created on first write under a per-owner lock — the only path that ever creates a
    Preference row.

    `instance_label` and `instance_color` describe the instance itself, so they are accepted with
    scope=GLOBAL only; providing either with scope=USER is a validation error.
    """

    class Arguments:
        scope = Argument(PreferenceWriteScopeType, required=True)
        date_format = Argument(DateFormat, required=False)
        timezone = String(required=False)
        instance_label = String(required=False)
        instance_color = Argument(InstanceColor, required=False)

    ok = Boolean()
    date_format = Field(DateFormat, required=False)
    timezone = String(required=False)
    instance_label = String(required=False)
    instance_color = Field(InstanceColor, required=False)

    @classmethod
    @retry_db_transaction(name="set_preferences")
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        scope: str,
        date_format: str | _Unset | None = _UNSET,
        timezone: str | _Unset | None = _UNSET,
        instance_label: str | _Unset | None = _UNSET,
        instance_color: str | _Unset | None = _UNSET,
    ) -> Self:
        graphql_context: GraphqlContext = info.context

        account_id = graphql_context.active_account_session.account_id

        if scope == PreferenceWriteScope.GLOBAL:
            # Super admins bypass via the permission manager.
            graphql_context.active_permissions.raise_for_permission(permission=MANAGE_GLOBAL_PREFERENCES_PERMISSION)
            owner_id = GLOBAL_OWNER_ID
        else:
            if instance_label is not _UNSET or instance_color is not _UNSET:
                raise ValidationError(input_value="instance_label and instance_color can only be set with scope GLOBAL")
            owner_id = account_id

        if timezone is not _UNSET:
            timezone = validate_timezone(timezone)
        if instance_label is not _UNSET:
            instance_label = validate_instance_label(instance_label)

        return await cls._set(
            graphql_context,
            owner_id=owner_id,
            actor_id=account_id,
            date_format=date_format,
            timezone=timezone,
            instance_label=instance_label,
            instance_color=instance_color,
        )

    @classmethod
    async def _set(
        cls,
        graphql_context: GraphqlContext,
        owner_id: str,
        actor_id: str,
        date_format: str | _Unset | None,
        timezone: str | _Unset | None,
        instance_label: str | _Unset | None,
        instance_color: str | _Unset | None,
    ) -> Self:
        # Per-owner distributed lock: the read-modify-write block below is not atomic on its own, so
        # concurrent first-upserts for the same owner could otherwise each see "no row" and create a
        # duplicate (and concurrent updates could lose writes). The read runs inside the lock so it
        # observes any in-flight write for the same owner. Keyed on owner_id so distinct owners never
        # contend.
        async with lock.registry.get(name=owner_id, namespace=PREFERENCE_LOCK_NAMESPACE, local=False):
            async with graphql_context.db.start_transaction() as db:
                repository = PreferenceRepository(db=db)
                preference = await repository.get_for_owner(owner_id=owner_id)
                if preference is None:
                    preference = Preference(owner_id=owner_id)

                if date_format is not _UNSET:
                    # Graphene hands over the enum member's value (a plain string); coerce it to the
                    # domain enum here
                    preference.date_format = None if date_format is None else DateFormatEnum(date_format)
                if timezone is not _UNSET:
                    preference.timezone = timezone
                if instance_label is not _UNSET:
                    preference.instance_label = instance_label
                if instance_color is not _UNSET:
                    preference.instance_color = None if instance_color is None else InstanceColorEnum(instance_color)

                await repository.save(preference, actor_id=actor_id)

        return cls(  # type: ignore[call-arg]
            ok=True,
            date_format=preference.date_format,
            timezone=preference.timezone,
            instance_label=preference.instance_label,
            instance_color=preference.instance_color,
        )
