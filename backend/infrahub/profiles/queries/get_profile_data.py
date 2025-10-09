from dataclasses import dataclass
from typing import Any

from infrahub.core.constants import NULL_VALUE
from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase


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
            if attr_value == NULL_VALUE:
                attr_value = None
            if attr_name == "profile_priority":
                if attr_value is not None and not isinstance(attr_value, int):
                    attr_value = int(attr_value)
                profile_data.priority = attr_value
            else:
                profile_data.attribute_values[attr_name] = attr_value
        return list(profile_data_by_uuid.values())
