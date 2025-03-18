from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import NULL_VALUE, RelationshipStatus
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class AttributeAddQuery(Query):
    name = "attribute_add"
    type = QueryType.WRITE

    def __init__(
        self,
        node_kind: str,
        attribute_name: str,
        attribute_kind: str,
        branch_support: str,
        default_value: Any | None = None,
        **kwargs: Any,
    ) -> None:
        self.node_kind = node_kind
        self.attribute_name = attribute_name
        self.attribute_kind = attribute_kind
        self.branch_support = branch_support
        self.default_value = default_value

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        self.params["node_kind"] = self.node_kind
        self.params["attr_name"] = self.attribute_name
        self.params["attr_type"] = self.attribute_kind
        self.params["branch_support"] = self.branch_support
        self.params["current_time"] = self.at.to_string()

        if self.default_value is not None:
            self.params["attr_value"] = self.default_value
        else:
            self.params["attr_value"] = NULL_VALUE

        self.params["rel_props"] = {
            "branch": self.branch.name,
            "branch_level": self.branch.hierarchy_level,
            "status": RelationshipStatus.ACTIVE.value,
            "from": self.at.to_string(),
        }

        self.params["is_protected_default"] = False
        self.params["is_visible_default"] = True

        query = """
        MERGE (av:AttributeValue { value: $attr_value, is_default: true })
        MERGE (is_protected_value:Boolean { value: $is_protected_default })
        MERGE (is_visible_value:Boolean { value: $is_visible_default })
        WITH av, is_protected_value, is_visible_value
        MATCH p = (n:%(node_kind)s)
        CALL {
            WITH n
            MATCH (root:Root)<-[r1:IS_PART_OF]-(n)
            OPTIONAL MATCH (n)-[r2:HAS_ATTRIBUTE]-(:Attribute { name: $attr_name })
            WHERE all(r in [r1, r2] WHERE (%(branch_filter)s))
            RETURN n as n1, r1 as r11, r2 as r12
            ORDER BY r2.branch_level DESC, r2.from ASC, r1.branch_level DESC, r1.from ASC
            LIMIT 1
        }
        WITH n1 as n, r11 as r1, r12 as r2, av, is_protected_value, is_visible_value
        WHERE r1.status = "active" AND (r2 IS NULL OR r2.status = "deleted")
        CREATE (a:Attribute { name: $attr_name, branch_support: $branch_support })
        CREATE (n)-[:HAS_ATTRIBUTE $rel_props ]->(a)
        CREATE (a)-[:HAS_VALUE $rel_props ]->(av)
        CREATE (a)-[:IS_PROTECTED $rel_props]->(is_protected_value)
        CREATE (a)-[:IS_VISIBLE $rel_props]->(is_visible_value)
        %(uuid_generation)s
        FOREACH (i in CASE WHEN r2.status = "deleted" THEN [1] ELSE [] END |
            SET r2.to = $current_time
        )
        """ % {
            "branch_filter": branch_filter,
            "node_kind": self.node_kind,
            "uuid_generation": db.render_uuid_generation(node_label="a", node_attr="uuid"),
        }
        self.add_to_query(query)
        self.return_labels = ["n.uuid", "a.uuid"]
