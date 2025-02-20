from typing import Any

from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase


class ValidateNodeRelationshipQuery(Query):
    name: str = "validate_node_rels"
    type: QueryType = QueryType.READ

    def __init__(self, node_id: str, **kwargs: Any) -> None:
        self.node_id = node_id
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        self.params["node_id"] = self.node_id
        self.params["branch"] = self.branch.name

        query = """
        // Match the pattern with specific branch conditions
        MATCH (node {uuid: $node_id})-[r:IS_RELATED]-(rel:Relationship)

        // Collect and process edges
        WITH
            node,
            rel,
            COLLECT(r) AS edges

        // Count and categorize edges
        WITH
            node,
            rel,
            edges,
            SIZE(edges) as nb_edges,
            [e IN edges WHERE e.branch = $branch] AS edges_on_correct_branch,
            [e IN edges WHERE e.status = 'active' AND e.to IS NOT NULL] AS active_with_to_edges,
            [e IN edges WHERE e.status = 'active' AND e.to IS NULL] AS active_no_to_edges,
            [e IN edges WHERE e.status = 'deleted'] AS deleted_edges

        // Count categorized edges
        WITH
            node,
            rel,
            active_with_to_edges,
            active_no_to_edges,
            deleted_edges,
            nb_edges,
            SIZE(edges_on_correct_branch) as nb_edges_on_correct_branch,
            SIZE(active_with_to_edges) AS nb_active_with_to_edges,
            SIZE(active_no_to_edges) AS nb_active_no_to_edges,
            SIZE(deleted_edges) AS nb_deleted_edges

        // Return the result based on conditions
        WITH
            CASE
                    WHEN nb_edges_on_correct_branch <> nb_edges
                    THEN "nb_edges: " + nb_edges + " VS nb_edges_on_correct_branch: " + nb_edges_on_correct_branch
                    ELSE
                        CASE
                            WHEN nb_edges = 1 AND nb_active_no_to_edges <> 1
                            THEN "1 edge but nb_active_no_to_edges: " + nb_active_no_to_edges
                            ELSE
                            CASE
                                WHEN nb_edges = 2 AND NOT (nb_active_with_to_edges = 1 AND nb_deleted_edges = 1
                                     AND active_with_to_edges[0].to = deleted_edges[0].from)
                                THEN "2 edges but they are invalid"
                                ELSE "Edges state is correct"
                            END
                        END
            END AS res
        """

        self.return_labels = ["res"]
        self.add_to_query(query)


async def validate_node_relationships(node: Node, branch: Branch, db: InfrahubDatabase) -> None:
    """
    This function will raise an error if following conditions are not met:
    - All IS_RELATED edges between this node and Relationship nodes should be on input branch
    - Between this node and any Relationship node, is expected:
       - Either 1 active edge without `to`
       - Or 1 active edge with `to` and 1 deleted edge with `active.to` = `deleted.from`

    IMPORTANT NOTE: This function currently validates a subset of all possible valid edge states.
    Typically, if between two nodes there are 1 active edge on main and 1 deleted on branch2,
    this function will raise an error while this state may happen while migrating an existing object node kind
    on branch2, but not on main.
    """

    query = await ValidateNodeRelationshipQuery.init(db=db, branch=branch, node_id=node.id)
    await query.execute(db=db)
    for result in query.results:
        print(result)
        assert len(result.data) == 1 and result.data[0] == "Edges state is correct"
