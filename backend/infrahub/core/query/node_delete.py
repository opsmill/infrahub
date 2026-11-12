from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query, QueryType
from infrahub.core.query.branch_windows import (
    build_branch_window_query,
    build_branch_windows_query,
    render_outranks,
    render_window_filter,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.database import InfrahubDatabase

RelationshipTriple = tuple[str, str, str]
"""A node kind, a relationship identifier and the kind of the peer on the other side of the link."""


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
    peer_kind: str
    peer_id: str


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
    return f"""{edge}.status = "active" AND {render_window_filter(edge=edge)}
        AND NOT EXISTS {{
            MATCH ({left})-[{competitor}:{edge_type}]-({right})
            WHERE {render_window_filter(edge=competitor)} AND {render_outranks(edge=edge, competitor=competitor)}
        }}"""


def _render_node_exists(node: str) -> str:
    """Render whether `node` exists in `window`."""
    part_of = f"{node}_part_of"
    root = f"{node}_root"
    return f"""EXISTS {{
            MATCH ({node})-[{part_of}:IS_PART_OF]->({root}:Root)
            WHERE {_render_latest_active_edge(edge=part_of, left=node, right=root, edge_type="IS_PART_OF")}
        }}"""


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
        cascade_triples: Sequence[RelationshipTriple],
        required_triples: Sequence[RelationshipTriple],
        levels: int,
        levels_cover_cascade: bool,
        **kwargs: Any,
    ) -> None:
        """Build the query.

        Args:
            request_window_name: The branch whose window decides which links and nodes exist.
            known_ids: The nodes already in the delete set, including `frontier_ids`.
            frontier_ids: The nodes the cascade continues from.
            cascade_triples: The links a delete cascades over, from the deleted node's side.
            required_triples: The links of a required relationship, from the deleted node's side.
            levels: The number of cascade levels to follow.
            levels_cover_cascade: Whether `levels` reaches the end of every cascade, so the required peers are read
                even when the last level reaches a node.

        """
        self.request_window_name = request_window_name
        self.known_ids = list(known_ids)
        self.frontier_ids = list(frontier_ids)
        self.cascade_triples = [list(triple) for triple in cascade_triples]
        self.required_triples = [list(triple) for triple in required_triples]
        self.levels = levels
        self.levels_cover_cascade = levels_cover_cascade
        super().__init__(**kwargs)
        self.limit = 1

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        window_query, window_params = build_branch_window_query(branch_name=self.request_window_name, at=self.at)
        self.params.update(window_params)
        self.params["known_ids"] = self.known_ids
        self.params["frontier_ids"] = self.frontier_ids
        self.params["cascade_triples"] = self.cascade_triples
        self.params["cascade_identifiers"] = sorted({triple[1] for triple in self.cascade_triples})
        self.params["required_triples"] = self.required_triples
        self.params["required_identifiers"] = sorted({triple[1] for triple in self.required_triples})
        self.params["levels_cover_cascade"] = self.levels_cover_cascade

        level_query = """
        CALL (window, frontier, nodes) {
            UNWIND frontier AS a
            MATCH (a)-[r1:IS_RELATED]-(rl:Relationship)-[r2:IS_RELATED]-(b:Node)
            WHERE rl.name IN $cascade_identifiers
            AND [a.kind, rl.name, b.kind] IN $cascade_triples
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
            AND [n.kind, drl.name, peer.kind] IN $required_triples
            AND NOT peer.uuid IN delete_ids
            AND %(d1_latest_active)s
            AND %(d2_latest_active)s
            AND %(peer_exists)s
            RETURN collect(DISTINCT {
                deleted_kind: n.kind,
                deleted_id: n.uuid,
                identifier: drl.name,
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
        }
        self.add_to_query(query)
        self.return_labels = ["delete_set", "frontier_ids", "required_links"]

    def get_data(self) -> NodeDeleteCascadeQueryResult:
        for result in self.get_results():
            return NodeDeleteCascadeQueryResult(
                nodes=result.get_as_list_of_type("delete_set", DeleteSetNode),
                frontier_ids=result.get_as_list_of_type("frontier_ids", str),
                required_links=result.get_as_list_of_type("required_links", RequiredPeerLink),
            )
        return NodeDeleteCascadeQueryResult(nodes=[], frontier_ids=[], required_links=[])


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
        required_triples_by_branch: dict[str, list[RelationshipTriple]],
        **kwargs: Any,
    ) -> None:
        """Build the query.

        Args:
            request_window_name: The branch whose window is left out.
            agnostic_ids: The branch-agnostic nodes being deleted.
            required_triples_by_branch: The links of a required relationship on each branch, from the deleted node's
                side; a branch left out has none.

        """
        self.request_window_name = request_window_name
        self.agnostic_ids = list(agnostic_ids)
        self.required_triples_by_branch = {
            branch_name: [list(triple) for triple in triples]
            for branch_name, triples in required_triples_by_branch.items()
        }
        super().__init__(**kwargs)
        self.limit = 1

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        windows_query, windows_params = build_branch_windows_query(at=self.at, enabled=True)
        self.params.update(windows_params)
        self.params["request_window_name"] = self.request_window_name
        self.params["agnostic_ids"] = self.agnostic_ids
        self.params["required_by_branch"] = self.required_triples_by_branch
        self.params["all_required_triples"] = sorted(
            {tuple(triple) for triples in self.required_triples_by_branch.values() for triple in triples}
        )

        query = """
        %(windows_query)s
        WITH [window IN branch_windows WHERE window.name <> $request_window_name] AS windows
        MATCH (src:Node)
        WHERE src.uuid IN $agnostic_ids
        WITH windows, src, [(src)-[r:IS_PART_OF]->(:Root) | r {%(edge_fields)s}] AS src_part_of
        MATCH (src)-[r1:IS_RELATED]-(rl:Relationship)-[r2:IS_RELATED]-(dst:Node)
        WHERE [src.kind, rl.name, dst.kind] IN $all_required_triples
        AND NOT dst.uuid IN $agnostic_ids
        AND r1.status = "active" AND r1.from <= $windows_at
        AND r2.status = "active" AND r2.from <= $windows_at
        WITH DISTINCT windows, src, src_part_of, rl, dst
        // Each edge group is read once, so testing it in every window reads nothing more
        WITH windows, src, rl, dst, [
            src_part_of,
            [(src)-[r:IS_RELATED]-(rl) | r {%(edge_fields)s}],
            [(rl)-[r:IS_RELATED]-(dst) | r {%(edge_fields)s}],
            [(dst)-[r:IS_PART_OF]->(:Root) | r {%(edge_fields)s}]
        ] AS edge_groups
        UNWIND windows AS window
        WITH src, rl, dst, window, edge_groups
        WHERE [src.kind, rl.name, dst.kind] IN $required_by_branch[window.name]
        AND all(edges IN edge_groups WHERE any(edge IN edges WHERE edge.status = "active" AND %(edge_visible)s
            AND none(r IN edges WHERE %(competitor_visible)s AND %(outranks)s)))
        WITH src, rl, dst, collect(window.name) AS branch_names
        WITH collect({
            deleted_kind: src.kind,
            deleted_id: src.uuid,
            identifier: rl.name,
            peer_kind: dst.kind,
            peer_id: dst.uuid,
            branch_names: branch_names
        }) AS links
        """ % {
            "windows_query": windows_query,
            "edge_fields": ".branch, .branch_level, .from, .to, .status",
            "edge_visible": render_window_filter(edge="edge"),
            "competitor_visible": render_window_filter(edge="r"),
            "outranks": render_outranks(edge="edge"),
        }
        self.add_to_query(query)
        self.return_labels = ["links"]

    def get_data(self) -> list[RequiredPeerLinkOnBranches]:
        links_on_branches: list[RequiredPeerLinkOnBranches] = []
        for result in self.get_results():
            links: list[dict[str, Any]] = result.get_as_type("links", list)
            links_on_branches.extend(
                RequiredPeerLinkOnBranches(
                    link=RequiredPeerLink(
                        deleted_kind=link["deleted_kind"],
                        deleted_id=link["deleted_id"],
                        identifier=link["identifier"],
                        peer_kind=link["peer_kind"],
                        peer_id=link["peer_id"],
                    ),
                    branch_names=list(link["branch_names"]),
                )
                for link in links
            )
        return links_on_branches
