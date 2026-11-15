from __future__ import annotations

from collections.abc import Sequence  # noqa: TC003  needed for pydantic
from typing import TYPE_CHECKING, Any

from infrahub.core.graph.schema import get_attribute_value_key
from infrahub.core.query import Query, QueryType
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


class AttributeKindUpdateMigrationQuery(AttributeMigrationQuery):
    name = "migration_attribute_kind"
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at)
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

        if needs_index:
            create_value_query = """
    OPTIONAL MATCH (existing_av:AttributeValue {is_default: av_is_default, value: av_value})
    WHERE "AttributeValueIndexed" IN labels(existing_av) = $needs_index
    WITH existing_av WHERE existing_av IS NULL
    LIMIT 1
    CREATE (:AttributeValue:AttributeValueIndexed {is_default: av_is_default, value: av_value})"""
            get_value_query = """
    MATCH (new_av:AttributeValue:AttributeValueIndexed {is_default: av.is_default, value: av.value})
    WHERE "AttributeValueIndexed" IN labels(new_av) = $needs_index
    LIMIT 1"""
        else:
            # Cypher cannot compute the hash, so the keys of the values to convert are computed here.
            values_query = await IndexedAttributeValuesQuery.init(
                db=db, branch=self.branch, node_kinds=self._node_kinds(), attribute_name=self.params["attr_name"]
            )
            await values_query.execute(db=db)
            self.params["value_keys"] = values_query.get_value_keys()
            # Indexed values never carry a key, so merging on the key cannot reuse one of them.
            create_value_query = """
    MERGE (:AttributeValue {
        is_default: av_is_default, value: av_value, value_key: $value_keys[%(lookup)s]
    })""" % {"lookup": VALUE_LOOKUP % {"value": "av_value"}}
            get_value_query = """
    MERGE (new_av:AttributeValue {
        is_default: av.is_default, value: av.value, value_key: $value_keys[%(lookup)s]
    })""" % {"lookup": VALUE_LOOKUP % {"value": "av.value"}}
        # ruff: noqa: S608
        query = """
// ------------
// start with all the Attribute vertices we might care about
// ------------
MATCH (n:%(schema_kinds)s)-[:HAS_ATTRIBUTE]->(attr:Attribute)
WHERE attr.name = $attr_name
WITH DISTINCT n, attr

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

// ------------
// check if the correct AttributeValue vertex to use exists
// create it if not
// ------------
WITH DISTINCT av.is_default AS av_is_default, av.value AS av_value
CALL (av_is_default, av_value) {%(create_value_query)s
}

// ------------
// get all the AttributeValue vertices that need to be updated again and run the updates
// ------------
WITH 1 AS one
LIMIT 1
MATCH (n:%(schema_kinds)s)-[:HAS_ATTRIBUTE]->(attr:Attribute)
WHERE attr.name = $attr_name
WITH DISTINCT n, attr

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

// ------------
// create and update the HAS_VALUE edges
// ------------
CALL (attr, has_value_e, av) {
    // ------------
    // get the correct AttributeValue vertex b/c it definitely exists now
    // ------------%(get_value_query)s

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
        """ % {
            "schema_kinds": "|".join(self._node_kinds()),
            "branch_filter": branch_filter,
            "create_value_query": create_value_query,
            "get_value_query": get_value_query,
        }
        self.add_to_query(query)

    def _node_kinds(self) -> list[str]:
        kind = self.migration.previous_schema.kind
        return [kind, f"Profile{kind}", f"Template{kind}"]


class AttributeKindUpdateMigration(AttributeSchemaMigration):
    name: str = "attribute.kind.update"
    queries: Sequence[type[AttributeMigrationQuery]] = [AttributeKindUpdateMigrationQuery]  # type: ignore[assignment]

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
