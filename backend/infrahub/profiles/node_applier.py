from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase

if TYPE_CHECKING:
    from infrahub.core.attribute import BaseAttribute


@dataclass
class ProfileData:
    uuid: str
    priority: float | int
    attribute_values: dict[str, Any]


class GetProfileDataQuery(Query):
    type: QueryType = QueryType.READ
    insert_return: bool = False

    def __init__(self, *args: Any, profile_ids: list[str], attr_names: list[str], **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.profile_ids = profile_ids
        self.attr_names = attr_names

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)
        self.params["profile_ids"] = self.profile_ids
        self.params["attr_names"] = self.attr_names + ["profile_priority"]

        query = """
// --------------
// get the Profile nodes
// --------------
MATCH (profile:Node)
WHERE profile.uuid IN $profile_ids
// --------------
// make sure we only use the active ones
// --------------
CALL (profile) {
    MATCH (profile)-[r:IS_PART_OF]->(:Root)
    WHERE %(branch_filter)s
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    RETURN r.status = "active" AS is_active
}
WITH profile
WHERE is_active = TRUE
// --------------
// get the attributes that we care about
// --------------
MATCH (profile)-[:HAS_ATTRIBUTE]-(attr:Attribute)
WHERE attr.name IN $attr_names
WITH DISTINCT profile, attr
CALL (profile, attr) {
    MATCH (profile)-[r:HAS_ATTRIBUTE]->(attr)
    WHERE %(branch_filter)s
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    RETURN r.status = "active" AS is_active
}
WITH profile, attr, is_active
WHERE is_active = TRUE
// --------------
// get the attribute values
// --------------
MATCH (attr)-[:HAS_VALUE]->(av:AttributeValue)
WITH DISTINCT profile, attr, av
CALL (attr, av) {
    MATCH (attr)-[r:HAS_VALUE]->(av)
    WHERE %(branch_filter)s
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    RETURN r.status = "active" AS is_active
}
WITH profile, attr, av
WHERE is_active = TRUE
RETURN profile.uuid AS profile_uuid, attr.name AS attr_name, av.value AS attr_value
        """ % {"branch_filter": branch_filter}
        self.add_to_query(query)
        self.return_labels = ["profile_uuid", "attr_name", "attr_value"]

    def get_profile_data(self) -> list[ProfileData]:
        profile_data_by_uuid: dict[str, ProfileData] = {}
        for result in self.results:
            profile_uuid = result.get_as_type(label="profile_uuid", return_type=str)
            if profile_uuid not in profile_data_by_uuid:
                profile_data_by_uuid[profile_uuid] = ProfileData(
                    uuid=profile_uuid, priority=float("inf"), attribute_values={}
                )
            profile_data = profile_data_by_uuid[profile_uuid]
            attr_name = result.get_as_type(label="attr_name", return_type=str)
            attr_value: Any = result.get(label="attr_value")
            if attr_name == "profile_priority":
                if attr_value is not None and not isinstance(attr_value, int):
                    attr_value = int(attr_value)
                profile_data.priority = attr_value
            else:
                profile_data.attribute_values[attr_name] = attr_value
        return list(profile_data_by_uuid.values())


class NodeProfilesApplier:
    def __init__(self, db: InfrahubDatabase, branch: Branch):
        self.db = db
        self.branch = branch

    async def apply_profiles(self, node: Node, profile_ids: list[str]) -> None:
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
            # TODO: make sure that any attributes using profiles have their HAS_SOURCE edges set to deleted
            return

        # get profiles priorities and attribute values on branch
        query = await GetProfileDataQuery.init(
            db=self.db, branch=self.branch, profile_ids=profile_ids, attr_names=attr_names_for_profiles
        )
        await query.execute(db=self.db)
        profile_data_list = query.get_profile_data()
        sorted_profile_data = sorted(profile_data_list, key=lambda x: x.priority)

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

        # update attribute values and sources on node in database
        # need to delete existing HAS_SOURCE edges for nodes that had a profile value and have a new value
