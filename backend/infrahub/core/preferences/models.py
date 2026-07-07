from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Self

from infrahub.core import registry
from infrahub.core.node.standard import StandardNode
from infrahub.core.preferences.constants import DateFormat, PreferenceSource
from infrahub.core.query.preference import PreferenceGetByOwnerQuery

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

# Distributed-lock namespace for Preference upserts, keyed on `owner_id`: concurrent upserts for the
# SAME owner serialise (preventing a duplicate first row or a lost update) while different owners
# never contend. The global row locks on the Root id, a user's on the account id. Reads are lock-free
# (they never write).
PREFERENCE_LOCK_NAMESPACE = "preference"


def global_owner_id() -> str:
    """`owner_id` for the organisation-wide (global) preferences: the Root node id.

    Raises:
        RuntimeError: if the registry has not been initialised (`registry.id` is unset).

    """
    if registry.id is None:
        raise RuntimeError("The registry is not initialised; registry.id (the Root id) is unset")
    return registry.id


class Preference(StandardNode):
    """Preferences owned by a single principal (one class for both user and global preferences).

    They share the same fields; the only difference is the owner, identified by `owner_id` — an
    account id for a user's preferences, or the Root node id (registry.id) for the organisation-wide
    (global) preferences. Reads NEVER create a row: a missing row means "nothing set" and the caller
    falls back (user → global → the client's built-in default).

    `owner_id` is a plain string, not a graph relationship: a StandardNode cannot declare a schema
    relationship with `on_delete: cascade` (that is a schema-Node feature), so deleting an account
    leaves its Preference row behind as unreachable dead data. Account ids are UUIDs and never reused,
    so such a row is permanently unreachable and benign. Cleanup is out of scope for V1 and tracked in
    Jira (IFC-2867).
    """

    owner_id: str
    # Persisted nullable fields must use `Optional[X]` (not `X | None`) until Python 3.14, because of
    # how StandardNode.guess_field_type works.
    # date_format is enum-typed so an unknown key is rejected at construction (including loads from
    # the db); it round-trips as a plain string because the enum subclasses str.
    date_format: Optional[DateFormat] = None
    timezone: Optional[str] = None

    @classmethod
    async def get_for_owner(cls, db: InfrahubDatabase, owner_id: str) -> Self | None:
        """Return the Preference owned by `owner_id`, or None. Never creates a row."""
        query = await PreferenceGetByOwnerQuery.init(db=db, owner_ids={owner_id}, node_type=cls.get_type())
        await query.execute(db=db)

        result = query.get_result()
        if not result:
            return None

        return cls.from_db(result.get_node("n"))

    @classmethod
    async def get_for_owners(cls, db: InfrahubDatabase, owner_ids: set[str]) -> dict[str, Self]:
        """Return a {owner_id: Preference} map for the owners that have a row, fetched in ONE query.

        Owners with no row are simply absent from the map.
        """
        query = await PreferenceGetByOwnerQuery.init(db=db, owner_ids=owner_ids, node_type=cls.get_type())
        await query.execute(db=db)

        preferences: dict[str, Self] = {}
        for result in query.get_results():
            node = cls.from_db(result.get_node("n"))
            # Keep the first row per owner (deterministic by uuid) if a duplicate ever existed.
            preferences.setdefault(node.owner_id, node)
        return preferences


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
    """

    user: Preference | None
    global_: Preference | None

    def resolve_date_format(self) -> ResolvedPreference[DateFormat]:
        return self._resolve(
            self.user.date_format if self.user else None,
            self.global_.date_format if self.global_ else None,
        )

    def resolve_timezone(self) -> ResolvedPreference[str]:
        return self._resolve(
            self.user.timezone if self.user else None,
            self.global_.timezone if self.global_ else None,
        )

    def _resolve[T](self, user_value: T | None, global_value: T | None) -> ResolvedPreference[T]:
        if user_value is not None:
            return ResolvedPreference(value=user_value, source=PreferenceSource.USER)
        if global_value is not None:
            return ResolvedPreference(value=global_value, source=PreferenceSource.GLOBAL)
        return ResolvedPreference(value=None, source=PreferenceSource.DEFAULT)
