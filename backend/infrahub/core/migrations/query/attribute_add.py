from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from infrahub.core.constants import NULL_VALUE, RelationshipStatus
from infrahub.core.query import Query

if TYPE_CHECKING:

    from infrahub.database import InfrahubDatabase


class AttributeAddQuery(Query):
    name = "attribute_add"

    def __init__(
        self,
        node_kind: str,
        attribute_name: str,
        attribute_kind: str,
        branch_support: str,
        default_value: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        self.node_kind = node_kind
        self.attribute_name = attribute_name
        self.attribute_kind = attribute_kind
        self.branch_support = branch_support
        self.default_value = default_value

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        self.params["node_kind"] = self.node_kind
        self.params["attr_name"] = self.attribute_name
        self.params["attr_type"] = self.attribute_kind
        self.params["branch_support"] = self.branch_support

        if self.default_value:
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
        MATCH p = (n:%(node_kind)s)
        WHERE NOT exists((n)-[:HAS_ATTRIBUTE]-(:Attribute { name: $attr_name }))
        CALL {
            WITH n
            MATCH (root:Root)<-[r:IS_PART_OF]-(n)
            WHERE %(branch_filter)s
            RETURN n as n1, r as r1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as n, r1 as rb
        WHERE rb.status = "active"
        MERGE (av:AttributeValue { value: $attr_value, is_default: true })
        MERGE (is_protected_value:Boolean { value: $is_protected_default })
        MERGE (is_visible_value:Boolean { value: $is_visible_default })
        WITH n, av, is_protected_value, is_visible_value
        CREATE (a:Attribute { name: $attr_name, branch_support: $branch_support })
        CREATE (n)-[:HAS_ATTRIBUTE $rel_props ]->(a)
        CREATE (a)-[:HAS_VALUE $rel_props ]->(av)
        CREATE (a)-[:IS_PROTECTED $rel_props]->(is_protected_value)
        CREATE (a)-[:IS_VISIBLE $rel_props]->(is_visible_value)
        """ % {"branch_filter": branch_filter, "node_kind": self.node_kind}
        self.add_to_query(query)
        self.return_labels = ["n.uuid", "a.uuid"]

        self.add_to_query(db.render_uuid_generation(node_label="a", node_attr="uuid"))
