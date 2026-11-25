from typing import Any

from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME, BranchSupportType
from infrahub.core.constants.database import DatabaseEdgeType
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
        MATCH (input_node:Node {uuid: $node_id})-[r:IS_RELATED]-(rel:Relationship)
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


def _count_graph_edges_query(predicate: str) -> str:
    """Build a query counting the edges of every graph edge type that match ``predicate`` on ``r``.

    Each type gets its own MATCH, because a type union in a single pattern is planned without the indexes.
    """
    matches = "\n    UNION ALL\n".join(
        f"    MATCH ()-[r:{edge_type.value}]->()\n    WHERE {predicate}\n    RETURN r" for edge_type in DatabaseEdgeType
    )
    return f"CALL () {{\n{matches}\n}}\nRETURN count(r) AS c"


async def count_branch_edges_at(db: InfrahubDatabase, branch_name: str, at: str) -> int:
    """Count edges on a branch whose ``from`` timestamp equals ``at`` (edges written exactly then)."""
    result = await db.execute_query(
        query=_count_graph_edges_query(predicate="r.from = $at AND r.branch = $branch"),
        params={"at": at, "branch": branch_name},
    )
    return result[0].get("c")


async def count_branch_edges_since(db: InfrahubDatabase, branch_name: str, at: str) -> int:
    """Count edges on a branch whose ``from`` timestamp is ``at`` or later."""
    result = await db.execute_query(
        query=_count_graph_edges_query(predicate="r.branch = $branch AND r.from >= $at"),
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


OPEN_ATTRIBUTE_EDGES_QUERY = """
MATCH (node:%(label)s)-[has_attribute:HAS_ATTRIBUTE]->(attribute:Attribute {name: $attribute_name})
WHERE has_attribute.branch = $branch_name AND has_attribute.to IS NULL
OPTIONAL MATCH (attribute)-[has_value:HAS_VALUE]->()
WHERE has_value.branch = $branch_name AND has_value.to IS NULL
RETURN node.uuid AS node_id, collect(DISTINCT has_attribute.status) AS attribute_statuses,
    collect(DISTINCT has_value.status) AS value_statuses
"""


async def open_attribute_edge_statuses(
    db: InfrahubDatabase, node_label: str, attribute_name: str, branch_name: str
) -> dict[str, tuple[list[str], list[str]]]:
    """Return the statuses of the open edges of an attribute, by node; a load writes its closing and its new edges at one timestamp."""
    results = await db.execute_query(
        query=OPEN_ATTRIBUTE_EDGES_QUERY % {"label": node_label},
        params={"attribute_name": attribute_name, "branch_name": branch_name},
    )
    return {
        record["node_id"]: (sorted(record["attribute_statuses"]), sorted(record["value_statuses"]))
        for record in results
    }


ACTIVE_VALUE_LABELS_QUERY = """
MATCH (node:Node {uuid: $node_id})-[has_attribute:HAS_ATTRIBUTE]->(:Attribute {name: $attribute_name})-[has_value:HAS_VALUE]->(value)
WHERE all(edge IN [has_attribute, has_value] WHERE edge.branch = $branch_name AND edge.to IS NULL AND edge.status = "active")
RETURN labels(value) AS value_labels
"""


async def active_value_labels(
    db: InfrahubDatabase, node_id: str, attribute_name: str, branch_name: str
) -> list[list[str]]:
    """Return the labels of the active value vertices of an attribute of a node."""
    results = await db.execute_query(
        query=ACTIVE_VALUE_LABELS_QUERY,
        params={"node_id": node_id, "attribute_name": attribute_name, "branch_name": branch_name},
    )
    return [sorted(record["value_labels"]) for record in results]


OPEN_ACTIVE_ATTRIBUTE_UUIDS_QUERY = """
MATCH (node:%(label)s {uuid: $node_id})-[has_attribute:HAS_ATTRIBUTE {status: "active"}]->(attribute:Attribute {name: $attribute_name})
WHERE has_attribute.branch = $branch_name AND has_attribute.to IS NULL
RETURN attribute.uuid AS attribute_id
"""


async def open_active_attribute_uuids(
    db: InfrahubDatabase, node_label: str, node_id: str, attribute_name: str, branch_name: str
) -> list[str]:
    """Return the uuid of every attribute with a name that has an open active edge to a node on a branch."""
    results = await db.execute_query(
        query=OPEN_ACTIVE_ATTRIBUTE_UUIDS_QUERY % {"label": node_label},
        params={"node_id": node_id, "attribute_name": attribute_name, "branch_name": branch_name},
    )
    return sorted(record["attribute_id"] for record in results)


OPEN_RELATIONSHIP_EDGES_QUERY = """
MATCH (node:%(label)s {uuid: $node_id})-[is_related:IS_RELATED]-(:Relationship {name: $identifier})
WHERE is_related.branch = $branch_name AND is_related.to IS NULL
RETURN is_related.status AS status
"""


async def open_relationship_edge_statuses(
    db: InfrahubDatabase, node_id: str, identifier: str, branch_name: str, node_label: str = "Node"
) -> list[str]:
    """Return the statuses of the open edges between a node and the relationships with an identifier.

    A kind update gives the node a new vertex with the same uuid, so a node label limits the edges to one vertex.
    """
    results = await db.execute_query(
        query=OPEN_RELATIONSHIP_EDGES_QUERY % {"label": node_label},
        params={"node_id": node_id, "identifier": identifier, "branch_name": branch_name},
    )
    return sorted(record["status"] for record in results)
