from typing import Any

from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME, BranchSupportType
from infrahub.core.node import Node
from infrahub.core.query import Query, QueryType
from infrahub.core.registry import registry
from infrahub.database import InfrahubDatabase


class ValidateNodeRelationshipQuery(Query):
    """This query will return error message if for any couple (input_node, relationship):
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
    """Raises an error if validation conditions of the query are not met."""
    query = await ValidateNodeRelationshipQuery.init(db=db, branch=branch, node_id=node.id)
    await query.execute(db=db)
    for result in query.results:
        print(result)
        assert len(result.data) == 1
        assert result.data[0] == "Edges state is correct"


async def verify_no_duplicate_paths(db: InfrahubDatabase) -> None:
    """Verify that no duplicate paths exist at the database level.

    Raises:
        ValueError: When duplicate paths are found between two nodes.

    """
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


async def verify_graph(db: InfrahubDatabase) -> None:
    """Run all post-merge graph validation checks."""
    await verify_no_duplicate_paths(db=db)
    await verify_no_orphaned_active_edges(db=db)
    await verify_relationship_edge_counts(db=db)


async def verify_no_orphaned_active_edges(db: InfrahubDatabase) -> None:
    """Verify that no active second-level edges exist under deleted first-level edges.

    If a HAS_ATTRIBUTE or IS_RELATED edge is deleted/closed on a branch, then all
    sub-edges (HAS_VALUE, IS_PROTECTED, HAS_OWNER, HAS_SOURCE, far-side IS_RELATED)
    hanging off the same Attribute/Relationship vertex on the same branch should also
    be deleted/closed.

    Raises:
        ValueError: When an active second-level edge is found under a deleted first-level edge.

    """
    query = """
// ----------------
// Find deleted/closed first-level edges (HAS_ATTRIBUTE or IS_RELATED)
// ----------------
MATCH (n:Node)-[r1:HAS_ATTRIBUTE|IS_RELATED]-(field:Attribute|Relationship)
WHERE (r1.status = "deleted" AND r1.to IS NULL)
   OR (r1.status = "active" AND r1.to IS NOT NULL)
WITH n, field, r1,
    CASE WHEN r1.status = "deleted" THEN r1.from ELSE r1.to END AS r1_deleted_at
// ----------------
// Exclude cases where another active first-level edge to this field exists on the same branch
// (e.g. migrated-kind nodes where old vertex HAS_ATTRIBUTE is deleted but new vertex's is active)
// ----------------
WHERE NOT EXISTS {
    MATCH (other:Node)-[active_r1:HAS_ATTRIBUTE|IS_RELATED {branch: r1.branch, status: "active"}]-(field)
    WHERE active_r1.to IS NULL
}
// ----------------
// Find all second-level peers of this field, then get the latest edge to each
// visible from the deleted first-level edge's branch
// ----------------
WITH n, field, r1, r1_deleted_at
MATCH (field)-[prop_edge:HAS_VALUE|IS_PROTECTED|HAS_OWNER|HAS_SOURCE|IS_RELATED]-(peer)
WHERE peer <> n
WITH DISTINCT n, field, r1, r1_deleted_at, type(prop_edge) AS prop_edge_type, peer
// ----------------
// Get the branched_from time if r1.branch is a user branch
// ----------------
OPTIONAL MATCH (r1_br:Branch {name: r1.branch})
// Use created_at instead of branched_from because branched_from is updated after a merge
WITH n, field, r1, r1_deleted_at, prop_edge_type, peer, r1_br.created_at AS r1_branch_created_at
// ----------------
// Get the latest edge to this peer visible from the first-level edge's branch
// ----------------
CALL (field, r1, r1_branch_created_at, prop_edge_type, peer) {
    MATCH (field)-[r2:HAS_VALUE|IS_PROTECTED|HAS_OWNER|HAS_SOURCE|IS_RELATED]-(peer)
    WHERE (
        r2.branch = r1.branch
        OR (r1_branch_created_at IS NOT NULL AND r2.branch = $default_branch AND r2.from < r1_branch_created_at)
    )
    AND type(r2) = prop_edge_type
    RETURN r2
    ORDER BY r2.branch_level DESC, r2.from DESC, r2.status ASC
    LIMIT 1
}
// ----------------
// Flag if the latest visible edge is active — it should have been deleted/closed
// ----------------
WITH field, r1, r2
WHERE r2.status = "active" AND r2.to IS NULL
RETURN DISTINCT
    field.name AS field_name,
    r1.branch AS branch,
    labels(field)[0] AS field_type,
    type(r2) AS child_type
    """
    params = {
        "default_branch": registry.default_branch,
    }
    records = await db.execute_query(query=query, params=params)
    for record in records:
        field_name = record.get("field_name")
        branch = record.get("branch")
        field_type = record.get("field_type")
        child_type = record.get("child_type")
        raise ValueError(
            f"Orphaned active {child_type} edge on {field_type} '{field_name}' "
            f"where all parent edges are deleted on branch '{branch}'"
        )


async def verify_relationship_edge_counts(db: InfrahubDatabase) -> None:
    """Verify that every Relationship vertex has exactly 0 or 2 active IS_RELATED edges per branch.

    A Relationship vertex connects two Node vertices. For any given branch, there should be
    either 0 active IS_RELATED edges (relationship not active on that branch) or exactly 2
    (one to each Node). Having 1 or 3+ is always invalid.

    Raises:
        ValueError: When a Relationship has an invalid number of active IS_RELATED edges on a branch.

    """
    query = """
MATCH (rel:Relationship)
// ----------------
// Get all distinct branches from any edge connected to this Relationship
// ----------------
CALL (rel) {
    MATCH (rel)-[e]-()
    RETURN DISTINCT e.branch AS branch
}
// ----------------
// Get created_at for user branches (NULL for default)
// Use created_at instead of branched_from because branched_from is updated after a merge
// ----------------
OPTIONAL MATCH (br:Branch {name: branch})
WITH rel, branch, br.created_at AS branch_created_at
// ----------------
// Find all peer Nodes this Relationship might connect to
// ----------------
MATCH (rel)-[:IS_RELATED]-(peer:Node)
WITH DISTINCT rel, branch, branch_created_at, peer
// ----------------
// For each (rel, branch, peer), get the latest IS_RELATED edge visible from this branch
// ----------------
CALL (rel, branch, branch_created_at, peer) {
    MATCH (rel)-[r:IS_RELATED]-(peer)
    WHERE (r.branch = branch)
       OR (branch_created_at IS NOT NULL AND r.branch = $default_branch AND r.from < branch_created_at)
    RETURN r
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
// ----------------
// Count peers where the latest visible edge is active
// ----------------
WITH rel, branch,
    CASE
        WHEN r.status = "active"
        AND (
            r.to IS NULL
            OR (branch <> $default_branch AND r.branch = $default_branch AND r.to > branch_created_at)
        )
        THEN 1
        ELSE NULL
    END AS is_active

WITH rel, branch, count(is_active) AS active_count
WHERE active_count <> 0 AND active_count <> 2
RETURN rel.name AS rel_name, rel.uuid AS rel_uuid, branch, active_count
    """
    records = await db.execute_query(query=query, params={"default_branch": registry.default_branch})
    for record in records:
        rel_name = record.get("rel_name")
        rel_uuid = record.get("rel_uuid")
        branch = record.get("branch")
        active_count = record.get("active_count")
        raise ValueError(
            f"Relationship '{rel_name}' ({rel_uuid}) has {active_count} active "
            f"IS_RELATED edges on branch '{branch}' (expected 0 or 2)"
        )


async def validate_no_duplicate_attributes(db: InfrahubDatabase, branch: Branch) -> list[str]:
    """Validate that no Nodes have duplicated attribute or relationship names"""
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
