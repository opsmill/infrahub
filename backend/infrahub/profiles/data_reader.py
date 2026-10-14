from __future__ import annotations

from typing import TYPE_CHECKING

from .queries.get_profile_data import GetProfileDataQuery, ProfileData, RelationshipFilter

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


class ProfileDataReader:
    """Read the values and the peers that profiles hold."""

    def __init__(self, db: InfrahubDatabase, branch: Branch) -> None:
        self.db = db
        self.branch = branch

    async def read(
        self, profile_ids: list[str], attr_names: list[str], rel_filters: list[RelationshipFilter]
    ) -> list[ProfileData]:
        """Return the named attribute values and relationship peers of the profiles, lowest priority value first."""
        if not profile_ids:
            return []
        query = await GetProfileDataQuery.init(
            db=self.db,
            branch=self.branch,
            profile_ids=profile_ids,
            attr_names=attr_names,
            include_relationships=rel_filters,
        )
        await query.execute(db=self.db)
        return sorted(query.get_profile_data(), key=lambda profile_data: (profile_data.priority, profile_data.uuid))
