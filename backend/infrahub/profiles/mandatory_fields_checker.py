from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict

from infrahub.core.query.node import NodeGetByHFIDQuery

from .queries.get_profile_data import GetProfileDataQuery, RelationshipFilter

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema import NodeSchema
    from infrahub.database import InfrahubDatabase


class ProfileInput(TypedDict, total=False):
    id: str
    hfid: list[str]


@dataclass
class ProfileIdentifiers:
    ids: list[str]
    hfids: list[list[str]]


def _extract_profile_identifiers_from_input(profiles_data: list[ProfileInput] | None) -> ProfileIdentifiers:
    """Extract profile IDs and HFIDs from input data."""
    if not profiles_data:
        return ProfileIdentifiers(ids=[], hfids=[])

    ids: list[str] = []
    hfids: list[list[str]] = []
    for item in profiles_data:
        if profile_id := item.get("id"):
            ids.append(profile_id)
        elif profile_hfid := item.get("hfid"):
            hfids.append(profile_hfid)

    return ProfileIdentifiers(ids=ids, hfids=hfids)


async def _resolve_hfids_to_ids(
    db: InfrahubDatabase, branch: Branch, profile_kind: str, hfids: list[list[str]]
) -> list[str]:
    query = await NodeGetByHFIDQuery.init(db=db, branch=branch, node_kind=profile_kind, hfids=hfids)
    await query.execute(db=db)
    return query.get_node_uuids()


async def get_mandatory_fields_from_profiles(
    db: InfrahubDatabase,
    branch: Branch,
    schema: NodeSchema,
    profiles_data: list[ProfileInput] | None,
    mandatory_attr_names: list[str],
    mandatory_rel_names: list[str],
) -> tuple[set[str], set[str]]:
    """Get mandatory attributes and relationships that are provided by profiles."""
    identifiers = _extract_profile_identifiers_from_input(profiles_data)

    profile_ids = list(identifiers.ids)
    if identifiers.hfids:
        resolved_ids = await _resolve_hfids_to_ids(
            db=db, branch=branch, profile_kind=f"Profile{schema.kind}", hfids=identifiers.hfids
        )
        profile_ids.extend(resolved_ids)

    if not profile_ids:
        return set(), set()

    rel_filters: list[RelationshipFilter] = []
    rel_name_to_filter: dict[str, RelationshipFilter] = {}
    for rel_name in mandatory_rel_names:
        rel_schema = schema.get_relationship(name=rel_name)
        if not rel_schema.support_profiles:
            continue

        rel_filter = RelationshipFilter(
            relationship_identifier=f"profile_{rel_schema.get_identifier()}", direction=rel_schema.direction
        )
        rel_filters.append(rel_filter)
        rel_name_to_filter[rel_name] = rel_filter

    query = await GetProfileDataQuery.init(
        db=db, branch=branch, profile_ids=profile_ids, attr_names=mandatory_attr_names, relationship_filters=rel_filters
    )
    await query.execute(db=db)
    profile_data_list = query.get_profile_data()

    provided_attrs: set[str] = set()
    provided_rels: set[str] = set()

    for profile_data in profile_data_list:
        for attr_name in mandatory_attr_names:
            if profile_data.attribute_values.get(attr_name) is not None:
                provided_attrs.add(attr_name)

        for rel_name, rel_filter in rel_name_to_filter.items():
            if profile_data.relationship_peers.get(rel_filter):
                provided_rels.add(rel_name)

    return provided_attrs, provided_rels
