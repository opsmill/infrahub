from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.core.constants import RelationshipDirection
    from infrahub.database import InfrahubDatabase


class DependentNodesQuery(Query):
    """Return the nodes of a kind related, through a named relationship, to any of a set of peer nodes.

    The path is traversed in the relationship's own direction, so a kind whose relationship points at
    its own kind resolves only the nodes on the owning side of the peers, not those on the opposite
    side.

    Considers edges at the timestamp on the input branch, default branch, and global branch, regardless
    of when the input branch forked from the default branch. That is, changes made on the default branch
    after the input branch was created WILL be included in the results.

    Each hop of the path (node→relationship and relationship→peer) is resolved to a single winner
    across the visible branches: the latest edge on the deepest branch decides, so a change on the
    input branch overrides the default branch. The user branch will always override the default
    branch if changes conflict.
    """

    name = "relationship_dependents"
    type = QueryType.READ

    def __init__(
        self,
        node_kind: str,
        relationship_identifier: str,
        relationship_direction: RelationshipDirection,
        peer_uuids: list[str],
        default_branch_name: str,
        **kwargs: Any,
    ) -> None:
        self.node_kind = node_kind
        self.relationship_identifier = relationship_identifier
        self.relationship_direction = relationship_direction
        self.peer_uuids = peer_uuids
        self.default_branch_name = default_branch_name
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "rel_identifier": self.relationship_identifier,
            "peer_uuids": self.peer_uuids,
            "at": self.at.to_string(),
            "branch": self.branch.name,
            "default_branch": self.default_branch_name,
            "global_branch": GLOBAL_BRANCH_NAME,
        }
        query_arrows = self.get_query_arrows(direction=self.relationship_direction)
        query = """
// --------------------
// start with all possible active Relationship paths on a branch we care about
// --------------------
MATCH (node:%(node_kind)s)%(lstart)s[r1:IS_RELATED]%(lend)s(rel:Relationship {name: $rel_identifier})%(rstart)s[r2:IS_RELATED]%(rend)s(peer)
WHERE peer.uuid IN $peer_uuids
AND peer <> node
AND r1.branch IN [$branch, $default_branch, $global_branch]
AND r1.status = "active"
AND r1.from <= $at
AND (r1.to IS NULL OR r1.to >= $at)
AND r2.branch IN [$branch, $default_branch, $global_branch]
AND r2.status = "active"
AND r2.from <= $at
AND (r2.to IS NULL OR r2.to >= $at)
WITH DISTINCT peer, rel, node
// --------------------
// keep only active edges. the latest edge on the deepest branch wins.
// --------------------
CALL (node, rel) {
    MATCH (node)%(lstart)s[r:IS_RELATED]%(lend)s(rel)
    WHERE r.branch IN [$branch, $default_branch, $global_branch]
    AND r.from <= $at
    AND (r.to IS NULL OR r.to >= $at)
    WITH r.status = "active" AS is_active
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
    WITH is_active
    WHERE is_active = TRUE
    RETURN TRUE AS node_rel_is_live
}
CALL (rel, peer) {
    MATCH (rel)%(rstart)s[r:IS_RELATED]%(rend)s(peer)
    WHERE r.branch IN [$branch, $default_branch, $global_branch]
    AND r.from <= $at
    AND (r.to IS NULL OR r.to >= $at)
    WITH r.status = "active" AS is_active
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
    WITH is_active
    WHERE is_active = TRUE
    RETURN TRUE AS rel_peer_is_live
}
        """ % {
            "node_kind": self.node_kind,
            "lstart": query_arrows.left.start,
            "lend": query_arrows.left.end,
            "rstart": query_arrows.right.start,
            "rend": query_arrows.right.end,
        }
        self.add_to_query(query=query)
        self.return_labels = ["DISTINCT node.uuid AS node_uuid"]

    def get_dependent_uuids(self) -> set[str]:
        return {result.get_as_type("node_uuid", return_type=str) for result in self.results}
