from dataclasses import dataclass
from typing import Any

from infrahub.core.constants import NULL_VALUE, RelationshipDirection
from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase


@dataclass
class RelationshipFilter:
    relationship_identifier: str
    direction: RelationshipDirection

    def __hash__(self) -> int:
        return hash((self.relationship_identifier, self.direction))


@dataclass
class ProfileData:
    uuid: str
    priority: float | int
    attribute_values: dict[str, Any]
    relationship_peers: dict[RelationshipFilter, list[str]]


class GetProfileDataQuery(Query):
    type: QueryType = QueryType.READ
    insert_return: bool = False

    def __init__(
        self,
        *args: Any,
        profile_ids: list[str],
        attr_names: list[str],
        relationship_filters: list[RelationshipFilter] | None = None,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self.profile_ids = profile_ids
        self.attr_names = attr_names
        self.relationship_filters = relationship_filters or []

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at)
        self.params.update(branch_params)
        self.params["profile_ids"] = self.profile_ids
        self.params["attr_names"] = self.attr_names + ["profile_priority"]

        # Prepare relationship filters
        outbound_identifiers = []
        inbound_identifiers = []
        bidirectional_identifiers = []
        for rf in self.relationship_filters:
            if rf.direction == RelationshipDirection.OUTBOUND:
                outbound_identifiers.append(rf.relationship_identifier)
            elif rf.direction == RelationshipDirection.INBOUND:
                inbound_identifiers.append(rf.relationship_identifier)
            elif rf.direction == RelationshipDirection.BIDIR:
                bidirectional_identifiers.append(rf.relationship_identifier)

        self.params["outbound_identifiers"] = outbound_identifiers
        self.params["inbound_identifiers"] = inbound_identifiers
        self.params["bidirectional_identifiers"] = bidirectional_identifiers

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
OPTIONAL MATCH (profile)-[:HAS_ATTRIBUTE]-(attr:Attribute)
WHERE attr.name IN $attr_names
WITH DISTINCT profile, attr
CALL (profile, attr) {
    OPTIONAL MATCH (profile)-[r:HAS_ATTRIBUTE]->(attr)
    WHERE %(branch_filter)s
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    RETURN r.status = "active" AS r1_is_active
}
// --------------
// get the attribute values
// --------------
CALL (attr) {
    OPTIONAL MATCH (attr)-[r:HAS_VALUE]->(av)
    WHERE %(branch_filter)s
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    RETURN av, r.status = "active" AS r2_is_active
    LIMIT 1
}
// --------------
// filter out null and inactive attributes
// --------------
WITH profile, CASE
    WHEN attr IS NOT NULL AND av IS NOT NULL AND r1_is_active = TRUE AND r2_is_active = TRUE THEN [attr.name, av.value]
    ELSE NULL
END AS attribute_details
WITH profile, collect(attribute_details) AS attributes
// --------------
// get all possible relationships we might want for this profile
// --------------
OPTIONAL MATCH (profile)-[r:IS_RELATED]-(rel:Relationship)
WHERE rel.name IN $outbound_identifiers + $bidirectional_identifiers + $inbound_identifiers
AND %(branch_filter)s
WITH DISTINCT profile, attributes, rel
// --------------
// filter to active near-side relationships with names and directions we want
// --------------
CALL (profile, rel) {
    OPTIONAL MATCH (profile)-[r:IS_RELATED]-(rel)
    WHERE (
        (rel.name IN $outbound_identifiers AND startNode(r) = profile)
        OR (rel.name IN $bidirectional_identifiers AND startNode(r) = profile)
        OR (rel.name IN $inbound_identifiers AND startNode(r) = rel)
    )
    AND %(branch_filter)s
    RETURN r AS r1
    ORDER BY r1.branch_level DESC, r1.from DESC, r1.status ASC
    LIMIT 1
}
WITH profile, attributes, r1, rel
// --------------
// filter to active far-side relationships with names and directions we want
// --------------
CALL (profile, rel) {
    OPTIONAL MATCH (rel)-[r:IS_RELATED]-(peer)
    WHERE peer <> profile
    AND (
        (rel.name IN $outbound_identifiers AND startNode(r) = rel)
        OR (rel.name IN $bidirectional_identifiers AND startNode(r) = peer)
        OR (rel.name IN $inbound_identifiers AND startNode(r) = peer)
    )
    AND %(branch_filter)s
    RETURN r AS r2, peer
    ORDER BY r2.branch_level DESC, r2.from DESC, r2.status ASC
    LIMIT 1
}
WITH profile, attributes, r1, rel, r2, peer
// --------------
// save the direction of the relationship
// --------------
WITH *, CASE
    WHEN r1 IS NULL OR r2 IS NULL THEN NULL
    WHEN startNode(r1) = profile AND startNode(r2) = rel THEN "outbound"
    WHEN startNode(r1) = rel AND startNode(r2) = peer THEN "inbound"
    ELSE "bidirectional"
END AS direction
// --------------
// filter out null and inactive relationships
// --------------
WITH profile, attributes, CASE
    WHEN rel IS NOT NULL AND peer IS NOT NULL AND r1.status = "active" AND r2.status = "active" THEN [rel.name, direction, peer.uuid]
    ELSE NULL
END AS relationship_details
WITH profile, attributes, collect(relationship_details) AS relationships
RETURN profile.uuid AS profile_uuid, attributes, relationships
        """ % {"branch_filter": branch_filter}
        self.add_to_query(query)
        self.return_labels = ["profile_uuid", "attributes", "relationships"]

    def get_profile_data(self) -> list[ProfileData]:
        profile_data_list: list[ProfileData] = []
        for result in self.results:
            profile_uuid = result.get_as_type(label="profile_uuid", return_type=str)
            attributes = result.get(label="attributes")
            relationships = result.get(label="relationships")

            profile_data = ProfileData(
                uuid=profile_uuid, priority=float("inf"), attribute_values={}, relationship_peers={}
            )

            for attr_pair in attributes:
                if not isinstance(attr_pair, list) or len(attr_pair) != 2:
                    continue
                attr_name, attr_value = attr_pair
                if attr_value == NULL_VALUE:
                    attr_value = None
                if attr_name == "profile_priority":
                    if attr_value is not None and not isinstance(attr_value, int):
                        attr_value = int(attr_value)
                    profile_data.priority = attr_value
                else:
                    profile_data.attribute_values[attr_name] = attr_value

            # Parse relationships
            for rel_tuple in relationships:
                if not isinstance(rel_tuple, list) or len(rel_tuple) != 3:
                    continue
                rel_name, direction_str, peer_uuid = rel_tuple
                direction = RelationshipDirection(direction_str)
                rel_filter = RelationshipFilter(relationship_identifier=rel_name, direction=direction)
                if rel_filter not in profile_data.relationship_peers:
                    profile_data.relationship_peers[rel_filter] = []
                profile_data.relationship_peers[rel_filter].append(peer_uuid)

            profile_data_list.append(profile_data)
        return profile_data_list
