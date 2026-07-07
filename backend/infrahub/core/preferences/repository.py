from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import SYSTEM_USER_ID
from infrahub.core.preferences.models import Preference
from infrahub.core.query.preference import PreferenceGetByOwnerQuery

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

# Distributed-lock namespace for Preference upserts, keyed on `owner_id`: concurrent upserts for the
# SAME owner serialise (preventing a duplicate first row or a lost update) while different owners
# never contend. The global row locks on the Root id, a user's on the account id. Reads are lock-free
# (they never write).
PREFERENCE_LOCK_NAMESPACE = "preference"


class PreferenceRepository:
    """All database access for Preference rows.

    Reads never create a row: a missing row means "nothing set" and the caller falls back
    (user → global → the client's built-in default). The single write path is a lazy upsert; the
    caller serialises concurrent writes per owner with a distributed lock on PREFERENCE_LOCK_NAMESPACE.
    """

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def get_for_owner(self, owner_id: str) -> Preference | None:
        """Return the Preference owned by `owner_id`, or None when there is no row."""
        query = await PreferenceGetByOwnerQuery.init(db=self.db, owner_ids={owner_id})
        await query.execute(db=self.db)

        result = query.get_result()
        if not result:
            return None

        return Preference.from_db(result.get_node("n"))

    async def get_for_owners(self, owner_ids: set[str]) -> dict[str, Preference]:
        """Return a {owner_id: Preference} map for the owners that have a row, fetched in ONE query.

        Owners with no row are simply absent from the map.
        """
        query = await PreferenceGetByOwnerQuery.init(db=self.db, owner_ids=owner_ids)
        await query.execute(db=self.db)

        preferences: dict[str, Preference] = {}
        for result in query.get_results():
            node = Preference.from_db(result.get_node("n"))
            # Keep the first row per owner (deterministic by uuid) if a duplicate ever existed.
            preferences.setdefault(node.owner_id, node)
        return preferences

    async def save(self, preference: Preference, actor_id: str = SYSTEM_USER_ID) -> None:
        """Persist the preference, creating the row on first write or updating it in place."""
        await preference.save(db=self.db, user_id=actor_id)
