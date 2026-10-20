from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .queries.get_profile_data import GetProfileDataQuery, ProfileData, RelationshipFilter

if TYPE_CHECKING:
    from collections.abc import Collection

    from infrahub.core.branch import Branch
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class _ProfileFieldsRead:
    attr_names: frozenset[str]
    rel_names: frozenset[str]
    profile_data: list[ProfileData]

    def covers(self, attr_names: Collection[str], rel_names: Collection[str]) -> bool:
        return self.attr_names.issuperset(attr_names) and self.rel_names.issuperset(rel_names)


class ProfileDataReader:
    """Read the values and the peers that profiles hold, for the components of one write.

    Caches the last read by profile kind and IDs, and answers a later read of fields it covers without a query.
    """

    def __init__(self, db: InfrahubDatabase, branch: Branch) -> None:
        self.db = db
        self.branch = branch
        self._reads: dict[tuple[str, frozenset[str]], _ProfileFieldsRead] = {}

    async def read(
        self, schema: MainSchemaTypes, profile_ids: list[str], attr_names: Collection[str], rel_names: Collection[str]
    ) -> list[ProfileData]:
        """Return at least the named attribute values and relationship peers of the profiles, lowest priority first.

        A relationship that profiles do not support is not read, and holds no peer in what is returned.
        """
        if not profile_ids:
            return []
        key = (schema.kind, frozenset(profile_ids))
        previous = self._reads.get(key)
        if previous is not None and previous.covers(attr_names=attr_names, rel_names=rel_names):
            return previous.profile_data
        query = await GetProfileDataQuery.init(
            db=self.db,
            branch=self.branch,
            profile_ids=profile_ids,
            attr_names=list(attr_names),
            include_relationships=[
                RelationshipFilter.for_relationship(relationship=relationship)
                for relationship in (schema.get_relationship(name=rel_name) for rel_name in rel_names)
                if relationship.support_profiles
            ],
        )
        await query.execute(db=self.db)
        fields_read = _ProfileFieldsRead(
            attr_names=frozenset(attr_names),
            rel_names=frozenset(rel_names),
            profile_data=sorted(
                query.get_profile_data(), key=lambda profile_data: (profile_data.priority, profile_data.uuid)
            ),
        )
        self._reads[key] = fields_read
        return fields_read.profile_data

    async def read_every_field(self, schema: MainSchemaTypes, profile_ids: list[str]) -> list[ProfileData]:
        """Return every attribute value and every relationship peer the profiles of the kind can hold."""
        return await self.read(
            schema=schema,
            profile_ids=profile_ids,
            attr_names=schema.attribute_names,
            rel_names=[relationship.name for relationship in schema.relationships if relationship.support_profiles],
        )
