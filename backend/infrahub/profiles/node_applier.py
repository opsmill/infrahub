from typing import TYPE_CHECKING

from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase

from .queries.get_profile_data import GetProfileDataQuery

if TYPE_CHECKING:
    from infrahub.core.attribute import BaseAttribute


class NodeProfilesApplier:
    def __init__(self, db: InfrahubDatabase, branch: Branch):
        self.db = db
        self.branch = branch

    async def apply_profiles(self, node: Node) -> None:
        if not hasattr(node, "profiles"):
            return
        profile_rels = await node.profiles.get_relationships(db=self.db)
        profile_ids = [pr.peer_id for pr in profile_rels]
        if not profile_ids:
            return

        node_schema = node.get_schema()

        # get the names of attributes that could be affected by profile changes
        attr_names_for_profiles: list[str] = []
        for attr_schema in node_schema.attributes:
            attr_name = attr_schema.name
            node_attr: BaseAttribute = getattr(node, attr_name)
            # TODO: make sure this accounts for attributes with NULL values correctly
            if node_attr.is_from_profile or node_attr.is_default:
                attr_names_for_profiles.append(attr_name)

        if not attr_names_for_profiles:
            return

        # get profiles priorities and attribute values on branch
        query = await GetProfileDataQuery.init(
            db=self.db, branch=self.branch, profile_ids=profile_ids, attr_names=attr_names_for_profiles
        )
        await query.execute(db=self.db)
        profile_data_list = query.get_profile_data()
        sorted_profile_data = sorted(profile_data_list, key=lambda x: (x.priority, x.uuid))

        # set attribute values/is_default/is_from_profile on nodes
        for attr_name in attr_names_for_profiles:
            node_attr = getattr(node, attr_name)
            for profile_data in sorted_profile_data:
                profile_value = profile_data.attribute_values.get(attr_name)
                if profile_value is not None:
                    node_attr.value = profile_value
                    node_attr.is_default = False
                    node_attr.is_from_profile = True
                    node_attr.set_source(value=profile_data.uuid)
                    break
