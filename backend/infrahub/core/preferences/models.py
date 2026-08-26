from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from infrahub.core.node.standard import StandardNode
from infrahub.core.preferences.constants import DateFormat, PreferenceSource


class Preference(StandardNode):
    """Preferences owned by a single principal (one class for both user and global preferences).

    They share the same fields; the only difference is the owner, identified by `owner_id` — an
    account id for a user's preferences, or a fixed sentinel for the organisation-wide (global)
    preferences (accounts are UUID-keyed, so the sentinel can never collide with one). Reads NEVER
    create a row: a missing row means "nothing set" and the caller falls back (user → global → the
    client's built-in default).

    `owner_id` is a plain string, not a graph relationship: a StandardNode cannot declare a schema
    relationship with `on_delete: cascade` (that is a schema-Node feature), so account deletion
    cannot cascade to the Preference row through the schema and deletes it explicitly instead. A row
    orphaned by a deletion path that skips that cleanup stays benign: account ids are UUIDs and
    never reused, so it is permanently unreachable.
    """

    owner_id: str
    # Persisted nullable fields must use `Optional[X]` (not `X | None`) until Python 3.14, because of
    # how StandardNode.guess_field_type works.
    # date_format is enum-typed so an unknown key is rejected at construction (including loads from
    # the db); it round-trips as a plain string because the enum subclasses str.
    date_format: Optional[DateFormat] = None
    timezone: Optional[str] = None


@dataclass(frozen=True)
class ResolvedPreference[T]:
    """One effective preference value together with the layer it was resolved from.

    `value` keeps the field's own type (a DateFormat key, an IANA timezone string, ...); a null value
    means the field resolved to DEFAULT.
    """

    value: T | None
    source: PreferenceSource


@dataclass(frozen=True)
class EffectivePreferences:
    """Resolves each preference field across the two stored layers.

    A field is taken from the user layer if set, else the global layer, else DEFAULT with a null
    value (a missing layer counts as "nothing set"). DEFAULT carries a None value: the backend does
    not know the clients' built-in defaults, it only reports that neither layer sets the field.

    The `inherited_*` projection runs the same resolution with the user layer suppressed, so it
    reports what the caller would fall back to and can only ever be GLOBAL or DEFAULT, never USER.
    """

    user: Preference | None
    global_: Preference | None

    def resolved_date_format(self) -> ResolvedPreference[DateFormat]:
        return self._resolve_field(
            self.user.date_format if self.user else None,
            self.global_.date_format if self.global_ else None,
        )

    def resolved_timezone(self) -> ResolvedPreference[str]:
        return self._resolve_field(
            self.user.timezone if self.user else None,
            self.global_.timezone if self.global_ else None,
        )

    def inherited_date_format(self) -> ResolvedPreference[DateFormat]:
        """What the caller would inherit for date_format with no override of their own (GLOBAL or DEFAULT)."""
        return self._resolve_field(user_value=None, global_value=self.global_.date_format if self.global_ else None)

    def inherited_timezone(self) -> ResolvedPreference[str]:
        """What the caller would inherit for timezone with no override of their own (GLOBAL or DEFAULT)."""
        return self._resolve_field(user_value=None, global_value=self.global_.timezone if self.global_ else None)

    def _resolve_field[T](self, user_value: T | None, global_value: T | None) -> ResolvedPreference[T]:
        if user_value is not None:
            return ResolvedPreference(value=user_value, source=PreferenceSource.USER)
        if global_value is not None:
            return ResolvedPreference(value=global_value, source=PreferenceSource.GLOBAL)
        return ResolvedPreference(value=None, source=PreferenceSource.DEFAULT)
