from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.constants import GLOBAL_BRANCH_NAME, BranchSupportType
from infrahub.utils import InfrahubStringEnum

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class GraphCheck(InfrahubStringEnum):
    DUPLICATE_RELATIONSHIPS = "duplicate_relationships"
    EDGES_AFTER_NODE_DELETE = "edges_after_node_delete"
    DUPLICATE_PATHS = "duplicate_paths"
    ORPHANED_ACTIVE_EDGES = "orphaned_active_edges"
    RELATIONSHIP_EDGE_COUNTS = "relationship_edge_counts"
    DUPLICATE_ATTRIBUTES = "duplicate_attributes"
    ATTRIBUTE_EDGE_BRANCH = "attribute_edge_branch"


@dataclass(frozen=True)
class GraphViolation:
    check: GraphCheck
    message: str

    def __str__(self) -> str:
        return f"[{self.check.value}] {self.message}"


class GraphValidationError(ValueError):
    """Raised when one or more graph-integrity checks report a violation."""

    def __init__(self, violations: list[GraphViolation]) -> None:
        self.violations = violations
        super().__init__("\n".join(str(violation) for violation in violations))


def _node_labels(kinds: list[str] | None) -> str:
    """Build the label expression for a Node anchor, narrowed to the requested kinds when there are any.

    Kind labels only ever sit on Node vertices, so matching on them alone already implies the Node label.
    """
    if not kinds:
        return "Node"
    return "|".join(kinds)


def _near_kind_filter(*variables: str, kinds: list[str] | None) -> str:
    """Build a Cypher predicate matching vertices carrying, or attached to a Node carrying, a requested label.

    Attribute, Relationship and value vertices carry no kind label of their own, so restricting a check
    that anchors on them requires looking one hop out to the Node they hang off.

    ``_near_kind_filter("p", "q", kinds=["TestCar", "TestPerson"])`` returns::

        ((p:TestCar|TestPerson OR EXISTS { MATCH (p)--(:TestCar|TestPerson) })
         OR (q:TestCar|TestPerson OR EXISTS { MATCH (q)--(:TestCar|TestPerson) }))

    Returns ``true`` when no filter is requested, so it can be interpolated unconditionally.
    """
    if not kinds:
        return "true"
    labels = "|".join(kinds)
    predicates = [f"({variable}:{labels} OR EXISTS {{ MATCH ({variable})--(:{labels}) }})" for variable in variables]
    return "(" + " OR ".join(predicates) + ")"


async def _check_duplicate_relationships(db: InfrahubDatabase, kinds: list[str] | None) -> list[GraphViolation]:
    """Verify that no duplicate active relationships exist at the database level.

    A duplicate is defined as
    - connecting the same two nodes
    - having the same identifier
    - having the same direction (inbound, outbound, bidirectional)
    - having the same branch
    A more thorough check that no duplicates exist at any point in time is possible, but more complex.
    """
    query = """
MATCH (a:%(node_labels)s)-[e1:IS_RELATED {status: "active"}]-(rel:Relationship)-[e2:IS_RELATED {branch: e1.branch, status: "active"}]-(b:Node)
WHERE a.uuid <> b.uuid
AND e1.to IS NULL
AND e2.to IS NULL
WITH a, rel.name AS rel_name, b, e1.branch AS branch, CASE
    WHEN startNode(e1) = a AND startNode(e2) = rel THEN "out"
    WHEN startNode(e1) = rel AND startNode(e2) = b THEN "in"
    ELSE "bidir"
END AS direction, COUNT(*) AS num_duplicates
WHERE num_duplicates > 1
RETURN a.uuid AS node_id1, b.uuid AS node_id2, rel_name, branch, direction, num_duplicates
    """ % {"node_labels": _node_labels(kinds)}
    results = await db.execute_query(query=query)
    violations = []
    for result in results:
        node_id1 = result.get("node_id1")
        node_id2 = result.get("node_id2")
        rel_name = result.get("rel_name")
        branch = result.get("branch")
        direction = result.get("direction")
        num_duplicates = result.get("num_duplicates")
        violations.append(
            GraphViolation(
                check=GraphCheck.DUPLICATE_RELATIONSHIPS,
                message=(
                    f"{num_duplicates} duplicate relationships ({branch=},{direction=}) between nodes"
                    f" '{node_id1}' and '{node_id2}' with relationship name '{rel_name}'"
                ),
            )
        )
    return violations


async def _check_edges_after_node_delete(db: InfrahubDatabase, kinds: list[str] | None) -> list[GraphViolation]:
    """Verify that no edges are added to a Node after it is deleted on a given branch."""
    query = """
// ------------
// find deleted nodes
// ------------
MATCH (n:%(node_labels)s)-[e:IS_PART_OF]->(:Root)
WHERE e.status = "deleted" OR e.to IS NOT NULL
WITH DISTINCT n, e.branch AS delete_branch, e.branch_level AS delete_branch_level, CASE
    WHEN e.status = "deleted" THEN e.from
    ELSE e.to
END AS delete_time
// ------------
// find the edges added to the deleted node after the delete time
// ------------
MATCH (n)-[added_e]-(peer)
WHERE added_e.from > delete_time
AND type(added_e) <> "IS_PART_OF"
// ------------
// if the node was deleted on a branch (delete_branch_level > 1), and then updated on main/global (added_e.branch_level = 1), we can ignore it
// ------------
AND added_e.branch_level >= delete_branch_level
AND (added_e.branch = delete_branch OR delete_branch_level = 1)
WITH DISTINCT n, delete_branch, delete_time, added_e, peer AS added_peer
// ------------
// get the branched_from for the branch on which the node was deleted
// ------------
CALL (added_e) {
    MATCH (b:Branch {name: added_e.branch})
    RETURN b.branched_from AS added_e_branched_from
}
// ------------
// account for the following situations, given that the edge update time is after the node delete time
//  - deleted on main/global, updated on branch
//    - illegal if the delete is before branch.branched_from
//  - deleted on branch, updated on branch
//    - illegal
// ------------
WITH n, delete_branch, delete_time, added_e, added_peer
// case 1: update on branch after delete on branch
WHERE delete_branch = added_e.branch
// case 2: update on branch after delete on main and branch forked after delete on main
OR (
    delete_branch <> added_e.branch
    AND delete_time <= added_e_branched_from
    // > instead of >= here allows for edges updated during a rebase
    AND added_e.from > added_e_branched_from
)
RETURN n.uuid AS n_uuid, delete_branch, delete_time, added_e, added_peer
    """ % {"node_labels": _node_labels(kinds)}
    results = await db.execute_query(query=query)
    violations = []
    for result in results:
        n_uuid = result.get("n_uuid")
        delete_branch = result.get("delete_branch")
        delete_time = result.get("delete_time")
        added_e = result.get("added_e")
        added_e_branch = added_e.get("branch")
        added_e_from = added_e.get("from")
        added_peer = result.get("added_peer")
        violations.append(
            GraphViolation(
                check=GraphCheck.EDGES_AFTER_NODE_DELETE,
                message=(
                    f"Node {n_uuid} was deleted on {delete_branch} at {delete_time} but has an {added_e.type} edge"
                    f" added on branch {added_e_branch} at {added_e_from} to {added_peer.element_id}"
                ),
            )
        )
    return violations


async def _check_duplicate_paths(db: InfrahubDatabase, kinds: list[str] | None) -> list[GraphViolation]:
    """Verify that no duplicate paths exist at the database level."""
    query = """
MATCH path = (p)-[e]->(q)
WHERE %(kind_filter)s
WITH
    elementId(p) AS node_id1,
    e.branch AS branch,
    e.from AS from_time,
    type(e) AS edge_type,
    elementId(q) AS node_id2,
    path
WITH node_id1, branch, from_time, edge_type, node_id2, size(collect(path)) AS num_paths
WHERE num_paths > 1
RETURN node_id1, branch, from_time, edge_type, node_id2, num_paths
    """ % {"kind_filter": _near_kind_filter("p", "q", kinds=kinds)}
    records = await db.execute_query(query=query)
    violations = []
    for record in records:
        node_id1 = record.get("node_id1")
        branch = record.get("branch")
        from_time = record.get("from_time")
        edge_type = record.get("edge_type")
        node_id2 = record.get("node_id2")
        num_paths = record.get("num_paths")
        violations.append(
            GraphViolation(
                check=GraphCheck.DUPLICATE_PATHS,
                message=(
                    f"{num_paths} paths ({branch=},{edge_type=},{from_time=}) between nodes"
                    f" '{node_id1}' and '{node_id2}'"
                ),
            )
        )
    return violations


async def _check_orphaned_active_edges(db: InfrahubDatabase, kinds: list[str] | None) -> list[GraphViolation]:
    """Verify that deleting an attribute or relationship closed the edges hanging off it.

    When a HAS_ATTRIBUTE or IS_RELATED edge is deleted on a branch, the second-level edges the branch holds
    for that field (HAS_VALUE, IS_PROTECTED, HAS_OWNER, HAS_SOURCE, far-side IS_RELATED) should be closed at
    that same moment. An edge left open is orphaned, and one written or closed afterwards is an update to a
    field that is gone.

    Edges on the branch that did the deleting are checked against it, and so are edges on a branch that
    forked afterwards, since that branch inherits the delete. A branch that forked before the delete has
    its own history and is checked against its own delete instead.
    """
    query = """
// ----------------
// Group on the uuid rather than the vertex: a kind update copies the node vertex and both copies point at
// the same field, so an edge left open on either of them means the field is still in use on that branch.
// ----------------
MATCH (n:%(node_labels)s)-[r:HAS_ATTRIBUTE|IS_RELATED]-(field:Attribute|Relationship)
WHERE r.status = "deleted" OR r.to IS NOT NULL
WITH DISTINCT n.uuid AS node_id, field, r.branch AS branch
// ----------------
// Then every edge the branch holds between that uuid and the field, deciding whether it deleted it
// ----------------
MATCH (node_copy:Node {uuid: node_id})-[r:HAS_ATTRIBUTE|IS_RELATED]-(field)
WHERE r.branch = branch
WITH node_id, field, branch,
    count(CASE WHEN r.status = "active" AND r.to IS NULL THEN 1 END) AS open_edges,
    // The last edge to close is the one that took the field away: a kind migration deletes the old copy's
    // edge and opens the new copy's at the same moment, so the field lives on until that one closes too
    max(CASE WHEN r.status = "deleted" THEN r.from ELSE r.to END) AS delete_time
WHERE open_edges = 0 AND delete_time IS NOT NULL
// ----------------
// The delete writes the field's edges at the same instant, so only what is still open, or what carries a
// later time, is a violation
// ----------------
MATCH (field)-[child:HAS_VALUE|IS_PROTECTED|HAS_OWNER|HAS_SOURCE|IS_RELATED]-(peer)
WHERE coalesce(peer.uuid, "") <> node_id
// ----------------
// A branch that forked after the delete inherits it, so writing the field there is an update to something
// already gone. A rebase re-stamps the edges it carries to the fork point, so only what comes after that
// was written with the delete in view.
// ----------------
AND CASE
    // updates on this branch after the delete
    WHEN child.branch = branch THEN (
        (child.status = "active" AND child.to IS NULL)
        OR child.from > delete_time
        OR child.to > delete_time
    )
    // Updates on a branch that forked after the delete. Branches are cut from the default branch, so only
    // a delete there is inherited: a delete on one branch is invisible to every other one.
    ELSE branch = $default_branch AND EXISTS {
        MATCH (child_branch:Branch {name: child.branch})
        WHERE child_branch.branched_from > delete_time
        AND child.from > child_branch.branched_from
    }
END
RETURN DISTINCT
    field.name AS field_name,
    branch AS deleted_on,
    child.branch AS edge_on,
    labels(field)[0] AS field_type,
    type(child) AS child_type
    """ % {"node_labels": _node_labels(kinds)}
    records = await db.execute_query(query=query, params={"default_branch": registry.default_branch})
    violations = []
    for record in records:
        field_name = record.get("field_name")
        deleted_on = record.get("deleted_on")
        edge_on = record.get("edge_on")
        field_type = record.get("field_type")
        child_type = record.get("child_type")
        location = f"branch '{edge_on}'" if edge_on == deleted_on else f"branch '{edge_on}', deleted on '{deleted_on}'"
        violations.append(
            GraphViolation(
                check=GraphCheck.ORPHANED_ACTIVE_EDGES,
                message=(
                    f"Orphaned active {child_type} edge on {field_type} '{field_name}' "
                    f"where all parent edges are deleted, on {location}"
                ),
            )
        )
    return violations


async def _check_relationship_edge_counts(db: InfrahubDatabase, kinds: list[str] | None) -> list[GraphViolation]:
    """Verify that every Relationship vertex has exactly 0 or 2 active IS_RELATED edges per branch.

    A Relationship vertex connects two Node vertices. For any given branch, there should be
    either 0 active IS_RELATED edges (relationship not active on that branch) or exactly 2
    (one to each Node). Having 1 or 3+ is always invalid.
    """
    # The kind filter selects which Relationship vertices are reported on; the peer count itself always
    # spans every peer, otherwise filtering out one side of a relationship would report a false violation.
    kind_scope = "true" if not kinds else f"""EXISTS {{ MATCH (rel)-[:IS_RELATED]-(:{"|".join(kinds)}) }}"""
    query = """
MATCH (rel:Relationship)
WHERE %(kind_scope)s
// ----------------
// Get all distinct branches from any edge connected to this Relationship
// ----------------
CALL (rel) {
    MATCH (rel)-[e]-()
    RETURN DISTINCT e.branch AS branch
}
// ----------------
// Get the fork point for user branches (NULL when the branch has no vertex)
// branched_from is the fork point a branch reads the default branch through, and a rebase moves it forward
// ----------------
OPTIONAL MATCH (br:Branch {name: branch})
WITH rel, branch, br.branched_from AS branch_branched_from
// ----------------
// Find all peer Nodes this Relationship might connect to
// ----------------
MATCH (rel)-[:IS_RELATED]-(peer:Node)
WITH DISTINCT rel, branch, branch_branched_from, peer
// ----------------
// For each (rel, branch, peer), get the latest IS_RELATED edge visible from this branch
// ----------------
CALL (rel, branch, branch_branched_from, peer) {
    MATCH (rel)-[r:IS_RELATED]-(peer)
    WHERE (r.branch = branch)
       OR (branch_branched_from IS NOT NULL AND r.branch = $default_branch AND r.from < branch_branched_from)
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
            OR (branch <> $default_branch AND r.branch = $default_branch AND r.to > branch_branched_from)
        )
        THEN 1
        ELSE NULL
    END AS is_active

WITH rel, branch, count(is_active) AS active_count
WHERE active_count <> 0 AND active_count <> 2
RETURN rel.name AS rel_name, rel.uuid AS rel_uuid, branch, active_count
    """ % {"kind_scope": kind_scope}
    records = await db.execute_query(query=query, params={"default_branch": registry.default_branch})
    violations = []
    for record in records:
        rel_name = record.get("rel_name")
        rel_uuid = record.get("rel_uuid")
        branch = record.get("branch")
        active_count = record.get("active_count")
        violations.append(
            GraphViolation(
                check=GraphCheck.RELATIONSHIP_EDGE_COUNTS,
                message=(
                    f"Relationship '{rel_name}' ({rel_uuid}) has {active_count} active "
                    f"IS_RELATED edges on branch '{branch}' (expected 0 or 2)"
                ),
            )
        )
    return violations


async def _check_duplicate_attributes(db: InfrahubDatabase, kinds: list[str] | None) -> list[GraphViolation]:
    """Verify that no Node carries two active attributes with the same name on any branch.

    The branch set is derived from the graph rather than taken as an argument, so one call covers every
    branch that touched a node instead of only the one the caller happened to pass.
    """
    query = """
// ----------------
// Filter to only possible duplicated-Attribute Nodes to start with
// ----------------
MATCH (n:%(node_labels)s)-[:HAS_ATTRIBUTE]->(field:Attribute)
WITH n, field.name AS field_name, collect(DISTINCT field) AS fields
WHERE size(fields) > 1
UNWIND fields AS field
// ----------------
// Every branch that touched one of this node's attributes has to be checked, a duplicate
// is only visible from the branch the extra edge was written on
// ----------------
WITH n, field_name, field
CALL (n, field_name) {
    MATCH (n)-[e:HAS_ATTRIBUTE]->(:Attribute {name: field_name})
    RETURN DISTINCT e.branch AS branch
}
// ----------------
// branched_from is the fork point a branch reads the default branch through
// ----------------
OPTIONAL MATCH (br:Branch {name: branch})
WITH n, field_name, field, branch, br.branched_from AS branch_branched_from
// ----------------
// For each (node, attribute, branch), get the latest edge visible from that branch
// ----------------
CALL (n, field, branch, branch_branched_from) {
    MATCH (n)-[r:HAS_ATTRIBUTE]->(field)
    // the global branch is visible from every branch, so an agnostic attribute duplicated there counts too
    WHERE r.branch IN [branch, $global_branch]
       OR (branch_branched_from IS NOT NULL AND r.branch = $default_branch AND r.from < branch_branched_from)
    RETURN r
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
WITH n, branch, field_name, r, branch_branched_from
// ----------------
// A default-branch edge closed after the branch forked is still open as the branch reads it
// ----------------
WHERE r.status = "active"
AND (
    r.to IS NULL
    OR (branch <> $default_branch AND r.branch = $default_branch AND r.to > branch_branched_from)
)
WITH n, branch, field_name, count(*) AS num_fields
WHERE num_fields > 1
RETURN n.uuid AS node_id, branch, field_name, num_fields
    """ % {"node_labels": _node_labels(kinds)}
    results = await db.execute_query(
        query=query,
        params={
            "default_branch": registry.default_branch,
            "global_branch": GLOBAL_BRANCH_NAME,
        },
    )
    violations = []
    for result in results:
        node_id = result.get("node_id")
        branch = result.get("branch")
        field_name = result.get("field_name")
        num_fields = result.get("num_fields")
        violations.append(
            GraphViolation(
                check=GraphCheck.DUPLICATE_ATTRIBUTES,
                message=f"Node '{node_id}' has {num_fields} duplicated attributes with {field_name=} on {branch=}",
            )
        )
    return violations


async def _check_attribute_edge_branch(db: InfrahubDatabase, kinds: list[str] | None) -> list[GraphViolation]:
    """Verify that an Attribute's live edges sit on the branch its branch support implies.

    A branch-agnostic attribute, and a branch-local attribute of a branch-agnostic node, are stored once
    on the global branch so that every branch reads the same value; anything else is stored on a branch.
    Only open, active edges are judged: a deleted branch-agnostic attribute is deliberately tombstoned
    at branch level, and the closed edges of same-uuid node copies are history rather than current state.
    """
    query = """
MATCH (n:%(node_labels)s)-[owning:HAS_ATTRIBUTE]->(a:Attribute)
WHERE owning.status = "active" AND owning.to IS NULL
WITH n, a, owning,
    (a.branch_support = $agnostic OR (a.branch_support = $local AND n.branch_support = $agnostic)) AS expects_global
OPTIONAL MATCH (a)-[prop]->()
WHERE prop.status = "active" AND prop.to IS NULL
WITH n, a, owning, expects_global, collect(prop) AS props
UNWIND [owning] + props AS e
WITH n, a, expects_global, e,
    CASE WHEN (e.branch = $global_branch) <> expects_global THEN "branch" ELSE "branch_level" END AS reason
WHERE (e.branch = $global_branch) <> expects_global
   OR (e.branch = $global_branch AND (e.branch_level IS NULL OR e.branch_level <> 1))
RETURN n.uuid AS node_id, a.name AS field_name, a.branch_support AS branch_support, expects_global,
       e.branch AS branch, e.branch_level AS branch_level, reason,
       collect(DISTINCT type(e)) AS edge_types, count(*) AS num_edges
    """ % {"node_labels": _node_labels(kinds)}
    results = await db.execute_query(
        query=query,
        params={
            "global_branch": GLOBAL_BRANCH_NAME,
            "agnostic": BranchSupportType.AGNOSTIC.value,
            "local": BranchSupportType.LOCAL.value,
        },
    )
    violations = []
    for result in results:
        node_id = result.get("node_id")
        field_name = result.get("field_name")
        branch_support = result.get("branch_support")
        branch = result.get("branch")
        branch_level = result.get("branch_level")
        num_edges = result.get("num_edges")
        edge_types = ",".join(sorted(result.get("edge_types")))
        if result.get("reason") == "branch_level":
            problem = f"on {branch=} with {branch_level=}, expected branch_level 1"
        elif result.get("expects_global"):
            problem = f"on {branch=}, expected '{GLOBAL_BRANCH_NAME}'"
        else:
            problem = f"on {branch=}, expected a branch of its own"
        violations.append(
            GraphViolation(
                check=GraphCheck.ATTRIBUTE_EDGE_BRANCH,
                message=(
                    f"Attribute {field_name=} of node '{node_id}' with {branch_support=}"
                    f" has {num_edges} active {edge_types} edge(s) {problem}"
                ),
            )
        )
    return violations


async def collect_graph_violations(db: InfrahubDatabase, kinds: list[str] | None = None) -> list[GraphViolation]:
    """Run every graph-integrity check and return all violations found.

    Args:
        kinds: when given, restrict the checks to vertices carrying one of these labels. Checks that
            anchor on Attribute or Relationship vertices resolve the label through the Node they hang off.

    """
    violations = []
    violations.extend(await _check_duplicate_paths(db=db, kinds=kinds))
    violations.extend(await _check_duplicate_relationships(db=db, kinds=kinds))
    violations.extend(await _check_duplicate_attributes(db=db, kinds=kinds))
    violations.extend(await _check_edges_after_node_delete(db=db, kinds=kinds))
    violations.extend(await _check_orphaned_active_edges(db=db, kinds=kinds))
    violations.extend(await _check_relationship_edge_counts(db=db, kinds=kinds))
    violations.extend(await _check_attribute_edge_branch(db=db, kinds=kinds))
    return violations


async def verify_graph(db: InfrahubDatabase, kinds: list[str] | None = None) -> None:
    """Run every graph-integrity check, reporting all violations found together.

    Args:
        kinds: when given, restrict the checks to vertices carrying one of these labels.

    Raises:
        GraphValidationError: When any check reports a violation.

    """
    violations = await collect_graph_violations(db=db, kinds=kinds)
    if violations:
        raise GraphValidationError(violations=violations)
