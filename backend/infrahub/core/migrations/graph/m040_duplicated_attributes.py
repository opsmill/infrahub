from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query, QueryType

from ..shared import GraphMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class DeleteDuplicatedAttributesQuery(Query):
    name: str = "delete_duplicated_attributes"
    type: QueryType = QueryType.WRITE
    insert_return: bool = False
    insert_limit: bool = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
// -------------
// get all the Nodes linked to multiple Attributes with the same name to drastically reduce the search space
// -------------
MATCH (n:Node)-[:HAS_ATTRIBUTE]->(attr:Attribute)
WITH DISTINCT n, attr
WITH n, attr.name AS attr_name, count(*) AS num_attrs
WHERE num_attrs > 1
// -------------
// for each Node-attr_name pair, get the possible duplicate Attributes
// -------------
MATCH (n)-[:HAS_ATTRIBUTE]->(dup_attr:Attribute {name: attr_name})
WITH DISTINCT n, dup_attr
// -------------
// get the branch(es) for each possible duplicate Attribute
// -------------
CALL (n, dup_attr) {
    MATCH (n)-[r:HAS_ATTRIBUTE {status: "active"}]->(dup_attr)
    WHERE r.to IS NULL
    AND NOT exists((n)-[:HAS_ATTRIBUTE {status: "deleted", branch: r.branch}]->(dup_attr))
    RETURN r.branch AS branch
}
// -------------
// get the latest update time for each duplicate Attribute on each branch
// -------------
CALL (dup_attr, branch) {
    MATCH (dup_attr)-[r {branch: branch}]-()
    RETURN max(r.from) AS latest_update
}
// -------------
// order the duplicate Attributes by latest update time
// -------------
WITH n, dup_attr, branch, latest_update
ORDER BY n, branch, dup_attr.name, latest_update DESC
// -------------
// for any Node-dup_attr_name pairs with multiple duplicate Attributes, keep the Attribute with the latest update
// on this branch and delete all the other edges on this branch for this Attribute
// -------------
WITH n, branch, dup_attr.name AS dup_attr_name, collect(dup_attr) AS dup_attrs_reverse_chronological
WHERE size(dup_attrs_reverse_chronological) > 1
WITH branch, tail(dup_attrs_reverse_chronological) AS dup_attrs_to_delete
UNWIND dup_attrs_to_delete AS dup_attr_to_delete
MATCH (dup_attr_to_delete)-[r {branch: branch}]-()
DELETE r
// -------------
// delete any orphaned Attributes
// -------------
WITH DISTINCT dup_attr_to_delete
WHERE NOT exists((dup_attr_to_delete)--())
DELETE dup_attr_to_delete
        """
        self.add_to_query(query)


class Migration040(GraphMigration):
    name: str = "040_duplicated_attributes"
    queries: Sequence[type[Query]] = [DeleteDuplicatedAttributesQuery]
    minimum_version: int = 39

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()
