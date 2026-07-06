# Preference model

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Self

from pydantic import field_validator

from infrahub.core import registry
from infrahub.core.node.standard import StandardNode
from infrahub.core.preferences.constants import DateFormat
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

    `registry.id` is the Root uuid string, always set once the registry is initialised
    (`get_root_node`); guard the `None` case so callers get a guaranteed `str` and a resolver that
    somehow runs before initialisation fails loudly instead of writing a bogus owner.

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
    # how StandardNode.guess_field_type works (mirrors Branch).
    date_format: Optional[str] = None
    timezone: Optional[str] = None

    @field_validator("date_format")
    @classmethod
    def _validate_date_format(cls, value: Optional[str]) -> Optional[str]:
        # date_format is stored as a plain string (StandardNode has no enum field type) but must be
        # one of the DateFormat semantic keys — reject anything else so it is never "any string".
        if value is not None:
            DateFormat(value)  # raises ValueError for an unknown key
        return value

    @classmethod
    async def get_for_owner(cls, db: InfrahubDatabase, owner_id: str) -> Self | None:
        """Return the Preference owned by `owner_id`, or None. Never creates a row."""
        query = await PreferenceGetByOwnerQuery.init(db=db, owner_ids=[owner_id], node_type=cls.get_type())
        await query.execute(db=db)

        result = query.get_result()
        if not result:
            return None

        return cls.from_db(result.get_node("n"))

    @classmethod
    async def get_for_owners(cls, db: InfrahubDatabase, owner_ids: list[str]) -> dict[str, Self]:
        """Return a {owner_id: Preference} map for the owners that have a row, fetched in ONE query.

        Used by the effective read to load the account row and the Root row together, then merge in
        Python. Owners with no row are simply absent from the map.
        """
        query = await PreferenceGetByOwnerQuery.init(db=db, owner_ids=owner_ids, node_type=cls.get_type())
        await query.execute(db=db)

        preferences: dict[str, Self] = {}
        for result in query.get_results():
            node = cls.from_db(result.get_node("n"))
            # Keep the first row per owner (deterministic by uuid) if a duplicate ever existed.
            preferences.setdefault(node.owner_id, node)
        return preferences
