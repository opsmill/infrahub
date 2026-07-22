from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import SYSTEM_USER_ID
from infrahub.core.query.preference import PreferenceGetAllQuery, PreferenceGetByOwnerQuery

if TYPE_CHECKING:
    from infrahub.core.preferences.models import Preference
    from infrahub.database import InfrahubDatabase


class PreferenceRepository:
    """All database access for Preference rows.

    Reads never create a row: a missing row means "nothing set" and the caller falls back
    (user → global → the client's built-in default). The single write path is a lazy upsert; the
    caller serialises concurrent writes per owner with a distributed lock.
    """

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def get_for_owner(self, owner_id: str) -> Preference | None:
        """Return the Preference owned by `owner_id`, or None when there is no row."""
        query = await PreferenceGetByOwnerQuery.init(db=self.db, owner_ids={owner_id})
        await query.execute(db=self.db)

        return next(iter(query.get_preferences()), None)

    async def get_for_owners(self, owner_ids: set[str]) -> dict[str, Preference]:
        """Return a {owner_id: Preference} map for the owners that have a row, fetched in ONE query.

        Owners with no row are simply absent from the map.
        """
        query = await PreferenceGetByOwnerQuery.init(db=self.db, owner_ids=owner_ids)
        await query.execute(db=self.db)

        preferences: dict[str, Preference] = {}
        for preference in query.get_preferences():
            # Keep the first row per owner (deterministic by uuid) if a duplicate ever existed.
            preferences.setdefault(preference.owner_id, preference)
        return preferences

    async def get_all(self) -> list[Preference]:
        """Return every stored Preference row, across all owners."""
        query = await PreferenceGetAllQuery.init(db=self.db)
        await query.execute(db=self.db)

        return query.get_preferences()

    async def save(self, preference: Preference, actor_id: str = SYSTEM_USER_ID) -> None:
        """Persist the preference, creating the row on first write or updating it in place."""
        await preference.save(db=self.db, user_id=actor_id)

    async def delete_for_owner(self, owner_id: str) -> None:
        """Delete every Preference row owned by `owner_id`; a no-op when there is none."""
        query = await PreferenceGetByOwnerQuery.init(db=self.db, owner_ids={owner_id})
        await query.execute(db=self.db)

        for preference in query.get_preferences():
            await preference.delete(db=self.db)
