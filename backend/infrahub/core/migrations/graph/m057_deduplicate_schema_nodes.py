from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.migrations.shared import MigrationInput, MigrationResult, get_migration_console
from infrahub.core.query import Query, QueryType
from infrahub.core.schema import GenericSchema, NodeSchema, SchemaRoot, internal_schema
from infrahub.core.schema.manager import SchemaManager
from infrahub.log import get_logger

from ..shared import ArbitraryMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()
console = get_migration_console()


@dataclass
class DuplicateSchemaNodeInfo:
    schema_type: str
    name: str
    namespace: str
    keep_uuid: str
    delete_uuid: str

    @property
    def kind(self) -> str:
        return f"{self.namespace}{self.name}"


class FindDuplicateSchemaNodesQuery(Query):
    name: str = "find_duplicate_schema_nodes"
    type: QueryType = QueryType.READ
    insert_return: bool = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict) -> None:  # noqa: ARG002
        query = """
MATCH (default_b:Branch)
WHERE default_b.is_default = TRUE
WITH default_b.name AS default_branch
LIMIT 1

// -------------------
// for every active Schema on the default branch
// -------------------
MATCH (n:SchemaNode|SchemaGeneric)
CALL (n, default_branch) {
    MATCH (n)-[rp:IS_PART_OF]->(root:Root)
    WHERE rp.branch = default_branch
    RETURN rp
    ORDER BY rp.from DESC
    LIMIT 1
}
WITH n, rp, default_branch
WHERE rp.status = "active" AND rp.to IS NULL

// -------------------
// get its name and namespace
// -------------------
CALL (n) {
    MATCH (n)-[r1:HAS_ATTRIBUTE]->(attr:Attribute {name: "name"})-[r2:HAS_VALUE]->(av:AttributeValue)
    WHERE r1.status = "active" AND r2.status = "active"
    RETURN av.value AS name_value
    ORDER BY r1.from DESC, r1.status ASC, r2.from DESC, r2.status ASC
    LIMIT 1
}
CALL (n) {
    MATCH (n)-[r1:HAS_ATTRIBUTE]->(attr:Attribute {name: "namespace"})-[r2:HAS_VALUE]->(av:AttributeValue)
    WHERE r1.status = "active" AND r2.status = "active"
    RETURN av.value AS namespace_value
    ORDER BY r1.from DESC, r1.status ASC, r2.from DESC, r2.status ASC
    LIMIT 1
}

// -------------------
// get its latest property update time on the default branch
// -------------------
CALL (n, default_branch) {
    MATCH (n)-[:HAS_ATTRIBUTE {branch: default_branch}]->(:Attribute)-[r:HAS_VALUE {branch: default_branch}]->(:AttributeValue)
    WHERE r.status = "active" AND r.to IS NULL
    RETURN max(r.from) AS node_latest
}

// -------------------
// get the latest property update for linked attributes and relationships on the default branch
// -------------------
CALL (n, default_branch) {
    OPTIONAL MATCH (n)-[rc1:IS_RELATED {branch: default_branch}]->(rel:Relationship)
        <-[rc2:IS_RELATED {branch: default_branch}]-(child)
        -[:HAS_ATTRIBUTE {branch: default_branch}]->(:Attribute)
        -[r:HAS_VALUE {branch: default_branch}]->(:AttributeValue)
    WHERE rel.name IN ["schema__node__relationships", "schema__node__attributes"]
    AND rc1.status = "active" AND rc1.to IS NULL
    AND rc2.status = "active" AND rc2.to IS NULL
    AND r.status = "active" AND r.to IS NULL
    RETURN max(r.from) AS child_latest
}

// -------------------
// use the latest Schema, Attribute, or Relationship property update time
// -------------------
WITH n, name_value, namespace_value,
    CASE WHEN child_latest IS NOT NULL AND child_latest > node_latest
        THEN child_latest
        ELSE node_latest
    END AS latest_update,
    CASE WHEN "SchemaNode" IN labels(n) THEN "SchemaNode" ELSE "SchemaGeneric" END AS schema_type
ORDER BY latest_update DESC, elementId(n) DESC
WITH schema_type, name_value, namespace_value, collect(n.uuid) AS uuids
WHERE size(uuids) > 1

// -------------------
// keep the latest update, mark the others to be deleted
// -------------------
UNWIND tail(uuids) AS delete_uuid
RETURN
    schema_type,
    name_value AS name,
    namespace_value AS namespace,
    head(uuids) AS keep_uuid,
    delete_uuid
        """
        self.add_to_query(query)
        self.return_labels = ["schema_type", "name", "namespace", "keep_uuid", "delete_uuid"]

    def get_duplicates(self) -> list[DuplicateSchemaNodeInfo]:
        return [
            DuplicateSchemaNodeInfo(
                schema_type=result.get_as_type("schema_type", return_type=str),
                name=result.get_as_type("name", return_type=str),
                namespace=result.get_as_type("namespace", return_type=str),
                keep_uuid=result.get_as_type("keep_uuid", return_type=str),
                delete_uuid=result.get_as_type("delete_uuid", return_type=str),
            )
            for result in self.get_results()
        ]


class Migration057(ArbitraryMigration):
    name: str = "057_deduplicate_schema_nodes"
    minimum_version: int = 56

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        at = migration_input.at
        user_id = migration_input.user_id

        console.log("[bold]Deduplicating SchemaNode and SchemaGeneric vertices[/bold]")

        # Set up SchemaManager
        manager = SchemaManager()
        registry.schema = manager
        manager.register_schema(schema=SchemaRoot(**internal_schema))
        default_branch = registry.get_branch_from_registry()
        await manager.load_schema_from_db(db=db, branch=default_branch)

        # Find duplicates
        query = await FindDuplicateSchemaNodesQuery.init(db=db)
        await query.execute(db=db)

        duplicates = query.get_duplicates()
        if not duplicates:
            console.log("No duplicate schema nodes found")
            return MigrationResult()

        console.log(f"Found {len(duplicates)} duplicate schema node(s) to remove")

        # Delete older duplicates
        for dup in duplicates:
            console.log(f"Deleting duplicate {dup.schema_type} {dup.kind} (uuid={dup.delete_uuid})")

            obj = await manager.get_one(id=dup.delete_uuid, db=db, branch=default_branch, prefetch_relationships=True)

            schema_obj: NodeSchema | GenericSchema
            if dup.schema_type == "SchemaNode":
                schema_obj = await manager.convert_node_schema_to_schema(schema_node=obj, db=db)
            else:
                schema_obj = await manager.convert_generic_schema_to_schema(schema_node=obj, db=db)

            await manager.delete_node_in_db(db=db, node=schema_obj, user_id=user_id, at=at, branch=default_branch)

        console.log("[bold green]Migration completed successfully[/bold green]")
        return MigrationResult()
