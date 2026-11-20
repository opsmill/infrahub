from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import GLOBAL_BRANCH_NAME, RelationshipStatus
from infrahub.core.ownership.queries import owner_set_key_filter
from infrahub.core.query import Query, QueryType
from infrahub.core.schema.generic_schema import GenericSchema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


def profile_and_template_kinds(
    db: InfrahubDatabase, branch: Branch, node_kind: str, attribute_name: str
) -> tuple[list[str], list[str]]:
    """Return the profile and template kinds of the kinds that get an attribute from a kind, and the kinds to skip.

    For a generic, these are the kind itself and each kind that inherits the attribute. The template of a kind that
    declares its own attribute with this name also has the label of the template of the generic, so it is a kind to
    skip.
    """
    kinds = [node_kind]
    kinds_to_skip = []
    schema = db.schema.get(name=node_kind, branch=branch, duplicate=False)
    if isinstance(schema, GenericSchema):
        for inheriting_kind in schema.used_by:
            attribute = db.schema.get_node_schema(
                name=inheriting_kind, branch=branch, duplicate=False
            ).get_attribute_or_none(name=attribute_name)
            if attribute is None or attribute.inherited:
                kinds.append(inheriting_kind)
            else:
                kinds_to_skip.append(f"Template{inheriting_kind}")
    return [f"{prefix}{kind}" for kind in kinds for prefix in ("Profile", "Template")], kinds_to_skip


class OwnerSetKeyMigrationQuery(Query):
    """Close the sets of owners of one field of the nodes of some kinds, and their edges.

    For a renamed attribute, the owners first go to the set with the new name. The key of a set is a vertex
    property, which all branches share, so the branch gets an edge to another set and the key of no set changes.

    An edge of another branch stays open and gets a `deleted` edge on the branch of the migration. So a branch with
    the schema before the change still reads the owners that a node of the global branch gives to the field.
    On the default branch, the new set of such a node gets its edges on the global branch.
    """

    name = "migration_owner_set_key"
    type: QueryType = QueryType.WRITE
    insert_return: bool = False

    def __init__(
        self,
        node_kinds: list[str],
        set_key: dict[str, str],
        new_set_key: dict[str, str] | None = None,
        kinds_to_skip: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Give in `set_key` the properties of the sets to close.

        Args:
            node_kinds: The kinds of the nodes that hold the sets.
            set_key: The `attribute`, or the `identifier` and the `direction`, of the field.
            new_set_key: The properties of the set that gets the owners, for a renamed field.
            kinds_to_skip: The kinds whose nodes keep their sets.

        """
        self.node_kinds = node_kinds
        self.set_key = set_key
        self.new_set_key = new_set_key
        self.kinds_to_skip = kinds_to_skip or []
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at)
        inherited_filter, _ = self.branch.get_query_filter_path(at=self.at, variable_name="inherited")
        self.params.update(branch_params)
        edge_properties = {
            "branch": self.branch.name,
            "branch_level": self.branch.hierarchy_level,
            "from": self.at.to_string(),
            "from_user_id": self.user_id,
        }
        self.params.update(
            {
                "set_key": self.set_key,
                "new_set_key": self.new_set_key,
                "kinds_to_skip": self.kinds_to_skip,
                "branch": self.branch.name,
                # On the default branch, a write of owners can only replace the edges of the global branch.
                "kept_edge_branch": GLOBAL_BRANCH_NAME if self.branch.is_default else None,
                "at": self.at.to_string(),
                "user_id": self.user_id,
                "active_edge": edge_properties | {"status": RelationshipStatus.ACTIVE.value},
                "deleted_edge": edge_properties | {"status": RelationshipStatus.DELETED.value},
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
MATCH (n:%(node_kinds)s)-[:HAS_OWNER_SET|HAS_TARGET_OWNER_SET]->(s:OwnerSet)
WHERE %(same_key)s
AND none(label IN labels(n) WHERE label IN $kinds_to_skip)
WITH DISTINCT n, s
CALL (n) {
    // The write lock lasts until the commit, so the reads below see a committed delete and no other write creates the set
    WITH n
    WHERE $new_set_key IS NOT NULL
    SET n.uuid = n.uuid
}
// ------------
// A rename gives no set to a node that is not active after the lock
// ------------
CALL (n) {
    OPTIONAL MATCH (n)-[r:IS_PART_OF]->(:Root)
    WHERE %(branch_filter)s
    WITH n, r
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
    RETURN r.status = "active" AND NOT EXISTS {
        // A delete that commits while the query waits for the lock can have a later time than the query
        MATCH (n)-[later:IS_PART_OF {status: "deleted"}]->(:Root)
        WHERE later.branch IN $later_branches AND later.from > $at
    } AS is_active
}
WITH n, s, is_active
WHERE $new_set_key IS NULL OR is_active
CALL (n, s) {
    MATCH (n)-[r:HAS_OWNER_SET|HAS_TARGET_OWNER_SET]->(s)
    WHERE %(branch_filter)s
    RETURN r AS attached
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
WITH n, s, attached
WHERE attached.status = "active"
CALL (s) {
    MATCH (s)-[r:HAS_OWNER|HAS_NO_OWNER|HAS_OWNER_SOURCE]->(peer)
    WHERE %(branch_filter)s
    WITH peer, type(r) AS edge_type, r
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    WITH peer, edge_type, head(collect(r)) AS latest
    WHERE latest.status = "active"
    RETURN collect(latest) AS held
}
// ------------
// Give the owners to the set with the new key, which is looked for on all branches and on each vertex of the UUID
// as a write of owners does
// ------------
CALL (n, attached, held) {
    WITH n, attached, held
    WHERE $new_set_key IS NOT NULL
    CALL (n, attached) {
        OPTIONAL MATCH (:Node {uuid: n.uuid})-[e:HAS_OWNER_SET|HAS_TARGET_OWNER_SET]->(existing:OwnerSet)
        WHERE type(e) = type(attached) AND %(same_new_key)s
        RETURN existing
        ORDER BY elementId(existing)
        LIMIT 1
    }
    CALL (existing) {
        WITH existing
        WHERE existing IS NULL
        CREATE (created:OwnerSet)
        SET created = $new_set_key
        RETURN created AS new_set
        UNION
        WITH existing
        WHERE existing IS NOT NULL
        RETURN existing AS new_set
    }
    CREATE (n)-[new_attached:$(type(attached)) $active_edge]->(new_set)
    SET new_attached.branch = CASE attached.branch WHEN $kept_edge_branch THEN attached.branch ELSE $branch END
    WITH new_set, held
    UNWIND held AS edge
    WITH new_set, edge, endNode(edge) AS peer
    CREATE (new_set)-[new_edge:$(type(edge)) $active_edge]->(peer)
    SET new_edge.branch = CASE edge.branch WHEN $kept_edge_branch THEN edge.branch ELSE $branch END
}
// ------------
// Close the set: an edge of this branch ends, and an edge of another branch gets a deleted edge on this branch,
// because a branch with the schema before the change still reads an edge of the global branch
// ------------
WITH s, [attached] + held AS closed
UNWIND closed AS edge
CALL (edge) {
    WITH edge
    WHERE edge.branch = $branch
    SET edge.to = $at, edge.to_user_id = $user_id
}
CALL (edge) {
    WITH edge, startNode(edge) AS holder, endNode(edge) AS peer
    WHERE edge.branch <> $branch
    OR EXISTS {
        MATCH (holder)-[inherited:HAS_OWNER|HAS_NO_OWNER|HAS_OWNER_SOURCE|HAS_OWNER_SET|HAS_TARGET_OWNER_SET]->(peer)
        WHERE type(inherited) = type(edge) AND inherited.branch <> $branch
        AND inherited.status = "active" AND %(inherited_filter)s
    }
    CREATE (holder)-[:$(type(edge)) $deleted_edge]->(peer)
}
RETURN DISTINCT elementId(s) AS owner_set
        """ % {
            "node_kinds": "|".join(self.node_kinds),
            "branch_filter": branch_filter,
            "inherited_filter": inherited_filter,
            "same_key": owner_set_key_filter(vertex="s", key="set_key"),
            "same_new_key": owner_set_key_filter(vertex="existing", key="new_set_key"),
        }
        self.add_to_query(query)
