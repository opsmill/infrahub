from typing import Any

from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME, BranchSupportType
from infrahub.core.node import Node
from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase


class ValidateNodeRelationshipQuery(Query):
    """
    This query will return error message if for any couple (input_node, relationship):
    - If relationship type is agnostic, all edges branches should be -global-
    - Else, there should not be any edge on global branch
    - Considering edges on the input branch:
        - Either 1 active edge without `to`
        - Either 1 deleted edge, and potentially 1 active edge having `active.to` = `deleted.from`

    NOTE: This query currently validates a subset of all possible valid edge states as edges states are mainly
          validated on input branch. Having a validation on any branch would require more logic
          (typically, a "groupby edge.branch" like behavior) and is TODO.
    """

    name: str = "validate_node_rels"
    type: QueryType = QueryType.READ

    def __init__(self, node_id: str, **kwargs: Any) -> None:
        self.node_id = node_id
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        self.params["node_id"] = self.node_id
        self.params["branch"] = self.branch.name
        self.params["global_branch_name"] = GLOBAL_BRANCH_NAME
        self.params["branch_agnostic"] = BranchSupportType.AGNOSTIC.value

        query = """
        // Match the pattern with specific branch conditions
        MATCH (input_node {uuid: $node_id})-[r:IS_RELATED]-(rel:Relationship)
        WITH DISTINCT rel
        MATCH (rel)-[is_related:IS_RELATED]-(node: Node)

        // Collect and process edges
        WITH
            node,
            rel,
            COLLECT(is_related) AS edges

        // Count and categorize edges
        WITH
            node,
            rel,
            edges,
            SIZE(edges) as nb_edges,
            [e IN edges WHERE e.branch = $branch] AS edges_on_branch,
            [e IN edges WHERE e.branch = $global_branch_name] AS edges_on_global_branch,
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
            SIZE(edges_on_branch) as nb_edges_on_branch,
            SIZE(edges_on_global_branch) as nb_edges_on_global_branch,
            SIZE(active_with_to_edges) AS nb_active_with_to_edges,
            SIZE(active_no_to_edges) AS nb_active_no_to_edges,
            SIZE(deleted_edges) AS nb_deleted_edges

        // Return the result based on conditions
        WITH
            CASE
                WHEN rel.branch_support = $branch_agnostic AND nb_edges_on_global_branch <> nb_edges
                THEN "Relationship is agnostic but found: " + (nb_edges - nb_edges_on_global_branch) + " aware edge(s)"
                WHEN rel.branch_support <> $branch_agnostic AND nb_edges_on_global_branch > 0
                THEN "Relationship is aware but found " + nb_edges_on_global_branch + " agnostic edge(s)"
                WHEN nb_edges_on_branch > 2
                THEN "More than 2 edges on a given branch between a node and a relationship"
                WHEN nb_edges_on_branch = 2 AND NOT (nb_active_with_to_edges = 1 AND nb_deleted_edges = 1
                AND active_with_to_edges[0].to = deleted_edges[0].from)
                THEN "Found 2 inconsistent edges between a node and a relationship"
                ELSE "Edges state is correct"  // It currently allows having one edge as we might not always create a `deleted` edge?
            END AS res
        """

        self.return_labels = ["res"]
        self.add_to_query(query)


async def validate_node_relationships(node: Node, branch: Branch, db: InfrahubDatabase) -> None:
    """
    Raises an error if validation conditions of the query are not met.
    """

    query = await ValidateNodeRelationshipQuery.init(db=db, branch=branch, node_id=node.id)
    await query.execute(db=db)
    for result in query.results:
        print(result)
        assert len(result.data) == 1 and result.data[0] == "Edges state is correct"


async def verify_no_duplicate_paths(db: InfrahubDatabase) -> None:
    """Verify that no duplicate paths exist at the database level"""
    query = """
MATCH path = (p)-[e]->(q)
WITH
    %(id_func)s(p) AS node_id1,
    e.branch AS branch,
    e.from AS from_time,
    type(e) AS edge_type,
    %(id_func)s(q) AS node_id2,
    path
WITH node_id1, branch, from_time, edge_type, node_id2, size(collect(path)) AS num_paths
WHERE num_paths > 1
RETURN node_id1, branch, from_time, edge_type, node_id2, num_paths
    """ % {"id_func": db.get_id_function_name()}
    records = await db.execute_query(query=query)
    for record in records:
        node_id1 = record.get("node_id1")
        branch = record.get("branch")
        from_time = record.get("from_time")
        edge_type = record.get("edge_type")
        node_id2 = record.get("node_id2")
        num_paths = record.get("num_paths")
        raise ValueError(
            f"{num_paths} paths ({branch=},{edge_type=},{from_time=}) between nodes '{node_id1}' and '{node_id2}'"
        )


async def validate_no_duplicate_attributes(db: InfrahubDatabase, branch: Branch) -> list[str]:
    """
    Validate that no Nodes have duplicated attribute or relationship names
    """
    branch_filter, branch_params = branch.get_query_filter_path()

    query = """
// -------------
// get all the active Attributes this branch and count them up
// -------------
MATCH (n:Node)-[:HAS_ATTRIBUTE]->(field:Attribute)
WITH DISTINCT n, field
CALL (n, field) {
MATCH (n)-[r:HAS_ATTRIBUTE]->(field)
WHERE %(branch_filter)s
RETURN r
ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
LIMIT 1
}
WITH n, field, r
WHERE r.status = "active" AND r.to IS NULL
WITH n.uuid AS node_id, field.name AS field_name, count(*) AS num_fields
WHERE num_fields > 1
RETURN node_id, field_name, num_fields
    """ % {"branch_filter": branch_filter}
    results = await db.execute_query(query=query, params=branch_params)
    errors = []
    for result in results:
        node_id = result.get("node_id")
        field_name = result.get("field_name")
        num_fields = result.get("num_fields")
        errors.append(f"Node '{node_id}' has {num_fields} duplicated attributes with {field_name=}")
    return errors
