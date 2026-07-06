from __future__ import annotations

from enum import StrEnum

from graphene import Enum, Field, ObjectType, String

from infrahub.core.preferences import DateFormat as DateFormatEnum

# GraphQL enum derived from the domain `DateFormat` Python enum, so the two can never drift and an
# invalid key is rejected at the GraphQL layer (pattern: graphql/types/enums.py). The description is
# passed explicitly as a single line rather than inheriting the enum's multi-line docstring — the SDL
# printer dedents multi-line descriptions differently across graphql-core versions, which made the
# generated schema.graphql environment-dependent.
DateFormat = Enum.from_enum(
    DateFormatEnum,
    description=(
        "Semantic date-format keys. The stored date_format is one of these keys (not a rendering "
        "pattern); each client maps the key to its own formatter. Single source of truth for the "
        "value on Preference.date_format."
    ),
)


class PreferenceWriteScope(StrEnum):
    """The WRITABLE axes of the preferences store.

    EFFECTIVE is intentionally absent: the resolved view is read-only, so it is unrepresentable as a
    write target (no runtime guard needed). USER writes the caller's own preferences; GLOBAL writes
    the organisation-wide ones (gated on manage_global_preferences).
    """

    USER = "user"
    GLOBAL = "global"


# GraphQL enum derived from the PreferenceWriteScope StrEnum (same pattern as DateFormat above).
# Graphene hands the resolver the member's value; being a StrEnum, the members compare equal to it.
PreferenceWriteScopeType = Enum.from_enum(
    PreferenceWriteScope,
    description=(
        "The writable axes of the preferences store: USER writes the caller's own preferences, "
        "GLOBAL writes the organisation-wide ones (gated on manage_global_preferences). EFFECTIVE is "
        "intentionally absent — the resolved view is read-only."
    ),
)


class PreferenceSource(Enum):
    """Where an effective preference value came from.

    USER    = the caller's own override.
    GLOBAL  = the organisation-wide default.
    DEFAULT = nothing is stored anywhere; the client applies its built-in default.
    """

    USER = "user"
    GLOBAL = "global"
    DEFAULT = "default"


class EffectiveDateFormat(ObjectType):
    """An effective `date_format` value and the source it was resolved from.

    `value` is a DateFormat key, or null when nothing is set.
    """

    value = Field(DateFormat, required=False)
    source = Field(PreferenceSource, required=True)


class EffectiveTimezone(ObjectType):
    """An effective `timezone`: the resolved IANA name (null when nothing is set) and its source."""

    value = Field(String, required=False)
    source = Field(PreferenceSource, required=True)


class EffectivePreferencesType(ObjectType):
    """The caller's resolved preferences (user → global → default) as typed, self-describing fields."""

    date_format = Field(EffectiveDateFormat, required=True)
    timezone = Field(EffectiveTimezone, required=True)


class RawPreferencesType(ObjectType):
    """Raw stored preferences for a single scope (USER = the caller's own, GLOBAL = organisation-wide).

    Each field is null when nothing is stored for it. Unlike the effective view there is no `source`
    — the scope IS the source.
    """

    date_format = Field(DateFormat, required=False)
    timezone = Field(String, required=False)
