from typing import Any

from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME, BranchSupportType
from infrahub.core.node import Node
from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase


class ValidateNodeRelationshipQuery(Query):
    """This query will return error message if for any couple (input_node, relationship):

    - If relationship type is agnostic, all edges branches should be -global-
    - Else, there should not be any edge on global branch
    - Considering edges on the input branch:
        - Either 1 active edge without `to`
        - Either 1 deleted edge, and potentially 1 active edge having `active.to` = `deleted.from`.

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
    """Raises an error if validation conditions of the query are not met."""
    query = await ValidateNodeRelationshipQuery.init(db=db, branch=branch, node_id=node.id)
    await query.execute(db=db)
    for result in query.results:
        print(result)
        assert len(result.data) == 1
        assert result.data[0] == "Edges state is correct"


LATEST_ATTRIBUTE_PATH_STATUS_QUERY = """
MATCH (node:%(label)s)
CALL (node) {
    MATCH (node)-[r1:HAS_ATTRIBUTE]->(attr:Attribute {name: $attr_name})
    WHERE r1.branch = $branch_name
    RETURN r1, attr
    ORDER BY r1.branch_level DESC, r1.from DESC
    LIMIT 1
}
CALL (attr) {
    MATCH (attr)-[r2:HAS_VALUE]->(av)
    WHERE r2.branch = $branch_name
    RETURN r2
    ORDER BY r2.branch_level DESC, r2.from DESC
    LIMIT 1
}
RETURN node.uuid AS node_id, r1.status AS has_attr_status, r2.status AS has_val_status
"""


async def assert_attribute_path_status(
    db: InfrahubDatabase,
    node_label: str,
    attr_name: str,
    branch_name: str,
    expected_status: str,
) -> None:
    query = LATEST_ATTRIBUTE_PATH_STATUS_QUERY % {"label": node_label}
    results = await db.execute_query(query=query, params={"attr_name": attr_name, "branch_name": branch_name})
    assert len(results) > 0, f"No {node_label} nodes found with attribute {attr_name!r}"
    for record in results:
        assert record["has_attr_status"] == expected_status, (
            f"Node {record['node_id']}: HAS_ATTRIBUTE status is {record['has_attr_status']!r}, expected {expected_status!r}"
        )
        assert record["has_val_status"] == expected_status, (
            f"Node {record['node_id']}: HAS_VALUE status is {record['has_val_status']!r}, expected {expected_status!r}"
        )


async def assert_attribute_absent(
    db: InfrahubDatabase,
    node_label: str,
    attr_name: str,
    branch_name: str,
) -> None:
    query = LATEST_ATTRIBUTE_PATH_STATUS_QUERY % {"label": node_label}
    results = await db.execute_query(query=query, params={"attr_name": attr_name, "branch_name": branch_name})
    assert len(results) == 0, f"Expected no active/deleted {node_label}.{attr_name} edges, found {len(results)}"


async def count_branch_edges_at(db: InfrahubDatabase, branch_name: str, at: str) -> int:
    """Count edges on a branch whose ``from`` timestamp equals ``at`` (edges written exactly then)."""
    result = await db.execute_query(
        query="MATCH ()-[r {from: $at, branch: $branch}]->() RETURN count(r) AS c",
        params={"at": at, "branch": branch_name},
    )
    return result[0].get("c")


async def get_node_metadata(db: InfrahubDatabase, node_uuid: str) -> dict[str, str | None]:
    """Return a node vertex's ``updated_at``/``previous_updated_at`` metadata."""
    result = await db.execute_query(
        query=(
            "MATCH (n:Node {uuid: $uuid}) "
            "RETURN n.updated_at AS updated_at, n.previous_updated_at AS previous_updated_at"
        ),
        params={"uuid": node_uuid},
    )
    return {
        "updated_at": result[0].get("updated_at"),
        "previous_updated_at": result[0].get("previous_updated_at"),
    }
