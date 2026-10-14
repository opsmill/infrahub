from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.query.node import NodeGetByHFIDQuery

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.branch import Branch
    from infrahub.core.schema import NodeSchema
    from infrahub.database import InfrahubDatabase

    from .data_reader import ProfileDataReader


@dataclass
class ProfileIdentifiers:
    ids: list[str]
    hfids: list[list[str]]


def _extract_profile_identifiers_from_input(profiles_data: Sequence[Any] | None) -> ProfileIdentifiers:
    """Extract profile IDs and HFIDs from input data."""
    if not profiles_data:
        return ProfileIdentifiers(ids=[], hfids=[])

    ids: list[str] = []
    hfids: list[list[str]] = []
    for item in profiles_data:
        if isinstance(item, str):
            # IDs
            ids.append(item)
        elif isinstance(item, dict):
            # Dicts with `id` or `hfid` keys
            if profile_id := item.get("id"):
                ids.append(profile_id)
            elif profile_hfid := item.get("hfid"):
                hfids.append(profile_hfid)
        elif hasattr(item, "id"):
            # Avoid circular import by not importing Node directly
            ids.append(item.id)

    return ProfileIdentifiers(ids=ids, hfids=hfids)


async def _resolve_hfids_to_ids(
    db: InfrahubDatabase, branch: Branch, profile_kind: str, hfids: list[list[str]]
) -> list[str]:
    query = await NodeGetByHFIDQuery.init(db=db, branch=branch, node_kind=profile_kind, hfids=hfids)
    await query.execute(db=db)
    return query.get_node_uuids()


class ProfilesMandatoryFieldGetter:
    def __init__(self, db: InfrahubDatabase, branch: Branch, profile_data_reader: ProfileDataReader) -> None:
        self.db = db
        self.branch = branch
        self.profile_data_reader = profile_data_reader

    async def get_mandatory_fields_from_profiles(
        self,
        schema: NodeSchema,
        profiles_data: Sequence[Any] | None,
        mandatory_attr_names: list[str],
        mandatory_rel_names: list[str],
        read_every_field: bool = False,
    ) -> tuple[set[str], set[str]]:
        """Get mandatory attributes and relationships that are provided by profiles.

        With `read_every_field`, every field the profiles can hold is read, for a later reader of the same profiles.
        """
        identifiers = _extract_profile_identifiers_from_input(profiles_data=profiles_data)

        profile_ids = list(identifiers.ids)
        if identifiers.hfids:
            resolved_ids = await _resolve_hfids_to_ids(
                db=self.db, branch=self.branch, profile_kind=f"Profile{schema.kind}", hfids=identifiers.hfids
            )
            profile_ids.extend(resolved_ids)

        if not profile_ids:
            return set(), set()

        if read_every_field:
            profile_data_list = await self.profile_data_reader.read_every_field(schema=schema, profile_ids=profile_ids)
        else:
            profile_data_list = await self.profile_data_reader.read(
                schema=schema, profile_ids=profile_ids, attr_names=mandatory_attr_names, rel_names=mandatory_rel_names
            )

        provided_attrs: set[str] = set()
        provided_rels: set[str] = set()

        for profile_data in profile_data_list:
            for attr_name in mandatory_attr_names:
                if profile_data.attribute_values.get(attr_name) is not None:
                    provided_attrs.add(attr_name)

            for rel_name in mandatory_rel_names:
                if profile_data.peers_of(relationship=schema.get_relationship(name=rel_name)):
                    provided_rels.add(rel_name)

        return provided_attrs, provided_rels
