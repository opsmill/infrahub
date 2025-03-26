from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from infrahub.core.constants import BranchSupportType, RelationshipStatus
from infrahub.core.graph.schema import GraphAttributeRelationships
from infrahub.core.query import Query

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from infrahub.database import InfrahubDatabase


class AttributeInfo(BaseModel):
    name: str
    node_kind: str
    branch_support: str = BranchSupportType.AWARE.value


class AttributeRenameQuery(Query):
    name = "attribute_rename"
    insert_return: bool = False

    def __init__(
        self,
        previous_attr: AttributeInfo,
        new_attr: AttributeInfo,
        **kwargs: Any,
    ) -> None:
        self.previous_attr = previous_attr
        self.new_attr = new_attr

        super().__init__(**kwargs)

    def render_match(self) -> str:
        query = """
        // Find all the active nodes
        CALL {
            MATCH (node:%(node_kind)s)
            WHERE exists((node)-[:HAS_ATTRIBUTE]-(:Attribute { name: $prev_attr.name }))
            RETURN node
            UNION
            MATCH (node:Profile%(node_kind)s)
            WHERE exists((node)-[:HAS_ATTRIBUTE]-(:Attribute { name: $prev_attr.name }))
            RETURN node
        }
        WITH node
        """ % {"node_kind": self.previous_attr.node_kind}

        return query

    @staticmethod
    def _render_sub_query_per_rel_type_update_active(rel_type: str, rel_def: FieldInfo) -> str:
        subquery = [
            "WITH peer_node, rb, active_attr",
            "WITH peer_node, rb, active_attr",
            f'WHERE type(rb) = "{rel_type}"',
        ]
        if rel_def.default.direction.value == "outbound":
            subquery.append(f"CREATE (active_attr)-[:{rel_type} $rel_props_delete ]->(peer_node)")
        elif rel_def.default.direction.value == "inbound":
            subquery.append(f"CREATE (active_attr)<-[:{rel_type} $rel_props_delete ]-(peer_node)")
        else:
            subquery.append(f"CREATE (active_attr)-[:{rel_type} $rel_props_delete ]-(peer_node)")

        subquery.append("RETURN peer_node as p2")
        return "\n".join(subquery)

    @staticmethod
    def _render_sub_query_per_rel_type_create_new(rel_type: str, rel_def: FieldInfo) -> str:
        subquery = [
            "WITH peer_node, rb, active_attr, new_attr",
            "WITH peer_node, rb, active_attr, new_attr",
            f'WHERE type(rb) = "{rel_type}"',
        ]
        if rel_def.default.direction.value == "outbound":
            subquery.append(f"CREATE (new_attr)-[:{rel_type} $rel_props_create ]->(peer_node)")
        elif rel_def.default.direction.value == "inbound":
            subquery.append(f"CREATE (new_attr)<-[:{rel_type} $rel_props_create ]-(peer_node)")
        else:
            subquery.append(f"CREATE (new_attr)-[:{rel_type} $rel_props_create ]-(peer_node)")

        subquery.append("RETURN peer_node as p2")
        return "\n".join(subquery)

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        self.params["new_attr"] = self.new_attr.model_dump()
        self.params["prev_attr"] = self.previous_attr.model_dump()

        self.params["current_time"] = self.at.to_string()
        self.params["branch_name"] = self.branch.name

        self.params["rel_props_create"] = {
            "branch": self.branch.name,
            "branch_level": self.branch.hierarchy_level,
            "status": RelationshipStatus.ACTIVE.value,
            "from": self.at.to_string(),
        }

        self.params["rel_props_delete"] = {
            "branch": self.branch.name,
            "branch_level": self.branch.hierarchy_level,
            "status": RelationshipStatus.DELETED.value,
            "from": self.at.to_string(),
        }

        sub_queries_create = [
            self._render_sub_query_per_rel_type_create_new(rel_type, rel_def)
            for rel_type, rel_def in GraphAttributeRelationships.model_fields.items()
        ]
        sub_query_create_all = "\nUNION\n".join(sub_queries_create)

        sub_queries_update = [
            self._render_sub_query_per_rel_type_update_active(rel_type, rel_def)
            for rel_type, rel_def in GraphAttributeRelationships.model_fields.items()
        ]
        sub_query_update_all = "\nUNION\n".join(sub_queries_update)

        self.add_to_query(self.render_match())

        add_uuid = db.render_uuid_generation(node_label="new_attr", node_attr="uuid")
        query = """
        CALL {
            WITH node
            MATCH (root:Root)<-[r:IS_PART_OF]-(node)
            WHERE %(branch_filter)s
            RETURN node as n1, r as r1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as active_node, r1 as rb
        WHERE rb.status = "active"
        // Find all the attributes that need to be updated
        CALL {
            WITH active_node
            MATCH (active_node)-[r:HAS_ATTRIBUTE]-(attr:Attribute { name: $prev_attr.name })
            WHERE %(branch_filter)s
            RETURN active_node as n1, r as r1, attr as attr1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as active_node, r1 as rb, attr1 as active_attr
        WHERE rb.status = "active"
        CREATE (new_attr:Attribute { name: $new_attr.name, branch_support: $new_attr.branch_support })
        %(add_uuid)s
        WITH active_attr, new_attr
        MATCH (active_attr)-[]-(peer)
        CALL {
            WITH active_attr, peer
            MATCH (active_attr)-[r]-(peer)
            WHERE %(branch_filter)s
            RETURN active_attr as a1, r as r1, peer as p1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH a1 as active_attr, r1 as rb, p1 as peer_node, new_attr
        WHERE rb.status = "active"
        CALL {
            %(sub_query_create_all)s
        }
        WITH p2 as peer_node, rb, new_attr, active_attr
        """ % {"branch_filter": branch_filter, "add_uuid": add_uuid, "sub_query_create_all": sub_query_create_all}
        self.add_to_query(query)

        if not (self.branch.is_default or self.branch.is_global):
            query = """
            CALL {
                %(sub_query_update_all)s
            }
            WITH p2 as peer_node, rb, new_attr
            RETURN DISTINCT new_attr
            """ % {"sub_query_update_all": sub_query_update_all}
            self.add_to_query(query)
        else:
            query = """
            FOREACH (i in CASE WHEN rb.branch = $branch_name THEN [1] ELSE [] END |
                SET rb.to = $current_time
            )
            RETURN DISTINCT new_attr
            """
            self.add_to_query(query)
