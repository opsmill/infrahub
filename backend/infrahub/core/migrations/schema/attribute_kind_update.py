from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.types import is_large_attribute_type

from ..query import AttributeMigrationQuery
from ..shared import AttributeSchemaMigration, MigrationResult

if TYPE_CHECKING:
    from infrahub.core.branch.models import Branch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class AttributeKindUpdateMigrationQuery(AttributeMigrationQuery):
    name = "migration_attribute_kind"
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at)
        self.params.update(branch_params)
        needs_index = not is_large_attribute_type(self.migration.new_attribute_schema.kind)
        self.params["needs_index"] = needs_index
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["at"] = self.at.to_string()
        self.params["attr_name"] = self.migration.previous_attribute_schema.name
        new_attr_value_labels = "AttributeValue"
        if needs_index:
            new_attr_value_labels += ":AttributeValueIndexed"
        # ruff: noqa: S608
        query = """
// ------------
// start with all the Attribute vertices we might care about
// ------------
MATCH (n:%(schema_kind)s)-[:HAS_ATTRIBUTE]->(attr:Attribute)
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
CALL (av_is_default, av_value) {
    OPTIONAL MATCH (existing_av:AttributeValue {is_default: av_is_default, value: av_value})
    WHERE "AttributeValueIndexed" IN labels(existing_av) = $needs_index
    WITH existing_av WHERE existing_av IS NULL
    LIMIT 1
    CREATE (:%(new_attr_value_labels)s {is_default: av_is_default, value: av_value})
}

// ------------
// get all the AttributeValue vertices that need to be updated again and run the updates
// ------------
WITH 1 AS one
LIMIT 1
MATCH (n:%(schema_kind)s)-[:HAS_ATTRIBUTE]->(attr:Attribute)
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
    // ------------
    MATCH (new_av:%(new_attr_value_labels)s {is_default: av.is_default, value: av.value})
    WHERE "AttributeValueIndexed" IN labels(new_av) = $needs_index
    LIMIT 1

    // ------------
    // create the new HAS_VALUE edge
    // ------------
    CREATE (attr)-[new_has_value_e:HAS_VALUE]->(new_av)
    SET new_has_value_e = properties(has_value_e)
    SET new_has_value_e.status = "active"
    SET new_has_value_e.branch = $branch
    SET new_has_value_e.branch_level = $branch_level
    SET new_has_value_e.from = $at
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
    SET deleted_has_value_e.to = NULL
}

// ------------
// if the existing edge is on the same branch as the update,
// then set its "to" time
// ------------
CALL (has_value_e) {
    WITH has_value_e
    WHERE has_value_e.branch = $branch
    SET has_value_e.to = $at
}
        """ % {
            "schema_kind": self.migration.previous_schema.kind,
            "branch_filter": branch_filter,
            "new_attr_value_labels": new_attr_value_labels,
        }
        self.add_to_query(query)


class AttributeKindUpdateMigration(AttributeSchemaMigration):
    name: str = "attribute.kind.update"
    queries: Sequence[type[AttributeMigrationQuery]] = [AttributeKindUpdateMigrationQuery]  # type: ignore[assignment]

    async def execute(self, db: InfrahubDatabase, branch: Branch, at: Timestamp | str | None = None) -> MigrationResult:
        is_indexed_previous = is_large_attribute_type(self.previous_attribute_schema.kind)
        is_indexed_new = is_large_attribute_type(self.new_attribute_schema.kind)
        if is_indexed_previous is is_indexed_new:
            return MigrationResult()

        return await super().execute(db=db, branch=branch, at=at)
