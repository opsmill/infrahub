from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, NamedTuple

from infrahub.core.constants import RelationshipDirection
from infrahub.core.query import Query, QueryType
from infrahub.core.query.branch_windows import (
    build_branch_window_query,
    build_branch_windows_query,
    render_outranks,
    render_window_filter,
)
from infrahub.exceptions import BranchNotFoundError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.database import InfrahubDatabase


class LinkPattern(NamedTuple):
    """A kind of link, seen from the node at `kind`.

    The direction is part of the pattern because one kind can declare an inbound and an outbound relationship with
    the same identifier and peer kind.
    """

    kind: str
    identifier: str
    direction: RelationshipDirection
    peer_kind: str

    def to_param(self) -> list[str]:
        return [self.kind, self.identifier, self.direction.value, self.peer_kind]


@dataclass(frozen=True)
class DeleteSetNode:
    uuid: str
    kind: str
    is_agnostic: bool
    """Whether the node exists on the global branch, so deleting it removes it from every branch."""


@dataclass(frozen=True, order=True)
class RequiredPeerLink:
    """A link from a peer with a required relationship to a node being deleted."""

    deleted_kind: str
    deleted_id: str
    identifier: str
    direction: RelationshipDirection
    """The direction of the link seen from the node being deleted."""
    peer_kind: str
    peer_id: str

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> RequiredPeerLink:
        return cls(
            deleted_kind=row["deleted_kind"],
            deleted_id=row["deleted_id"],
            identifier=row["identifier"],
            direction=RelationshipDirection(row["direction"]),
            peer_kind=row["peer_kind"],
            peer_id=row["peer_id"],
        )


@dataclass(frozen=True)
class NodeDeleteCascadeQueryResult:
    nodes: list[DeleteSetNode]
    """The nodes already known and every node the cascade reached, in the request branch's window."""

    frontier_ids: list[str]
    """The nodes reached at the last level, from which the cascade continues."""

    required_links: list[RequiredPeerLink]
    """The links to peers outside the delete set, empty when the cascade continues."""


@dataclass(frozen=True)
class RequiredPeerLinkOnBranches:
    link: RequiredPeerLink
    branch_names: list[str]
    """The branches other than the request branch whose window holds the link."""


def _render_latest_active_edge(edge: str, left: str, right: str, edge_type: str) -> str:
    """Render whether `edge` between `left` and `right` is active and no other edge visible in `window` outranks it."""
    competitor = f"{edge}_competitor"
    return """%(edge)s.status = "active" AND %(edge_visible)s
        AND NOT EXISTS {
            MATCH (%(left)s)-[%(competitor)s:%(edge_type)s]-(%(right)s)
            WHERE %(competitor_visible)s AND %(outranks)s
        }""" % {
        "edge": edge,
        "edge_visible": render_window_filter(edge=edge),
        "left": left,
        "competitor": competitor,
        "edge_type": edge_type,
        "right": right,
        "competitor_visible": render_window_filter(edge=competitor),
        "outranks": render_outranks(edge=edge, competitor=competitor),
    }


def _render_link_direction(node: str, node_edge: str, relationship: str, peer_edge: str) -> str:
    """Render the direction of the link seen from `node`, or null when no relationship creates such edges."""
    return """CASE
            WHEN startNode(%(node_edge)s) = %(node)s AND startNode(%(peer_edge)s) = %(relationship)s THEN "outbound"
            WHEN startNode(%(node_edge)s) = %(node)s AND endNode(%(peer_edge)s) = %(relationship)s THEN "bidirectional"
            WHEN endNode(%(node_edge)s) = %(node)s AND endNode(%(peer_edge)s) = %(relationship)s THEN "inbound"
        END""" % {"node": node, "node_edge": node_edge, "relationship": relationship, "peer_edge": peer_edge}


def _render_node_exists(node: str) -> str:
    """Render whether `node` exists in `window`."""
    part_of = f"{node}_part_of"
    root = f"{node}_root"
    return """EXISTS {
            MATCH (%(node)s)-[%(part_of)s:IS_PART_OF]->(%(root)s:Root)
            WHERE %(part_of_latest_active)s
        }""" % {
        "node": node,
        "part_of": part_of,
        "root": root,
        "part_of_latest_active": _render_latest_active_edge(
            edge=part_of, left=node, right=root, edge_type="IS_PART_OF"
        ),
    }


class NodeDeleteCascadeQuery(Query):
    """Read the nodes a delete cascades to in the request branch's window, and the required peers left outside them.

    Each level of the cascade is one subquery, so the cost grows with the number of nodes reached rather than with
    the number of paths to them. The query returns a single row.
    """

    name = "node_delete_cascade"
    type = QueryType.READ
    insert_limit = False

    def __init__(
        self,
        request_window_name: str,
        known_ids: Sequence[str],
        frontier_ids: Sequence[str],
        cascade_patterns: Sequence[LinkPattern],
        required_patterns: Sequence[LinkPattern],
        levels: int,
        levels_cover_cascade: bool,
        **kwargs: Any,
    ) -> None:
        """Build the query.

        Args:
            request_window_name: The branch whose window decides which links and nodes exist.
            known_ids: The nodes already in the delete set, including `frontier_ids`.
            frontier_ids: The nodes the cascade continues from.
            cascade_patterns: The links a delete cascades over, from the deleted node's side.
            required_patterns: The links of a required relationship, from the deleted node's side.
            levels: The number of cascade levels to follow.
            levels_cover_cascade: Whether `levels` reaches the end of every cascade, so the required peers are read
                even when the last level reaches a node.

        """
        self.request_window_name = request_window_name
        self.known_ids = list(known_ids)
        self.frontier_ids = list(frontier_ids)
        self.cascade_patterns = list(cascade_patterns)
        self.required_patterns = list(required_patterns)
        self.levels = levels
        self.levels_cover_cascade = levels_cover_cascade
        super().__init__(**kwargs)
        self.limit = 1

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        window_query, window_params = build_branch_window_query(branch_name=self.request_window_name, at=self.at)
        self.params.update(window_params)
        self.params["known_ids"] = self.known_ids
        self.params["frontier_ids"] = self.frontier_ids
        self.params["cascade_patterns"] = [pattern.to_param() for pattern in self.cascade_patterns]
        self.params["cascade_identifiers"] = sorted({pattern.identifier for pattern in self.cascade_patterns})
        self.params["required_patterns"] = [pattern.to_param() for pattern in self.required_patterns]
        self.params["required_identifiers"] = sorted({pattern.identifier for pattern in self.required_patterns})
        self.params["levels_cover_cascade"] = self.levels_cover_cascade

        level_query = """
        CALL (window, frontier, nodes) {
            UNWIND frontier AS a
            MATCH (a)-[r1:IS_RELATED]-(rl:Relationship)-[r2:IS_RELATED]-(b:Node)
            WHERE rl.name IN $cascade_identifiers
            AND [a.kind, rl.name, %(direction)s, b.kind] IN $cascade_patterns
            AND NOT b IN nodes
            AND %(r1_latest_active)s
            AND %(r2_latest_active)s
            AND %(b_exists)s
            RETURN collect(DISTINCT b) AS next_level
        }
        WITH window, next_level AS frontier, nodes + next_level AS nodes
        """ % {
            "r1_latest_active": _render_latest_active_edge(edge="r1", left="a", right="rl", edge_type="IS_RELATED"),
            "r2_latest_active": _render_latest_active_edge(edge="r2", left="rl", right="b", edge_type="IS_RELATED"),
            "b_exists": _render_node_exists(node="b"),
            "direction": _render_link_direction(node="a", node_edge="r1", relationship="rl", peer_edge="r2"),
        }

        query = """
        %(window_query)s
        MATCH (known:Node)
        WHERE known.uuid IN $known_ids
        WITH window, collect(DISTINCT known) AS nodes
        WITH window, nodes, [node IN nodes WHERE node.uuid IN $frontier_ids] AS frontier
        %(levels)s
        CALL (nodes) {
            UNWIND nodes AS n
            RETURN collect({
                uuid: n.uuid,
                kind: n.kind,
                is_agnostic: EXISTS {
                    MATCH (n)-[global_part_of:IS_PART_OF]->(:Root)
                    WHERE global_part_of.branch = $global_branch_name
                }
            }) AS delete_set
        }
        WITH window, nodes, frontier, delete_set, [node IN nodes | node.uuid] AS delete_ids
        CALL (window, nodes, frontier, delete_ids) {
            // A cascade that goes on past the last level can still reach a required peer, so it is not read yet
            UNWIND CASE WHEN $levels_cover_cascade OR size(frontier) = 0 THEN nodes ELSE [] END AS n
            MATCH (n)-[d1:IS_RELATED]-(drl:Relationship)-[d2:IS_RELATED]-(peer:Node)
            WHERE drl.name IN $required_identifiers
            AND [n.kind, drl.name, %(direction)s, peer.kind] IN $required_patterns
            AND NOT peer.uuid IN delete_ids
            AND %(d1_latest_active)s
            AND %(d2_latest_active)s
            AND %(peer_exists)s
            RETURN collect(DISTINCT {
                deleted_kind: n.kind,
                deleted_id: n.uuid,
                identifier: drl.name,
                direction: %(direction)s,
                peer_kind: peer.kind,
                peer_id: peer.uuid
            }) AS required_links
        }
        WITH delete_set, [node IN frontier | node.uuid] AS frontier_ids, required_links
        """ % {
            "window_query": window_query,
            "levels": level_query * self.levels,
            "d1_latest_active": _render_latest_active_edge(edge="d1", left="n", right="drl", edge_type="IS_RELATED"),
            "d2_latest_active": _render_latest_active_edge(edge="d2", left="drl", right="peer", edge_type="IS_RELATED"),
            "peer_exists": _render_node_exists(node="peer"),
            "direction": _render_link_direction(node="n", node_edge="d1", relationship="drl", peer_edge="d2"),
        }
        self.add_to_query(query)
        self.return_labels = ["delete_set", "frontier_ids", "required_links"]

    def get_data(self) -> NodeDeleteCascadeQueryResult:
        """Return the delete set.

        Raises:
            BranchNotFoundError: No branch has the request window's name, so the query returned no row.

        """
        for result in self.get_results():
            required_links: list[dict[str, Any]] = result.get_as_type(label="required_links", return_type=list)
            return NodeDeleteCascadeQueryResult(
                nodes=result.get_as_list_of_type(label="delete_set", return_type=DeleteSetNode),
                frontier_ids=result.get_as_list_of_type(label="frontier_ids", return_type=str),
                required_links=[RequiredPeerLink.from_row(row) for row in required_links],
            )
        raise BranchNotFoundError(identifier=self.request_window_name)


class NodeDeleteOtherBranchesQuery(Query):
    """Read the required links to the given branch-agnostic nodes in the window of every live branch but one.

    A link counts in a window when the relationship is required on that branch, and the peer is not one of the
    given nodes. The edges of each link are read once and tested in every window. The query returns a single row.
    """

    name = "node_delete_other_branches"
    type = QueryType.READ
    insert_limit = False

    def __init__(
        self,
        request_window_name: str,
        agnostic_ids: Sequence[str],
        required_patterns_by_branch: dict[str, list[LinkPattern]],
        **kwargs: Any,
    ) -> None:
        """Build the query.

        Args:
            request_window_name: The branch whose window is left out.
            agnostic_ids: The branch-agnostic nodes being deleted.
            required_patterns_by_branch: The links of a required relationship on each branch, from the deleted
                node's side; a branch left out has none.

        """
        self.request_window_name = request_window_name
        self.agnostic_ids = list(agnostic_ids)
        self.required_patterns_by_branch = required_patterns_by_branch
        super().__init__(**kwargs)
        self.limit = 1

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        windows_query, windows_params = build_branch_windows_query(at=self.at, enabled=True)
        self.params.update(windows_params)
        self.params["request_window_name"] = self.request_window_name
        self.params["agnostic_ids"] = self.agnostic_ids
        self.params["required_by_branch"] = {
            branch_name: [pattern.to_param() for pattern in patterns]
            for branch_name, patterns in self.required_patterns_by_branch.items()
        }
        all_required_patterns = sorted(
            {pattern for patterns in self.required_patterns_by_branch.values() for pattern in patterns}
        )
        self.params["all_required_patterns"] = [pattern.to_param() for pattern in all_required_patterns]
        self.params["all_required_identifiers"] = sorted({pattern.identifier for pattern in all_required_patterns})

        query = """
        %(windows_query)s
        WITH [window IN branch_windows WHERE window.name <> $request_window_name] AS windows
        MATCH (src:Node)
        WHERE src.uuid IN $agnostic_ids
        WITH windows, src, [(src)-[r:IS_PART_OF]->(:Root) | r {.branch, .branch_level, .from, .to, .status}] AS src_part_of
        MATCH (src)-[r1:IS_RELATED]-(rl:Relationship)-[r2:IS_RELATED]-(dst:Node)
        WHERE rl.name IN $all_required_identifiers
        AND [src.kind, rl.name, %(direction)s, dst.kind] IN $all_required_patterns
        AND NOT dst.uuid IN $agnostic_ids
        AND r1.status = "active" AND r1.from <= $windows_at
        AND r2.status = "active" AND r2.from <= $windows_at
        WITH DISTINCT windows, src, src_part_of, rl, dst, %(direction)s AS direction
        // Each edge group is read once, so testing it in every window reads nothing more
        WITH windows, src, rl, dst, direction, [
            src_part_of,
            [(src)-[r:IS_RELATED]-(rl) | r {.branch, .branch_level, .from, .to, .status}],
            [(rl)-[r:IS_RELATED]-(dst) | r {.branch, .branch_level, .from, .to, .status}],
            [(dst)-[r:IS_PART_OF]->(:Root) | r {.branch, .branch_level, .from, .to, .status}]
        ] AS edge_groups
        UNWIND windows AS window
        WITH src, rl, dst, direction, window, edge_groups
        WHERE [src.kind, rl.name, direction, dst.kind] IN $required_by_branch[window.name]
        AND all(edges IN edge_groups WHERE any(edge IN edges WHERE edge.status = "active" AND %(edge_visible)s
            AND none(r IN edges WHERE %(competitor_visible)s AND %(outranks)s)))
        WITH src, rl, dst, direction, collect(window.name) AS branch_names
        WITH collect({
            deleted_kind: src.kind,
            deleted_id: src.uuid,
            identifier: rl.name,
            direction: direction,
            peer_kind: dst.kind,
            peer_id: dst.uuid,
            branch_names: branch_names
        }) AS links
        """ % {
            "windows_query": windows_query,
            "edge_visible": render_window_filter(edge="edge"),
            "competitor_visible": render_window_filter(edge="r"),
            "outranks": render_outranks(edge="edge"),
            "direction": _render_link_direction(node="src", node_edge="r1", relationship="rl", peer_edge="r2"),
        }
        self.add_to_query(query)
        self.return_labels = ["links"]

    def get_data(self) -> list[RequiredPeerLinkOnBranches]:
        links_on_branches: list[RequiredPeerLinkOnBranches] = []
        for result in self.get_results():
            links: list[dict[str, Any]] = result.get_as_type(label="links", return_type=list)
            links_on_branches.extend(
                RequiredPeerLinkOnBranches(
                    link=RequiredPeerLink.from_row(link), branch_names=list(link["branch_names"])
                )
                for link in links
            )
        return links_on_branches
