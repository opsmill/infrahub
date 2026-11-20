from __future__ import annotations

from collections.abc import Sequence  # noqa: TC003  needed for pydantic
from typing import TYPE_CHECKING, Any

from infrahub.types import is_large_attribute_type

from ..query import AttributeMigrationQuery, MigrationBaseQuery
from ..query.selection import MigrationSelectionQuery
from ..shared import AttributeSchemaMigration, MigrationInput, MigrationResult

if TYPE_CHECKING:
    from infrahub.core.branch.models import Branch
    from infrahub.database import InfrahubDatabase


TOWARD_INDEXED_QUERY = """
%(selection)s

// ------------
// group the attributes by value so that each value is looked up and created once
// ------------
WITH av.is_default AS av_is_default, av.value AS av_value,
    collect({n: n, attr: attr, has_value_e: has_value_e, av: av}) AS updates
CALL (av_is_default, av_value) {
    OPTIONAL MATCH (existing_av:AttributeValue:AttributeValueIndexed {is_default: av_is_default, value: av_value})
    RETURN existing_av
    LIMIT 1
}
CALL (av_is_default, av_value, existing_av) {
    WITH av_is_default, av_value, existing_av
    WHERE existing_av IS NULL
    CREATE (created_av:AttributeValue:AttributeValueIndexed {is_default: av_is_default, value: av_value})
    RETURN collect(created_av) AS created_avs
}
WITH updates, coalesce(existing_av, head(created_avs)) AS new_av
UNWIND updates AS update
WITH update.n AS n, update.attr AS attr, update.has_value_e AS has_value_e, update.av AS av, new_av

%(edge_updates)s
"""

TOWARD_LARGE_QUERY = """
// ------------
// the values in play come from their own pass over the selection so that only the grouping holds the attributes in memory
// ------------
CALL () {
    %(selection)s
    RETURN collect(DISTINCT av.value) AS values_in_play
}

// ------------
// only AttributeValueIndexed has an index on value, so the other value vertices are scanned once for the values in play
// and joined to the attributes by grouping on the value
// ------------
CALL (values_in_play) {
    %(selection)s
    RETURN av.is_default AS av_is_default, av.value AS av_value,
        {n: n, attr: attr, has_value_e: has_value_e, av: av} AS update, NULL AS existing_av
    UNION ALL
    WITH values_in_play
    WHERE size(values_in_play) > 0
    MATCH (existing_av:AttributeValue)
    WHERE NOT existing_av:AttributeValueIndexed AND existing_av.value IN values_in_play
    RETURN existing_av.is_default AS av_is_default, existing_av.value AS av_value,
        NULL AS update, existing_av
}
WITH av_is_default, av_value, collect(update) AS updates, head(collect(existing_av)) AS existing_av
WHERE size(updates) > 0
CALL (av_is_default, av_value, existing_av) {
    WITH av_is_default, av_value, existing_av
    WHERE existing_av IS NULL
    CREATE (created_av:AttributeValue {is_default: av_is_default, value: av_value})
    RETURN collect(created_av) AS created_avs
}
WITH updates, coalesce(existing_av, head(created_avs)) AS new_av
UNWIND updates AS update
WITH update.n AS n, update.attr AS attr, update.has_value_e AS has_value_e, update.av AS av, new_av

%(edge_updates)s
"""

EDGE_UPDATES_QUERY = """
// ------------
// create and update the HAS_VALUE edges
// ------------
CALL (attr, has_value_e, av, new_av) {
    // ------------
    // create the new HAS_VALUE edge
    // ------------
    CREATE (attr)-[new_has_value_e:HAS_VALUE]->(new_av)
    SET new_has_value_e = properties(has_value_e)
    SET new_has_value_e.status = "active"
    SET new_has_value_e.branch = $branch
    SET new_has_value_e.branch_level = $branch_level
    SET new_has_value_e.from = $at
    SET new_has_value_e.from_user_id = $user_id
    SET new_has_value_e.to = NULL

    // ------------
    // if we are updating on a branch and the existing edge is on the default branch,
    // then create a new deleted edge on this branch
    // ------------
    WITH attr, has_value_e, av
    WHERE has_value_e.branch <> $branch
    CREATE (attr)-[deleted_has_value_e:HAS_VALUE]->(av)
    SET deleted_has_value_e = properties(has_value_e)
    SET deleted_has_value_e.status = "deleted"
    SET deleted_has_value_e.branch = $branch
    SET deleted_has_value_e.branch_level = $branch_level
    SET deleted_has_value_e.from = $at
    SET deleted_has_value_e.from_user_id = $user_id
    SET deleted_has_value_e.to = NULL
}

// ------------
// if the existing edge is on the same branch as the update,
// then set its "to" time
// ------------
CALL (has_value_e) {
    WITH has_value_e
    WHERE has_value_e.branch = $branch
    SET has_value_e.to = $at, has_value_e.to_user_id = $user_id
}

// ------------
// Set metadata on Attribute and Node vertices if on default/global branch
// ------------
CALL (attr, n) {
    WITH attr, n
    WHERE $set_metadata
    SET attr.previous_updated_at = CASE WHEN attr.updated_at IS NULL OR attr.updated_at <> $at THEN attr.updated_at ELSE attr.previous_updated_at END,
        attr.previous_updated_by = CASE WHEN attr.updated_at IS NULL OR attr.updated_at <> $at THEN attr.updated_by ELSE attr.previous_updated_by END
    SET attr.updated_at = $at, attr.updated_by = $user_id
    SET n.previous_updated_at = CASE WHEN n.updated_at IS NULL OR n.updated_at <> $at THEN n.updated_at ELSE n.previous_updated_at END,
        n.previous_updated_by = CASE WHEN n.updated_at IS NULL OR n.updated_at <> $at THEN n.updated_by ELSE n.previous_updated_by END
    SET n.updated_at = $at, n.updated_by = $user_id
}
"""


class AttributeKindUpdateMigrationQuery(AttributeMigrationQuery, MigrationSelectionQuery):
    name = "migration_attribute_kind"
    insert_return = False
    selected_node = "n"

    def render_selection(self) -> str:
        branch_filter, _ = self.branch.get_query_filter_path(at=self.at)
        kind = self.migration.previous_schema.kind
        schema_kinds = [kind, f"Profile{kind}", f"Template{kind}"]
        # The index hint of the node scope applies only to a MATCH that holds the node alone.
        node_match = self.render_node_match("n", schema_kinds)
        node_attribute_match = f"{node_match}\nMATCH (n)-[:HAS_ATTRIBUTE]->(attr:Attribute)"
        return """
%(node_attribute_match)s
WHERE attr.name = $attr_name
WITH DISTINCT n, attr

// ------------
// a branch-agnostic attribute's global edges are visible from nodes that do not exist on this branch
// ------------
CALL (n) {
    MATCH (:Root)<-[r:IS_PART_OF]-(n)
    WHERE %(branch_filter)s
    RETURN r
    ORDER BY r.branch_level DESC, r.from DESC
    LIMIT 1
}
WITH n, attr
WHERE r.status = "active"

// ------------
// for each Attribute, find the most recent active edge and AttributeValue vertex that needs to be [un]indexed
// ------------
CALL (n, attr) {
    MATCH (n)-[r1:HAS_ATTRIBUTE]->(attr:Attribute)-[r2:HAS_VALUE]->(av)
    WHERE all(r IN [r1, r2] WHERE %(branch_filter)s)
    WITH r2, av, r1.status = "active" AND r2.status = "active" AS is_active
    ORDER BY r2.branch_level DESC, r2.from DESC, r2.status = "active" DESC, r1.branch_level DESC, r1.from DESC, r1.status = "active" DESC
    LIMIT 1
    WITH r2 AS has_value_e, av, "AttributeValueIndexed" IN labels(av) AS is_indexed
    WHERE is_active AND is_indexed <> $needs_index
    RETURN has_value_e, av
}
""" % {"node_attribute_match": node_attribute_match, "branch_filter": branch_filter}

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        _, branch_params = self.branch.get_query_filter_path(at=self.at)
        self.params.update(branch_params)
        needs_index = not is_large_attribute_type(self.migration.new_attribute_schema.kind)
        self.params["needs_index"] = needs_index
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["at"] = self.at.to_string()
        self.params["attr_name"] = self.migration.previous_attribute_schema.name
        self.params["user_id"] = self.user_id

        # Set metadata for vertex properties on default/global branch
        self.params["set_metadata"] = self.branch.is_default or self.branch.is_global

        template = TOWARD_INDEXED_QUERY if needs_index else TOWARD_LARGE_QUERY
        self.add_to_query(template % {"selection": self.render_selection(), "edge_updates": EDGE_UPDATES_QUERY})


class AttributeKindUpdateMigration(AttributeSchemaMigration):
    name: str = "attribute.kind.update"
    queries: Sequence[type[AttributeMigrationQuery]] = [AttributeKindUpdateMigrationQuery]

    async def execute(
        self,
        migration_input: MigrationInput,
        branch: Branch,
        queries: Sequence[type[MigrationBaseQuery]] | None = None,
    ) -> MigrationResult:
        is_indexed_previous = is_large_attribute_type(self.previous_attribute_schema.kind)
        is_indexed_new = is_large_attribute_type(self.new_attribute_schema.kind)
        if is_indexed_previous is is_indexed_new:
            return MigrationResult()

        return await super().execute(migration_input=migration_input, branch=branch, queries=queries)
