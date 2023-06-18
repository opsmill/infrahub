from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List

from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from neo4j import AsyncSession

    from infrahub.core.group import Group, GroupAssociationType


class GroupQuery(Query):
    def __init__(
        self,
        association_type: GroupAssociationType,
        group: Group,
        *args,
        **kwargs,
    ):
        self.association_type = association_type
        self.rel_name = f"IS_{association_type.value}".upper()
        self.group = group

        super().__init__(*args, **kwargs)


class GroupAddAssociationQuery(GroupQuery):
    name = "group_association_add"

    type: QueryType = QueryType.WRITE

    def __init__(
        self,
        node_ids: List[str],
        *args,
        **kwargs,
    ):
        self.node_ids = node_ids

        super().__init__(*args, **kwargs)

    async def query_init(self, session: AsyncSession, *args, **kwargs):
        self.params["group_id"] = self.group.id
        self.params["node_ids"] = self.node_ids
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["at"] = self.at.to_string()

        query = (
            """
        MATCH (grp { uuid: $group_id })
        MATCH (m:Node) WHERE m.uuid IN $node_ids
        CREATE (m)-[:%s { branch: $branch, branch_level: $branch_level, status: "active", from: $at, to: null }]->(grp)
        """
            % self.rel_name
        )

        self.add_to_query(query)
        self.return_labels = ["grp"]


class GroupGetAssociationQuery(GroupQuery):
    name = "group_member_get"

    type: QueryType = QueryType.WRITE

    async def query_init(self, session: AsyncSession, *args, **kwargs):
        self.params["group_id"] = self.group.id
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["at"] = self.at.to_string()

        rels_filter, rels_params = self.branch.get_query_filter_path(at=self.at)
        self.params.update(rels_params)

        query = """
        MATCH (grp { uuid: $group_id })
        CALL {
            WITH grp
            MATCH (grp)-[r:%s]-(mb:Node)
            WHERE %s
            RETURN DISTINCT mb as mb1, r as r1
            ORDER BY [r.branch_level, r.from] DESC
        }
        WITH mb1 as mb, r1 as r
        WHERE r.status = "active"
        """ % (
            self.rel_name,
            rels_filter,
        )

        self.add_to_query(query)
        self.return_labels = ["mb.uuid"]

    async def get_members(self):
        return [result.get("mb.uuid") for result in self.get_results()]


class GroupHasAssociationQuery(GroupQuery):
    name = "group_member_has"

    type: QueryType = QueryType.WRITE

    def __init__(
        self,
        node_ids: List[str],
        *args,
        **kwargs,
    ):
        self.node_ids = node_ids

        super().__init__(*args, **kwargs)

    async def query_init(self, session: AsyncSession, *args, **kwargs):
        self.params["group_id"] = self.group.id
        self.params["node_ids"] = self.node_ids
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["at"] = self.at.to_string()

        rels_filter, rels_params = self.branch.get_query_filter_path(at=self.at)
        self.params.update(rels_params)

        query = """
        MATCH (grp { uuid: $group_id })
        MATCH (mb:Node) WHERE mb.uuid IN $node_ids
        CALL {
            WITH grp, mb
            MATCH (grp)-[r:%s]-(mb:Node)
            WHERE %s
            RETURN DISTINCT mb as mb1, r as r1
            ORDER BY [r.branch_level, r.from] DESC
        }
        WITH mb1 as mb, r1 as r
        WHERE r.status = "active"
        """ % (
            self.rel_name,
            rels_filter,
        )

        self.add_to_query(query)
        self.return_labels = ["mb.uuid"]

    async def get_memberships(self) -> Dict[str, bool]:
        members = [result.get("mb.uuid") for result in self.get_results()]
        return {node_id: True if node_id in members else False for node_id in self.node_ids}
