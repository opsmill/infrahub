from __future__ import annotations

from collections.abc import Sequence  # noqa: TC003  needed for pydantic
from typing import TYPE_CHECKING, Any, ClassVar

from infrahub.core.graph.schema import get_attribute_value_key
from infrahub.core.migrations.schema.phases import MigrationPhase
from infrahub.core.query import Query, QueryType
from infrahub.core.query.vertex_metadata import stamp_vertex_metadata
from infrahub.types import is_large_attribute_type

from ..query import AttributeMigrationQuery, MigrationBaseQuery
from ..shared import AttributeSchemaMigration, MigrationInput, MigrationResult

if TYPE_CHECKING:
    from infrahub.core.branch.models import Branch
    from infrahub.database import InfrahubDatabase

# The string a stored value is looked up by in the map of keys, built the same way on both sides of the query.
VALUE_LOOKUP = "CASE WHEN %(value)s IS :: STRING THEN %(value)s ELSE toString(%(value)s) END"


class IndexedAttributeValuesQuery(Query):
    """Read the distinct indexed values an attribute of the given kinds has on any branch or at any time."""

    name = "migration_attribute_kind_indexed_values"
    type = QueryType.READ

    def __init__(self, node_kinds: list[str], attribute_name: str, **kwargs: Any) -> None:
        self.node_kinds = node_kinds
        self.attribute_name = attribute_name
        # A stable order keeps the pages of the read from skipping or repeating a value.
        super().__init__(order_by=["lookup"], **kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["attr_name"] = self.attribute_name
        query = """
        MATCH (:%(node_kinds)s)-[:HAS_ATTRIBUTE]->(:Attribute {name: $attr_name})-[:HAS_VALUE]->(av:AttributeValueIndexed)
        WITH DISTINCT av.value AS value
        WITH value, %(lookup)s AS lookup
        """ % {"node_kinds": "|".join(self.node_kinds), "lookup": VALUE_LOOKUP % {"value": "value"}}
        self.add_to_query(query)
        self.return_labels = ["value", "lookup"]

    def get_value_keys(self) -> dict[str, str]:
        return {
            result.get_as_type("lookup", return_type=str): get_attribute_value_key(result.get("value"))
            for result in self.get_results()
        }


def _get_node_kinds(kind: str) -> list[str]:
    return [kind, f"Profile{kind}", f"Template{kind}"]


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
%(selection)s

// ------------
// group the attributes by value so that each value is looked up and created once
// ------------
WITH av.is_default AS av_is_default, av.value AS av_value,
    collect({n: n, attr: attr, has_value_e: has_value_e, av: av}) AS updates

// ------------
// indexed values never carry a key, so merging on the key cannot reuse one of them,
// and LIMIT 1 links each attribute to one value when concurrent writes left equal values
// ------------
CALL (av_is_default, av_value) {
    MERGE (new_av:AttributeValue {
        is_default: av_is_default, value: av_value, value_key: $value_keys[%(lookup)s]
    })
    RETURN new_av
    LIMIT 1
}
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
    %(stamp_attr)s
    %(stamp_n)s
}
"""


class AttributeKindUpdateMigrationQuery(AttributeMigrationQuery):
    """Link each attribute whose kind changed to a value stored the way its new kind stores values.

    `value_keys` maps each value converted to a large kind, as a string, to its key, and is empty otherwise.
    """

    name = "migration_attribute_kind"
    insert_return = False
    selected_node = "n"

    def __init__(self, value_keys: dict[str, str], **kwargs: Any) -> None:
        self.value_keys = value_keys
        super().__init__(**kwargs)

    def render_selection(self) -> str:
        branch_filter, _ = self.branch.get_query_filter_path(at=self.at)
        # The kind rename runs in an earlier phase, so the nodes already carry the new kind
        schema_kinds = _get_node_kinds(self.migration.new_schema.kind)
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
        # The attribute rename runs in an earlier phase, so the attribute already carries its new name
        self.params["attr_name"] = self.migration.new_attribute_schema.name
        self.params["user_id"] = self.user_id

        # Set metadata for vertex properties on default/global branch
        self.params["set_metadata"] = self.branch.is_default or self.branch.is_global

        if needs_index:
            template = TOWARD_INDEXED_QUERY
        else:
            template = TOWARD_LARGE_QUERY
            self.params["value_keys"] = self.value_keys
        stamp_attr, stamp_params = stamp_vertex_metadata("attr", at=self.at, operation_ats=self.operation_ats)
        self.params.update(stamp_params)
        stamp_n, stamp_params = stamp_vertex_metadata("n", at=self.at, operation_ats=self.operation_ats)
        self.params.update(stamp_params)
        edge_updates = EDGE_UPDATES_QUERY % {
            "stamp_attr": stamp_attr,
            "stamp_n": stamp_n,
        }
        self.add_to_query(
            template
            % {
                "selection": self.render_selection(),
                "edge_updates": edge_updates,
                "lookup": VALUE_LOOKUP % {"value": "av_value"},
            }
        )


class AttributeKindUpdateMigration(AttributeSchemaMigration):
    phase: ClassVar[MigrationPhase] = MigrationPhase.ATTRIBUTE_KIND_UPDATE
    name: str = "attribute.kind.update"
    queries: Sequence[type[AttributeMigrationQuery]] = [AttributeKindUpdateMigrationQuery]

    async def build_query(
        self,
        migration_query: type[MigrationBaseQuery],
        migration_input: MigrationInput,
        branch: Branch,
    ) -> MigrationBaseQuery:
        if not issubclass(migration_query, AttributeKindUpdateMigrationQuery):
            return await super().build_query(
                migration_query=migration_query, migration_input=migration_input, branch=branch
            )

        value_keys: dict[str, str] = {}
        if is_large_attribute_type(self.new_attribute_schema.kind):
            # Cypher cannot compute the hash, so the keys of the values to convert are computed before the query.
            values_query = await IndexedAttributeValuesQuery.init(
                db=migration_input.db,
                branch=branch,
                node_kinds=_get_node_kinds(self.new_schema.kind),
                attribute_name=self.new_attribute_schema.name,
            )
            await values_query.execute(db=migration_input.db)
            value_keys = values_query.get_value_keys()

        return await migration_query.init(
            db=migration_input.db,
            branch=branch,
            at=migration_input.at,
            migration=self,
            user_id=migration_input.user_id,
            operation_ats=migration_input.operation_ats,
            node_ids=migration_input.node_ids,
            value_keys=value_keys,
        )

    async def execute(
        self,
        migration_input: MigrationInput,
        branch: Branch,
        queries: Sequence[type[MigrationBaseQuery]] | None = None,
    ) -> MigrationResult:
        previous_attribute_schema = self.previous_version_of_new_attribute_schema
        if previous_attribute_schema is None:
            raise ValueError(f"Unable to find the previous version of the attribute {self.new_attribute_schema.name}")
        is_indexed_previous = is_large_attribute_type(previous_attribute_schema.kind)
        is_indexed_new = is_large_attribute_type(self.new_attribute_schema.kind)
        if is_indexed_previous is is_indexed_new:
            return MigrationResult()

        return await super().execute(migration_input=migration_input, branch=branch, queries=queries)
