from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Sequence

from infrahub.core.constants import BranchSupportType
from infrahub.core.query import Query, QueryType

from ..shared import AttributeSchemaMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class NodeAttributeAddMigrationQuery01(Query):
    name = "migration_node_attribute_add_01"
    type: QueryType = QueryType.WRITE

    def __init__(
        self,
        *args: Any,
        migration: NodeAttributeAddMigration,
        **kwargs: Any,
    ):
        self.migration = migration

        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: Dict[str, Any]) -> None:
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        self.params["node_kind"] = self.migration.node_schema.kind
        self.params["attr_name"] = self.migration.attribute_schema.name
        self.params["attr_type"] = self.migration.attribute_schema.kind

        if self.migration.attribute_schema.default_value:
            self.params["attr_value"] = self.migration.attribute_schema.default_value
        else:
            self.params["attr_value"] = "NULL"

        if self.branch.is_default:
            self.params["branch_support"] = self.migration.attribute_schema._branch.value
        else:
            self.params["branch_support"] = BranchSupportType.LOCAL.value

        self.params["rel_props"] = {
            "branch": self.branch.name,
            "branch_level": self.branch.hierarchy_level,
            "status": "active",
            "from": self.at.to_string(),
        }

        self.params["is_protected_default"] = False
        self.params["is_visible_default"] = True

        query = """
        MATCH p = (n:Node)
        WHERE $node_kind IN LABELS(n) AND NOT exists((n)-[:HAS_ATTRIBUTE]-(:Attribute {name: $attr_name}))
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
        MERGE (av:AttributeValue { type: $attr_type, value: $attr_value })
        MERGE (is_protected_value:Boolean { value: $is_protected_default })
        MERGE (is_visible_value:Boolean { value: $is_visible_default })
        WITH n, av, is_protected_value, is_visible_value
        CREATE (a:Attribute { name: $attr_name, type: $attr_type, branch_support: $branch_support })
        CREATE (n)-[:HAS_ATTRIBUTE $rel_props ]->(a)
        CREATE (a)-[:HAS_VALUE $rel_props ]->(av)
        CREATE (a)-[:IS_PROTECTED $rel_props]->(is_protected_value)
        CREATE (a)-[:IS_VISIBLE $rel_props]->(is_visible_value)
        """ % {"branch_filter": branch_filter}
        self.add_to_query(query)
        self.return_labels = ["n.uuid", "a.uuid"]

        self.add_to_query(db.render_uuid_generation(node_label="a", node_attr="uuid"))


class NodeAttributeAddMigration(AttributeSchemaMigration):
    name: str = "node.attribute.add"
    queries: Sequence[type[Query]] = [NodeAttributeAddMigrationQuery01]
