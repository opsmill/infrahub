from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import PROFILE_NODE_RELATIONSHIP_IDENTIFIER, InfrahubKind
from infrahub.core.schema import GenericSchema

from .constants import MAX_INHERITANCE_DEPTH, OWNERS_IDS_FILTER, OWNERS_ISNULL_FILTER, PROFILE_PRIORITY_ATTRIBUTE
from .queries import ActiveEdgeFilter, parent_relationships_by_kind

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.timestamp import Timestamp

OWNER_FILTERS = (OWNERS_IDS_FILTER, OWNERS_ISNULL_FILTER)
_PARAMS_PREFIX = "owner_filter_"


def has_owner_filter(filters: dict[str, Any] | None) -> bool:
    return filters is not None and any(filters.get(name) is not None for name in OWNER_FILTERS)


class OwnerFilter(ActiveEdgeFilter):
    """Build the Cypher of the owner filters of a list of nodes of one kind.

    The Cypher starts from the owners and goes down to the nodes that inherit, so its cost follows the number of nodes
    that have an owner, not the number of nodes of the kind. It gives each node the answer of the read of the owners
    that apply: the same parent for each kind, the same depth limit, the same order of profiles, and a deleted owner
    does not count.
    """

    params_prefix = _PARAMS_PREFIX

    def __init__(self, branch: Branch, at: Timestamp, schema_branch: SchemaBranch, kind: str) -> None:
        super().__init__(branch=branch, at=at)
        self.schema_branch = schema_branch
        self.kind = kind
        self.parents = parent_relationships_by_kind(schema_branch=schema_branch)

    def render(self, filters: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Return the Cypher that binds `n` one time to each node that the filters match, and its parameters.

        The Cypher checks that the owners and the edges are active. It does not check that `n` is active.
        """
        owner_ids: list[str] | None = filters.get(OWNERS_IDS_FILTER)
        without_owner: bool = filters.get(OWNERS_ISNULL_FILTER) is True
        if without_owner and owner_ids is not None:
            # No node has both an owner of the list and no owner.
            owner_ids = []

        kinds = self._inheriting_kinds()
        _, params = self.branch.get_query_filter_path(at=self.at, params_prefix=_PARAMS_PREFIX)
        params |= {
            f"{_PARAMS_PREFIX}parents": self.parents,
            f"{_PARAMS_PREFIX}kinds": kinds,
            f"{_PARAMS_PREFIX}identifiers": sorted({self.parents[kind]["identifier"] for kind in kinds}),
            f"{_PARAMS_PREFIX}profile_identifier": PROFILE_NODE_RELATIONSHIP_IDENTIFIER,
            f"{_PARAMS_PREFIX}priority_name": PROFILE_PRIORITY_ATTRIBUTE,
        }
        if owner_ids is not None:
            params[f"{_PARAMS_PREFIX}ids"] = owner_ids

        query = self._nodes_with_owners(filter_owners=owner_ids is not None)
        if without_owner and owner_ids is None:
            query += f"""
WITH collect(DISTINCT n) AS {_PARAMS_PREFIX}owned
MATCH (n:{self.kind})
WHERE NOT n IN {_PARAMS_PREFIX}owned
WITH n
"""
        else:
            query += "WITH DISTINCT n\n"
        return query, params

    def _inheriting_kinds(self) -> list[str]:
        """Return the kinds that inherit on the way from an owner down to the kind of the list."""
        visited: set[str] = set()
        to_visit = [self.kind]
        while to_visit:
            name = to_visit.pop()
            if name in visited:
                continue
            visited.add(name)
            schema = self.schema_branch.get(name=name, duplicate=False)
            if isinstance(schema, GenericSchema):
                to_visit.extend(schema.used_by)
            elif name in self.parents:
                to_visit.append(self.parents[name]["peer"])
        return sorted(name for name in visited if name in self.parents)

    def _nodes_with_owners(self, filter_owners: bool) -> str:
        """Return the Cypher that walks down to the nodes of the kind, from each node that takes live owners.

        A node takes owners from its own state, else from the first of its profiles that gives owners, else from
        its copy of the owners of an object template.
        """
        prefix = _PARAMS_PREFIX
        # Without the hint, the planner can read the owner edges of all owners to find the edges of a few owners.
        owners = f"USING INDEX owner:Node(uuid)\nWHERE owner.uuid IN ${prefix}ids AND" if filter_owners else "WHERE"
        latest = ""
        if self.ranks_edges:
            latest = """
    ORDER BY held.branch_level DESC, held.from DESC, held.status ASC
    WITH owner, h, head(collect(held)) AS held"""
        alive = f"""EXISTS {{
        MATCH (owner)-[alive:IS_PART_OF]->(root:Root)
        WHERE {self._active("alive", "(owner)-[%s:IS_PART_OF]->(root)")}
    }}"""
        return f"""
CALL () {{
    MATCH (owner:Node)<-[held:HAS_OWNER]-(h:Node)
    {owners} {self._branch_filter("held")}
    WITH owner, h, held{latest}
    WHERE held.status = "active" AND {alive}
    AND NOT ({self._is_template_copy(node="h")} AND EXISTS {{
        {self._giving_profiles(node="h")}
    }})
    RETURN h
    UNION
    MATCH (owner:Node)<-[held:HAS_OWNER]-(s:OwnerSet)<-[gives:HAS_TARGET_OWNER_SET]-(profile:{InfrahubKind.PROFILE})
    {owners} s.attribute IS NULL AND s.identifier IS NULL
    AND {self._active("held", "(s)-[%s:HAS_OWNER]->(owner)")}
    AND {self._active("gives", "(profile)-[%s:HAS_TARGET_OWNER_SET]->(s)")}
    AND {alive}
    WITH DISTINCT profile
    MATCH (profile)-[u2:IS_RELATED]-(ul:Relationship {{name: ${prefix}profile_identifier}})-[u1:IS_RELATED]-(h:Node)
    WHERE {self._active("u1", "(h)-[%s:IS_RELATED]-(ul)")}
    AND {self._active("u2", "(ul)-[%s:IS_RELATED]-(profile)")}
    AND NOT ({self._holds_owner_edges(node="h")} AND NOT {self._is_template_copy(node="h")})
    WITH h, collect(DISTINCT profile) AS profiles
    CALL (h) {{
        {self._giving_profiles(node="h")}
        CALL (gp) {{
            OPTIONAL MATCH (gp)-[pa:HAS_ATTRIBUTE]->(:Attribute {{name: ${prefix}priority_name}})-[pv:HAS_VALUE]->(av)
            WHERE {self._branch_filter("pa")} AND {self._branch_filter("pv")}
            RETURN toInteger(av.value) AS priority
            ORDER BY pv.branch_level DESC, pv.from DESC, pv.status ASC
            LIMIT 1
        }}
        RETURN gp AS first_profile
        ORDER BY priority IS NULL, priority, gp.uuid
        LIMIT 1
    }}
    WITH h, profiles, first_profile
    WHERE first_profile IN profiles
    RETURN h
}}
MATCH (h) (
    (p:Node)-[r2:IS_RELATED]-(rl:Relationship)-[r1:IS_RELATED]-(c:Node)
    WHERE rl.name IN ${prefix}identifiers AND c.kind IN ${prefix}kinds
    AND rl.name = ${prefix}parents[c.kind].identifier AND c <> p
    AND {self._active("r1", "(c)-[%s:IS_RELATED]-(rl)")}
    AND {self._active("r2", "(rl)-[%s:IS_RELATED]-(p)")}
    AND (
        (${prefix}parents[c.kind].direction = "bidirectional" AND startNode(r1) = c AND startNode(r2) = p)
        OR (${prefix}parents[c.kind].direction = "outbound" AND startNode(r1) = c AND startNode(r2) = rl)
        OR (${prefix}parents[c.kind].direction = "inbound" AND startNode(r1) = rl AND startNode(r2) = p)
    )
    AND NOT {self._holds_owner_edges(node="c")}
    AND NOT EXISTS {{
        {self._giving_profiles(node="c")}
    }}
){{0,{MAX_INHERITANCE_DEPTH}}} (n:{self.kind})
"""

    def _giving_profiles(self, node: str) -> str:
        """Return the Cypher that binds `gp` to each profile of a node that gives owners or "no owner" to its nodes."""
        return f"""MATCH ({node})-[g1:IS_RELATED]-(gl:Relationship {{name: ${_PARAMS_PREFIX}profile_identifier}})
            -[g2:IS_RELATED]-(gp:{InfrahubKind.PROFILE})-[g3:HAS_TARGET_OWNER_SET]->(gs:OwnerSet)
            -[g4:HAS_OWNER]->(g_peer)
        WHERE gs.attribute IS NULL AND gs.identifier IS NULL
        AND {self._active("g1", f"({node})-[%s:IS_RELATED]-(gl)")}
        AND {self._active("g2", "(gl)-[%s:IS_RELATED]-(gp)")}
        AND {self._active("g3", "(gp)-[%s:HAS_TARGET_OWNER_SET]->(gs)")}
        AND {self._active("g4", "(gs)-[%s:HAS_OWNER]->(g_peer)")}"""
