from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core import registry
from infrahub.core.constants import GLOBAL_BRANCH_NAME, BranchSupportType
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.core.schema import AttributeSchema
    from infrahub.database import InfrahubDatabase


class UpdateAttributeValuesQuery(Query):
    """
    Update the values of the given attribute schema for the input node-id-to-value map.

    This version only expires existing values when they're different from the new value,
    making it safe to run idempotently without clearing correct existing values.

    This code is adapted from m044_backfill_hfid_display_label_in_db.
    """

    name = "update_attribute_values"
    type = QueryType.WRITE
    insert_return = False

    def __init__(self, attribute_schema: AttributeSchema, values_by_id_map: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.attribute_name = attribute_schema.name
        self.is_branch_agnostic = attribute_schema.get_branch() is BranchSupportType.AGNOSTIC
        self.values_by_id_map = values_by_id_map

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params = {
            "node_uuids": list(self.values_by_id_map.keys()),
            "attribute_name": self.attribute_name,
            "values_by_id": self.values_by_id_map,
            "default_branch": registry.default_branch,
            "global_branch": GLOBAL_BRANCH_NAME,
            "branch": GLOBAL_BRANCH_NAME if self.is_branch_agnostic else self.branch.name,
            "branch_level": 1 if self.is_branch_agnostic else self.branch.hierarchy_level,
            "at": self.at.to_string(),
        }
        branch_filter, branch_filter_params = self.branch.get_query_filter_path(at=self.at)
        self.params.update(branch_filter_params)

        if self.branch.name in [registry.default_branch, GLOBAL_BRANCH_NAME]:
            update_value_query = """
// ------------
// Find the Nodes and Attributes we need to update
// ------------
MATCH (n:Node)-[e:IS_PART_OF]->(:Root)
WHERE n.uuid IN $node_uuids
AND e.branch IN [$default_branch, $global_branch]
AND e.to IS NULL
AND e.status = "active"
WITH DISTINCT n
MATCH (n)-[e:HAS_ATTRIBUTE]->(attr:Attribute {name: $attribute_name})
WHERE e.branch IN [$default_branch, $global_branch]
AND e.to IS NULL
AND e.status = "active"
// ------------
// If the attribute has an existing value on the branch, then set the to time on it
// but only if the value is different from the new value
// ------------
WITH DISTINCT n, attr
CALL (attr) {
    OPTIONAL MATCH (attr)-[e:HAS_VALUE]->(existing_av)
    WHERE e.branch IN [$default_branch, $global_branch]
    AND e.to IS NULL
    AND e.status = "active"
    RETURN existing_av, e AS existing_has_value
}
CALL (existing_has_value, existing_av, n) {
    WITH existing_has_value, existing_av, n
    WHERE existing_has_value IS NOT NULL
    AND existing_av.value <> $values_by_id[n.uuid]
    SET existing_has_value.to = $at
}
WITH n, attr, existing_av
            """
        else:
            update_value_query = """
// ------------
// Find the Nodes and Attributes we need to update
// ------------
MATCH (n:Node)
WHERE n.uuid IN $node_uuids
CALL (n) {
    MATCH (n)-[r:IS_PART_OF]->(:Root)
    WHERE %(branch_filter)s
    RETURN r.status = "active" AS is_active
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
WITH n, is_active
WHERE is_active = TRUE
WITH DISTINCT n
CALL (n) {
    MATCH (n)-[r:HAS_ATTRIBUTE]->(attr:Attribute {name: $attribute_name})
    WHERE %(branch_filter)s
    RETURN attr, r.status = "active"  AS is_active
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
WITH DISTINCT n, attr, is_active
WHERE is_active = TRUE
// ------------
// If the attribute has an existing value on the branch, then set the to time on it
// but only if the value is different from the new value
// ------------
CALL (n, attr) {
    OPTIONAL MATCH (attr)-[r:HAS_VALUE]->(existing_av)
    WHERE %(branch_filter)s
    WITH r, existing_av, n
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
    WITH CASE
        WHEN existing_av.value <> $values_by_id[n.uuid]
        AND r.status = "active"
        AND r.branch = $branch
        THEN [r, existing_av]
        ELSE [NULL, NULL]
    END AS existing_details
    RETURN existing_details[0] AS existing_has_value, existing_details[1] AS existing_av
}
CALL (existing_has_value) {
    WITH existing_has_value
    WHERE existing_has_value IS NOT NULL
    SET existing_has_value.to = $at
}
WITH n, attr, existing_av
            """ % {"branch_filter": branch_filter}
        self.add_to_query(update_value_query)

        set_value_query = """
// ------------
// only make updates if the existing value is not the same as the new value
// ------------
WITH n, attr, existing_av, $values_by_id[n.uuid] AS required_value
WHERE existing_av.value <> required_value
OR existing_av IS NULL
CALL (n, attr) {
    MERGE (av:AttributeValue&AttributeValueIndexed {is_default: false, value: $values_by_id[n.uuid]} )
    WITH av, attr
    LIMIT 1
    CREATE (attr)-[r:HAS_VALUE { branch: $branch, branch_level: $branch_level, status: "active", from: $at }]->(av)
}
            """
        self.add_to_query(set_value_query)
