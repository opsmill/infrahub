from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypedDict

from infrahub.core.constants import PROFILE_NODE_RELATIONSHIP_IDENTIFIER, InfrahubKind, RelationshipKind
from infrahub.core.query import Query, QueryType
from infrahub.core.query.subquery import ranks_latest_value
from infrahub.core.query.vertex_metadata import stamp_vertex_metadata

from .constants import MAX_INHERITANCE_DEPTH, NO_OWNER_VERTEX_UUID, PROFILE_PRIORITY_ATTRIBUTE
from .models import NODE_HOLDER, HolderKey, HolderKind

if TYPE_CHECKING:
    from collections.abc import Generator

    from infrahub.core.branch import Branch
    from infrahub.core.schema import MainSchemaTypes, RelationshipSchema
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


def parent_relationship(schema: MainSchemaTypes) -> RelationshipSchema | None:
    """Return the relationship that passes owners down to the nodes of a kind: the Parent one, else the hierarchy parent."""
    return next((rel for rel in schema.relationships if rel.kind == RelationshipKind.PARENT), None) or next(
        (rel for rel in schema.relationships if rel.kind == RelationshipKind.HIERARCHY and rel.name == "parent"), None
    )


def parent_relationships_by_kind(schema_branch: SchemaBranch) -> dict[str, dict[str, str]]:
    """Return the relationship that passes owners down to each node kind.

    Each entry holds the `identifier` and the `direction` of the relationship, and the kind of its `peer`.
    """
    parents: dict[str, dict[str, str]] = {}
    for name in schema_branch.node_names:
        relationship = parent_relationship(schema=schema_branch.get_node(name=name, duplicate=False))
        if relationship is not None and relationship.identifier:
            parents[name] = {
                "identifier": relationship.identifier,
                "direction": relationship.direction.value,
                "peer": relationship.peer,
            }
    return parents


class ActiveEdgeFilter:
    """Build the Cypher conditions that an edge is the active edge between its two vertices, as a branch reads it."""

    params_prefix: str

    def __init__(self, branch: Branch, at: Timestamp) -> None:
        self.branch = branch
        self.at = at
        self.ranks_edges = ranks_latest_value(branch=branch, branch_agnostic=False)

    def _active(self, edge: str, pattern: str) -> str:
        """Return the condition that an edge is the active edge between its two vertices.

        Args:
            edge: The variable of the edge.
            pattern: The pattern of the edges between the same two vertices, with `%s` for the edge variable.

        """
        condition = f'{self._branch_filter(edge)} AND {edge}.status = "active"'
        if not self.ranks_edges:
            return condition
        # A branch hides an edge of the default branch with a later `deleted` edge, and leaves the hidden edge open.
        later = f"{edge}_later"
        return f"""{condition} AND NOT EXISTS {{
            MATCH {pattern % later}
            WHERE {self._branch_filter(later)} AND {later}.status = "deleted"
            AND ({later}.branch_level > {edge}.branch_level
                OR ({later}.branch_level = {edge}.branch_level AND {later}.from > {edge}.from))
        }}"""

    def _branch_filter(self, edge: str) -> str:
        branch_filter, _ = self.branch.get_query_filter_path(
            at=self.at, variable_name=edge, params_prefix=self.params_prefix
        )
        return branch_filter

    def _holds_owner_edges(self, node: str) -> str:
        return f"""EXISTS {{
        MATCH ({node})-[own:HAS_OWNER|HAS_NO_OWNER]->(own_peer)
        WHERE {self._active("own", f"({node})-[%s:HAS_OWNER|HAS_NO_OWNER]->(own_peer)")}
    }}"""

    def _is_template_copy(self, node: str) -> str:
        """Return the condition that the owner edges of a node are a copy from an object template."""
        return f"""EXISTS {{
        MATCH ({node})-[copied:HAS_OWNER_SOURCE]->(template)
        WHERE {self._active("copied", f"({node})-[%s:HAS_OWNER_SOURCE]->(template)")}
    }}"""


class LineageWalk(ActiveEdgeFilter):
    """Build the Cypher that finds the nodes whose stored states give the owners that apply to some nodes."""

    params_prefix = ""

    def _has_own_owners(self, node: str) -> str:
        return f"({self._holds_owner_edges(node=node)} AND NOT {self._is_template_copy(node=node)})"

    def render(self, branch_filter: str) -> str:
        """Return the Cypher that binds `node_id` to each node of `$node_ids`, to its parents and to its profiles.

        The walk to the parents stops at the depth limit, at a node with its own owners and at a copy from an
        object template. The profiles are the ones of each node that takes owners from its profiles.
        """
        return """
UNWIND $node_ids AS start_id
MATCH (start:Node {uuid: start_id})
CALL (start) {
    MATCH (start) (
        (c:Node)-[w1:IS_RELATED]-(wl:Relationship)-[w2:IS_RELATED]-(p:Node)
        WHERE wl.name = $parent_by_kind[c.kind].identifier AND c <> p
        AND %(w1_active)s
        AND %(w2_active)s
        AND (
            ($parent_by_kind[c.kind].direction = "outbound" AND startNode(w1) = c AND startNode(w2) = wl)
            OR ($parent_by_kind[c.kind].direction = "inbound" AND startNode(w1) = wl AND startNode(w2) = p)
            OR ($parent_by_kind[c.kind].direction = "bidirectional" AND startNode(w1) = c AND startNode(w2) = p)
        )
        AND NOT %(c_holds_owner_edges)s
    ){0,%(max_depth)s} (member:Node)
    RETURN DISTINCT member
}
WITH DISTINCT member
CALL (member) {
    OPTIONAL MATCH (member)-[r1:IS_RELATED]-(:Relationship {name: $profile_identifier})-[r2:IS_RELATED]-(profile:%(profile_label)s)
    WHERE all(r IN [r1, r2] WHERE %(branch_filter)s)
    AND (($with_attributes AND member.uuid IN $node_ids) OR NOT %(member_has_own_owners)s)
    RETURN collect(DISTINCT profile.uuid) AS profile_ids
}
WITH collect(member.uuid) AS member_ids, collect(profile_ids) AS profile_lists
UNWIND member_ids + reduce(listed = [], ids IN profile_lists | listed + ids) AS node_id
WITH DISTINCT node_id""" % {
            "w1_active": self._active("w1", "(c)-[%s:IS_RELATED]-(wl)"),
            "w2_active": self._active("w2", "(wl)-[%s:IS_RELATED]-(p)"),
            "c_holds_owner_edges": self._holds_owner_edges(node="c"),
            "member_has_own_owners": self._has_own_owners(node="member"),
            "max_depth": MAX_INHERITANCE_DEPTH,
            "profile_label": InfrahubKind.PROFILE,
            "branch_filter": branch_filter,
        }


class ProfilePriority(TypedDict):
    profile_id: str
    priority: int | None


class HeldEdges(TypedDict):
    """The active owner edges of one vertex that holds owners for a node."""

    set_type: str | None
    """The type of the edge from the node to an `OwnerSet`. None for an attribute."""

    attribute: str | None
    identifier: str | None
    direction: str | None
    held: list[list[str]]
    """The type and the peer ID of each edge."""


@dataclass(frozen=True)
class NodeOwnerStateReadQueryResult:
    node_id: str
    kind: str
    held: tuple[tuple[str, str], ...]
    """The type and the peer ID of each active owner edge and source edge of the node vertex."""

    field_holders: tuple[tuple[HolderKey, tuple[tuple[str, str], ...]], ...]
    """The active owner edges of each attribute and of each `OwnerSet` of the node."""

    parent_id: str | None
    profiles: tuple[tuple[str, int | None], ...]


class NodeOwnerStateReadQuery(Query):
    """Read the owner states and the sources that each active node stores, with its parent and its profiles.

    The states are the one of the node vertex and the one of each `OwnerSet` of the node, each with the object
    template that it is a copy from.
    """

    name = "ownership_node_owner_state_read"
    type = QueryType.READ

    def __init__(
        self,
        node_ids: list[str],
        parent_by_kind: dict[str, dict[str, str]],
        attributes: bool = False,
        lineage: bool = False,
        **kwargs: Any,
    ) -> None:
        """Give in `parent_by_kind` the `identifier` and the `direction` of the relationship to the parent of a kind.

        Args:
            attributes: True to read the states of the attributes of each node of `node_ids` also.
            lineage: True to read also the parents above each node, up to the depth limit or to the first node
                with its own owners or with a copy from an object template, and the profiles of each node that
                takes owners from its profiles.

        """
        self.node_ids = node_ids
        self.parent_by_kind = parent_by_kind
        self.attributes = attributes
        self.lineage = lineage
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at)
        attached_filter, _ = self.branch.get_query_filter_path(at=self.at, variable_name="attached")
        self.params.update(branch_params)
        self.params["node_ids"] = self.node_ids
        self.params["parent_by_kind"] = self.parent_by_kind
        self.params["profile_identifier"] = PROFILE_NODE_RELATIONSHIP_IDENTIFIER
        self.params["priority_name"] = PROFILE_PRIORITY_ATTRIBUTE
        self.params["with_attributes"] = self.attributes
        nodes_to_read = "UNWIND $node_ids AS node_id"
        if self.lineage:
            nodes_to_read = LineageWalk(branch=self.branch, at=self.at).render(branch_filter=branch_filter)
        query = """
%(nodes_to_read)s
CALL (node_id) {
    MATCH (n:Node {uuid: node_id})-[r:IS_PART_OF]->(:Root)
    WHERE %(branch_filter)s
    RETURN n, r AS part_of
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
WITH node_id, n, part_of
WHERE part_of.status = "active"
CALL (n) {
    MATCH (n)-[r:HAS_OWNER|HAS_NO_OWNER|HAS_OWNER_SOURCE|HAS_SOURCE]->(peer)
    WHERE %(branch_filter)s
    WITH peer, type(r) AS edge_type, r
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    WITH peer, edge_type, head(collect(r)) AS latest
    WHERE latest.status = "active"
    RETURN collect([edge_type, peer.uuid]) AS held
}
CALL (n) {
    WITH n, $parent_by_kind[n.kind] AS link
    MATCH (n)-[r1:IS_RELATED]-(rel:Relationship {name: link.identifier})-[r2:IS_RELATED]-(parent:Node)
    WHERE parent <> n
    AND all(r IN [r1, r2] WHERE %(branch_filter)s)
    AND (
        (link.direction = "outbound" AND startNode(r1) = n AND startNode(r2) = rel)
        OR (link.direction = "inbound" AND startNode(r1) = rel AND startNode(r2) = parent)
        OR (link.direction = "bidirectional" AND startNode(r1) = n AND startNode(r2) = parent)
    )
    WITH rel, parent, r1, r2
    ORDER BY r1.branch_level DESC, r1.from DESC, r1.status ASC, r2.branch_level DESC, r2.from DESC, r2.status ASC
    WITH rel, parent, head(collect([r1, r2])) AS latest
    WHERE latest[0].status = "active" AND latest[1].status = "active"
    RETURN min(parent.uuid) AS parent_id
}
CALL (n) {
    MATCH (n)-[attached:HAS_OWNER_SET|HAS_TARGET_OWNER_SET]->(s:OwnerSet)
    WHERE %(attached_filter)s
    WITH s, type(attached) AS set_type, attached
    ORDER BY attached.branch_level DESC, attached.from DESC, attached.status ASC
    WITH s, set_type, head(collect(attached)) AS latest_attached
    WHERE latest_attached.status = "active"
    MATCH (s)-[r:HAS_OWNER|HAS_NO_OWNER|HAS_OWNER_SOURCE]->(peer)
    WHERE %(branch_filter)s
    WITH s, set_type, peer, type(r) AS edge_type, r
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    WITH s, set_type, peer, edge_type, head(collect(r)) AS latest
    WHERE latest.status = "active"
    WITH s, set_type, collect([edge_type, peer.uuid]) AS held
    RETURN collect({
        set_type: set_type, attribute: s.attribute, identifier: s.identifier, direction: s.direction, held: held
    }) AS sets
}
CALL (n) {
    WITH n
    WHERE $with_attributes AND n.uuid IN $node_ids
    MATCH (n)-[r1:HAS_ATTRIBUTE]->(a:Attribute)-[r2:HAS_OWNER|HAS_NO_OWNER|HAS_OWNER_SOURCE]->(peer)
    WHERE all(r IN [r1, r2] WHERE %(branch_filter)s)
    WITH a, peer, type(r2) AS edge_type, r1, r2
    ORDER BY r1.branch_level DESC, r1.from DESC, r1.status ASC, r2.branch_level DESC, r2.from DESC, r2.status ASC
    WITH a, peer, edge_type, head(collect([r1, r2])) AS latest
    WHERE latest[0].status = "active" AND latest[1].status = "active"
    WITH a, collect([edge_type, peer.uuid]) AS held
    RETURN collect({set_type: NULL, attribute: a.name, identifier: NULL, direction: NULL, held: held}) AS attributes
}
CALL (n) {
    MATCH (n)-[r1:IS_RELATED]-(rel:Relationship {name: $profile_identifier})-[r2:IS_RELATED]-(profile:%(profile_label)s)
    WHERE all(r IN [r1, r2] WHERE %(branch_filter)s)
    WITH rel, profile, r1, r2
    ORDER BY r1.branch_level DESC, r1.from DESC, r1.status ASC, r2.branch_level DESC, r2.from DESC, r2.status ASC
    WITH rel, profile, head(collect([r1, r2])) AS latest
    WHERE latest[0].status = "active" AND latest[1].status = "active"
    CALL (profile) {
        OPTIONAL MATCH (profile)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: $priority_name})-[r2:HAS_VALUE]->(av)
        WHERE all(r IN [r1, r2] WHERE %(branch_filter)s)
        RETURN toInteger(av.value) AS priority
        ORDER BY r2.branch_level DESC, r2.from DESC, r2.status ASC
        LIMIT 1
    }
    RETURN collect(DISTINCT {profile_id: profile.uuid, priority: priority}) AS profiles
}
        """ % {
            "nodes_to_read": nodes_to_read,
            "branch_filter": branch_filter,
            "attached_filter": attached_filter,
            "profile_label": InfrahubKind.PROFILE,
        }
        self.add_to_query(query)
        self.return_labels = [
            "node_id",
            "n.kind AS kind",
            "held",
            "sets + attributes AS field_holders",
            "parent_id",
            "profiles",
        ]
        self.order_by = ["node_id"]

    def get_data(self) -> Generator[NodeOwnerStateReadQueryResult, None, None]:
        for result in self.get_results():
            yield NodeOwnerStateReadQueryResult(
                node_id=result.get_as_type("node_id", str),
                kind=result.get_as_type("kind", str),
                held=_edges(result.get_as_list_of_type("held", list)),
                field_holders=tuple(
                    (_holder_key(item), _edges(item["held"]))
                    for item in result.get_as_list_of_type("field_holders", HeldEdges)
                ),
                parent_id=result.get_as_optional_type("parent_id", str),
                profiles=tuple(
                    (profile["profile_id"], profile["priority"])
                    for profile in result.get_as_list_of_type("profiles", ProfilePriority)
                ),
            )


def _edges(held: list[list[str]]) -> tuple[tuple[str, str], ...]:
    return tuple((edge_type, peer_id) for edge_type, peer_id in held)


def owner_set_key_filter(vertex: str, key: str) -> str:
    """Return the Cypher condition that a set vertex has the key that the parameter `key` holds.

    The condition reads only the properties of the key, so that another property on the vertex does not hide the set.
    """
    return " AND ".join(
        f'coalesce({vertex}.{name}, "") = coalesce(${key}.{name}, "")'
        for name in ("attribute", "identifier", "direction")
    )


def _holder_key(item: HeldEdges) -> HolderKey:
    kinds = {None: HolderKind.ATTRIBUTE, "HAS_OWNER_SET": HolderKind.FIELD_SET}
    return HolderKey(
        kind=kinds.get(item["set_type"], HolderKind.TARGET_SET),
        attribute=item["attribute"],
        identifier=item["identifier"],
        direction=item["direction"],
    )


def _active_edge_query(edge_type: str, peer: str, inherited_filter: str) -> str:
    """Return the Cypher that makes the edge from the holder `h` to the vertex `peer` active on the write branch.

    Args:
        edge_type: The type of the edge.
        peer: The variable of the vertex that the edge ends at.
        inherited_filter: The condition that the edge `inherited` is one that the branch of the query reads.

    """
    return """CALL (h, %(peer)s) {
        OPTIONAL MATCH (h)-[hidden:%(edge_type)s {branch: $branch, status: "deleted"}]->(%(peer)s)
        WHERE hidden.to IS NULL AND EXISTS {
            MATCH (h)-[inherited:%(edge_type)s]->(%(peer)s)
            WHERE inherited.branch_level < $branch_level AND inherited.status = "active" AND %(inherited_filter)s
        }
        WITH collect(hidden) AS hidden_edges
        // A new edge next to the inherited edge goes to the default branch at a merge, also after that branch closed its edge
        FOREACH (edge IN hidden_edges | SET edge.to = $at, edge.to_user_id = $user_id)
        WITH hidden_edges
        WHERE size(hidden_edges) = 0
        CREATE (h)-[:%(edge_type)s {
            branch: $branch, branch_level: $branch_level, status: "active", from: $at, from_user_id: $user_id
        }]->(%(peer)s)
    }""" % {"edge_type": edge_type, "peer": peer, "inherited_filter": inherited_filter}


class OwnerStateWriteQuery(Query):
    """Replace the owner state that one holder of an active node stores.

    The edges are read with the branch of the query and written on the write branch, so that a node that all
    branches share keeps one owner state.
    """

    name = "ownership_owner_state_write"
    type = QueryType.WRITE
    raise_error_if_empty = True
    closed_edge_types = "HAS_OWNER|HAS_NO_OWNER|HAS_OWNER_SOURCE"
    listed_edge_type = "HAS_OWNER"
    """The type of the edges to the nodes of `owner_ids`."""

    edge_condition = ""
    """A Cypher condition on the edge `r` from the holder `h` of the node `n` to `peer`, to not close all edges."""

    def __init__(
        self,
        node_id: str,
        holder: HolderKey,
        owner_ids: list[str] | None,
        write_branch: Branch,
        template_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Set `owner_ids` to None for inherit, and to an empty list for "no owner".

        Args:
            template_id: The object template that the owners are a copy from. A write without it closes the mark.

        """
        self.node_id = node_id
        self.holder = holder
        self.owner_ids = owner_ids
        self.write_branch = write_branch
        self.template_id = template_id
        super().__init__(**kwargs)

    def _holders_query(self, branch_filter: str) -> str:
        """Return the Cypher that binds `h` to each holder of the node `n` that the query writes."""
        if self.holder == NODE_HOLDER:
            return "WITH n, n AS h"
        if self.holder.kind == HolderKind.ATTRIBUTE:
            self.params["attribute"] = self.holder.attribute
            return """
CALL (n) {
    MATCH (n)-[r:HAS_ATTRIBUTE]->(a:Attribute {name: $attribute})
    WHERE %(branch_filter)s
    WITH a, r
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    WITH a, head(collect(r)) AS latest
    WHERE latest.status = "active"
    RETURN a AS h
    LIMIT 1
}
CALL (h) {
    WITH h
    WHERE $branch_level = 1
    %(stamp)s
}
""" % {"branch_filter": branch_filter, "stamp": stamp_vertex_metadata(variable="h")}
        key = {
            "attribute": self.holder.attribute,
            "identifier": self.holder.identifier,
            "direction": self.holder.direction,
        }
        self.params["set_key"] = {name: value for name, value in key.items() if value is not None}
        # The set is looked for on all branches, so that the node keeps one set after the merges.
        return """
CALL (n) {
    OPTIONAL MATCH (n)-[:%(set_edge)s]->(s:OwnerSet)
    WHERE %(same_key)s
    RETURN s
    ORDER BY elementId(s)
    LIMIT 1
}
CALL (s) {
    WITH s
    WHERE s IS NULL AND $has_state
    CREATE (created:OwnerSet)
    SET created = $set_key
    RETURN created AS h
    UNION
    WITH s
    WHERE s IS NOT NULL OR NOT $has_state
    RETURN s AS h
}
CALL (n, h) {
    WITH n, h
    WHERE h IS NOT NULL AND $has_state
    OPTIONAL MATCH (n)-[r:%(set_edge)s]->(h)
    WHERE %(branch_filter)s
    WITH n, h, r
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
    WITH n, h, r
    WHERE r IS NULL OR r.status <> "active"
    CREATE (n)-[:%(set_edge)s {
        branch: $branch, branch_level: $branch_level, status: "active", from: $at, from_user_id: $user_id
    }]->(h)
}
""" % {
            "branch_filter": branch_filter,
            "set_edge": "HAS_OWNER_SET" if self.holder.kind == HolderKind.FIELD_SET else "HAS_TARGET_OWNER_SET",
            "same_key": owner_set_key_filter(vertex="s", key="set_key"),
        }

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at)
        self.params.update(branch_params)
        inherited_filter, _ = self.branch.get_query_filter_path(at=self.at, variable_name="inherited")
        self.params.update(
            {
                "node_id": self.node_id,
                "owner_ids": self.owner_ids or [],
                "no_owner": self.owner_ids == [],
                "has_state": self.owner_ids is not None,
                "template_id": self.template_id,
                "no_owner_uuid": NO_OWNER_VERTEX_UUID,
                "branch": self.write_branch.name,
                "branch_level": self.write_branch.hierarchy_level,
                "write_is_global": self.write_branch.is_global,
                "at": self.at.to_string(),
                "user_id": self.user_id,
                # An isolated branch reads its origin branch at the branch start, so a later delete there is hidden.
                "later_branches": sorted(
                    {
                        name
                        for names, time in self.branch.get_branches_and_times_to_query_global(at=self.at).items()
                        if time == self.at.to_string()
                        for name in names
                    }
                ),
            }
        )
        query = """
MATCH (n:Node {uuid: $node_id})
CALL (n) {
    // The lock lasts until the commit and comes before the check of the node, so the check reads a committed delete
    SET n.uuid = n.uuid
}
WITH n
MATCH (n)-[r:IS_PART_OF]->(:Root)
WHERE %(branch_filter)s
WITH n, r
ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
LIMIT 1
WITH n, r
WHERE r.status = "active"
AND NOT EXISTS {
    // A delete that commits while the write waits for the lock can have a later time than the write
    MATCH (n)-[later:IS_PART_OF {status: "deleted"}]->(:Root)
    WHERE later.branch IN $later_branches AND later.from > $at
}
WITH n
%(holders)s
CALL (n, h) {
    MATCH (h)-[r:%(edge_types)s]->(peer)
    WHERE %(branch_filter)s %(edge_condition)s
    WITH peer, type(r) AS edge_type, r
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    WITH peer, edge_type, head(collect(r)) AS latest
    WHERE latest.status = "active"
    RETURN collect({peer: peer, edge_type: edge_type, latest: latest}) AS current
}
CALL (h, current) {
    UNWIND current AS item
    WITH item.peer AS peer, item.edge_type AS edge_type, item.latest AS latest
    WHERE NOT (edge_type = "%(listed_edge)s" AND peer.uuid IN $owner_ids)
    AND NOT (edge_type = "HAS_NO_OWNER" AND $no_owner)
    CALL (latest) {
        WITH latest
        // A branch reads a global edge at its start, so the edge can be closed already
        WHERE latest.branch = $branch AND latest.to IS NULL
        SET latest.to = $at, latest.to_user_id = $user_id
    }
    CALL (h, peer, edge_type, latest) {
        WITH latest
        // A branch reads a global edge that was open at its start, also after the global branch closes it
        WHERE $write_is_global
        OR latest.branch_level < $branch_level
        OR EXISTS {
            MATCH (h)-[inherited:%(edge_types)s]->(peer)
            WHERE type(inherited) = edge_type AND inherited.branch_level < $branch_level
            AND inherited.status = "active" AND %(inherited_filter)s
        }
        CREATE (h)-[:$(edge_type) {
            branch: $branch, branch_level: $branch_level, status: "deleted", from: $at, from_user_id: $user_id
        }]->(peer)
    }
}
CALL (h, current) {
    UNWIND $owner_ids AS owner_id
    WITH owner_id
    WHERE NOT any(item IN current WHERE item.edge_type = "%(listed_edge)s" AND item.peer.uuid = owner_id)
    CALL (owner_id) {
        MATCH (owner:Node {uuid: owner_id})-[r:IS_PART_OF]->(:Root)
        WHERE %(branch_filter)s
        RETURN owner, r AS part_of
        ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
        LIMIT 1
    }
    WITH owner, part_of
    WHERE part_of.status = "active"
    %(owner_edge)s
}
CALL (h, current) {
    WITH h
    WHERE $no_owner AND NOT any(item IN current WHERE item.edge_type = "HAS_NO_OWNER")
    // the vertex exists before the first write, so this MERGE creates it only in a database that was built without it
    MERGE (no_owner:NoOwner {uuid: $no_owner_uuid})
    %(no_owner_edge)s
}
CALL (h) {
    MATCH (template:Node {uuid: $template_id})-[r:IS_PART_OF]->(:Root)
    WHERE %(branch_filter)s
    WITH template, r
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
    WITH template, r
    WHERE r.status = "active"
    CREATE (h)-[:HAS_OWNER_SOURCE {
        branch: $branch, branch_level: $branch_level, status: "active", from: $at, from_user_id: $user_id
    }]->(template)
}
        """ % {
            "branch_filter": branch_filter,
            "inherited_filter": inherited_filter,
            "holders": self._holders_query(branch_filter=branch_filter),
            "edge_types": self.closed_edge_types,
            "listed_edge": self.listed_edge_type,
            "edge_condition": self.edge_condition,
            "owner_edge": _active_edge_query(
                edge_type=self.listed_edge_type, peer="owner", inherited_filter=inherited_filter
            ),
            "no_owner_edge": _active_edge_query(
                edge_type="HAS_NO_OWNER", peer="no_owner", inherited_filter=inherited_filter
            ),
        }
        self.add_to_query(query)
        self.return_labels = ["n.uuid AS node_id"]


class NoOwnerVertexCreateQuery(Query):
    """Create the one vertex that every "no owner" edge ends at, when it does not exist."""

    name = "ownership_no_owner_vertex_create"
    type = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["no_owner_uuid"] = NO_OWNER_VERTEX_UUID
        self.add_to_query("MERGE (:NoOwner {uuid: $no_owner_uuid})")


class NodeOwnerEdgesCloseQuery(OwnerStateWriteQuery):
    """Close the owner edges of a node, of its attributes and of its sets of owners, and the edges to those sets.

    The query also closes the source edges of the node, and each mark of a copy from an object template that ends
    at the node. The copied owners stay. It changes nothing when the node is not active.
    """

    name = "ownership_node_owner_edges_close"
    raise_error_if_empty = False
    closed_edge_types = f"{OwnerStateWriteQuery.closed_edge_types}|HAS_OWNER_SET|HAS_TARGET_OWNER_SET|HAS_SOURCE"
    # The delete of an attribute closes the edge to the source of the attribute.
    edge_condition = """AND (type(r) <> "HAS_SOURCE" OR h:Node)
    AND (
        h = n
        OR EXISTS { (n)-[:HAS_OWNER_SET|HAS_TARGET_OWNER_SET|HAS_ATTRIBUTE]->(h) }
        OR (type(r) = "HAS_OWNER_SOURCE" AND peer = n)
    )"""

    def _holders_query(self, branch_filter: str) -> str:  # noqa: ARG002
        # Most nodes have no owner, so this check skips their holders; it comes after the lock to read committed edges.
        return """
WITH n
WHERE EXISTS { (n)-[:HAS_OWNER|HAS_NO_OWNER|HAS_OWNER_SOURCE|HAS_SOURCE|HAS_OWNER_SET|HAS_TARGET_OWNER_SET]->() }
OR EXISTS { (n)-[:HAS_ATTRIBUTE]->(:Attribute)-[:HAS_OWNER|HAS_NO_OWNER|HAS_OWNER_SOURCE]->() }
OR EXISTS { ()-[:HAS_OWNER_SOURCE]->(n) }
CALL (n) {
    RETURN n AS h
    UNION
    MATCH (n)-[:HAS_OWNER_SET|HAS_TARGET_OWNER_SET|HAS_ATTRIBUTE]->(h:OwnerSet|Attribute)
    RETURN h
    UNION
    MATCH (h)-[:HAS_OWNER_SOURCE]->(n)
    RETURN h
}
"""


class NodeLabelsReadQuery(Query):
    """Read the labels of each node that is active."""

    name = "ownership_node_labels_read"
    type = QueryType.READ

    def __init__(self, node_ids: list[str], **kwargs: Any) -> None:
        self.node_ids = node_ids
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at)
        self.params.update(branch_params)
        self.params["node_ids"] = self.node_ids
        query = """
UNWIND $node_ids AS node_id
CALL (node_id) {
    MATCH (n:Node {uuid: node_id})-[r:IS_PART_OF]->(:Root)
    WHERE %(branch_filter)s
    RETURN n, r AS part_of
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
WITH node_id, n, part_of
WHERE part_of.status = "active"
        """ % {"branch_filter": branch_filter}
        self.add_to_query(query)
        self.return_labels = ["node_id", "labels(n) AS node_labels"]
        self.order_by = ["node_id"]

    def get_labels(self) -> dict[str, set[str]]:
        return {
            result.get_as_type("node_id", str): set(result.get_as_list_of_type("node_labels", str))
            for result in self.get_results()
        }
