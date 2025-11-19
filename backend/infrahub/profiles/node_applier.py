from typing import Any

from infrahub.core.attribute import BaseAttribute
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase

from .queries.get_profile_data import GetProfileDataQuery, ProfileData


class NodeProfilesApplier:
    def __init__(self, db: InfrahubDatabase, branch: Branch):
        self.db = db
        self.branch = branch

    async def _get_profile_ids(self, node: Node) -> list[str]:
        try:
            profiles_rel = node.get_relationship("profiles")
        except ValueError:
            return []
        profile_rels = await profiles_rel.get_relationships(db=self.db)
        return [pr.peer_id for pr in profile_rels if pr.peer_id]

    async def _get_attr_names_for_profiles(self, node: Node) -> list[str]:
        node_schema = node.get_schema()

        # get the names of attributes that could be affected by profile changes
        attr_names_for_profiles: list[str] = []
        for attr_schema in node_schema.attributes:
            attr_name = attr_schema.name
            node_attr: BaseAttribute = getattr(node, attr_name)
            if node_attr.is_from_profile or node_attr.is_default:
                attr_names_for_profiles.append(attr_name)
        return attr_names_for_profiles

    async def _get_sorted_profile_data(
        self, profile_ids: list[str], attr_names_for_profiles: list[str]
    ) -> list[ProfileData]:
        if not profile_ids:
            return []
        query = await GetProfileDataQuery.init(
            db=self.db, branch=self.branch, profile_ids=profile_ids, attr_names=attr_names_for_profiles
        )
        await query.execute(db=self.db)
        profile_data_list = query.get_profile_data()
        return sorted(profile_data_list, key=lambda x: (x.priority, x.uuid))

    def _apply_profile_to_attribute(self, node_attr: BaseAttribute, profile_value: Any, profile_id: str) -> bool:
        is_changed = False
        if node_attr.value != profile_value:
            node_attr.value = profile_value
            is_changed = True
        if node_attr.is_default is not False:
            node_attr.is_default = False
            is_changed = True
        if node_attr.is_from_profile is not True:
            node_attr.is_from_profile = True
            is_changed = True
        if node_attr.source_id != profile_id:  # type: ignore[attr-defined]
            node_attr.set_source(value=profile_id)
            is_changed = True
        return is_changed

    def _remove_profile_from_attribute(self, node_attr: BaseAttribute) -> None:
        node_attr.clear_source()
        node_attr.value = node_attr.schema.default_value
        node_attr.is_default = True
        node_attr.is_from_profile = False

    async def apply_profiles(self, node: Node) -> list[str]:
        profile_ids = await self._get_profile_ids(node=node)
        attr_names_for_profiles = await self._get_attr_names_for_profiles(node=node)

        if not attr_names_for_profiles:
            return []

        # get profiles priorities and attribute values on branch
        sorted_profile_data = await self._get_sorted_profile_data(
            profile_ids=profile_ids, attr_names_for_profiles=attr_names_for_profiles
        )

        updated_field_names = []
        # set attribute values/is_default/is_from_profile on nodes
        for attr_name in attr_names_for_profiles:
            has_profile_data = False
            node_attr = node.get_attribute(attr_name)
            for profile_data in sorted_profile_data:
                profile_value = profile_data.attribute_values.get(attr_name)
                if profile_value is not None:
                    has_profile_data = True
                    is_changed = False
                    is_changed = self._apply_profile_to_attribute(
                        node_attr=node_attr, profile_value=profile_value, profile_id=profile_data.uuid
                    )
                    if is_changed:
                        updated_field_names.append(attr_name)
                    break
            if not has_profile_data and node_attr.is_from_profile:
                self._remove_profile_from_attribute(node_attr=node_attr)
                updated_field_names.append(attr_name)
        return updated_field_names
