from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from rich import print as rprint
from rich.console import Console
from rich.table import Table

from infrahub.cli.constants import FAILED_BADGE, SUCCESS_BADGE
from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase


class SchemaFieldType(StrEnum):
    ATTRIBUTE = "attribute"
    RELATIONSHIP = "relationship"


@dataclass
class SchemaFieldDetails:
    schema_kind: str
    schema_uuid: str
    field_type: SchemaFieldType
    field_name: str


class DuplicateSchemaFields(Query):
    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
MATCH (root:Root)
LIMIT 1
WITH root.default_branch AS default_branch
MATCH (field:SchemaAttribute|SchemaRelationship)
CALL (default_branch, field) {
    MATCH (field)-[is_part_of:IS_PART_OF]->(:Root)
    WHERE is_part_of.branch = default_branch
    ORDER BY is_part_of.from DESC
    RETURN is_part_of
    LIMIT 1
}
WITH default_branch, field, CASE
    WHEN is_part_of.status = "active" AND is_part_of.to IS NULL THEN is_part_of.from
    ELSE NULL
END AS active_from
WHERE active_from IS NOT NULL
WITH default_branch, field, active_from, "SchemaAttribute" IN labels(field) AS is_attribute
CALL (field, default_branch) {
    MATCH (field)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[r2:HAS_VALUE]->(name_value:AttributeValue)
    WHERE r1.branch = default_branch AND r2.branch = default_branch
    AND r1.status = "active" AND r2.status = "active"
    AND r1.to IS NULL AND r2.to IS NULL
    ORDER BY r1.from DESC, r1.status ASC, r2.from DESC, r2.status ASC
    LIMIT 1
    RETURN name_value.value AS field_name
}
CALL (field, default_branch) {
    MATCH (field)-[r1:IS_RELATED]-(rel:Relationship)-[r2:IS_RELATED]-(peer:SchemaNode|SchemaGeneric)
    WHERE rel.name IN ["schema__node__relationships", "schema__node__attributes"]
    AND r1.branch = default_branch AND r2.branch = default_branch
    AND r1.status = "active" AND r2.status = "active"
    AND r1.to IS NULL AND r2.to IS NULL
    ORDER BY r1.from DESC, r1.status ASC, r2.from DESC, r2.status ASC
    LIMIT 1
    RETURN peer AS schema_vertex
}
WITH default_branch, field, field_name, is_attribute, active_from, schema_vertex
ORDER BY active_from DESC
WITH default_branch, field_name, is_attribute, schema_vertex, collect(field) AS fields_reverse_chron
WHERE size(fields_reverse_chron) > 1
        """
        self.add_to_query(query)


class GetDuplicateSchemaFields(DuplicateSchemaFields):
    """
    Get the kind, field type, and field name for any duplicated attributes or relationships on a given schema
    on the default branch
    """

    name = "get_duplicate_schema_fields"
    type = QueryType.READ
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:
        await super().query_init(db=db, **kwargs)
        query = """
CALL (schema_vertex, default_branch) {
    MATCH (schema_vertex)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: "namespace"})-[r2:HAS_VALUE]->(name_value:AttributeValue)
    WHERE r1.branch = default_branch AND r2.branch = default_branch
    ORDER BY r1.from DESC, r1.status ASC, r2.from DESC, r2.status ASC
    LIMIT 1
    RETURN name_value.value AS schema_namespace
}
CALL (schema_vertex, default_branch) {
    MATCH (schema_vertex)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[r2:HAS_VALUE]->(name_value:AttributeValue)
    WHERE r1.branch = default_branch AND r2.branch = default_branch
    ORDER BY r1.from DESC, r1.status ASC, r2.from DESC, r2.status ASC
    LIMIT 1
    RETURN name_value.value AS schema_name
}
RETURN schema_namespace + schema_name AS schema_kind, schema_vertex.uuid AS schema_uuid, field_name, is_attribute
ORDER BY schema_kind ASC, is_attribute DESC, field_name ASC
        """
        self.return_labels = ["schema_kind", "schema_uuid", "field_name", "is_attribute"]
        self.add_to_query(query)

    def get_schema_field_details(self) -> list[SchemaFieldDetails]:
        schema_field_details: list[SchemaFieldDetails] = []
        for result in self.results:
            schema_kind = result.get_as_type(label="schema_kind", return_type=str)
            schema_uuid = result.get_as_type(label="schema_uuid", return_type=str)
            field_name = result.get_as_type(label="field_name", return_type=str)
            is_attribute = result.get_as_type(label="is_attribute", return_type=bool)
            schema_field_details.append(
                SchemaFieldDetails(
                    schema_kind=schema_kind,
                    schema_uuid=schema_uuid,
                    field_name=field_name,
                    field_type=SchemaFieldType.ATTRIBUTE if is_attribute else SchemaFieldType.RELATIONSHIP,
                )
            )
        return schema_field_details


class FixDuplicateSchemaFields(DuplicateSchemaFields):
    """
    Fix the duplicate schema fields by hard deleting the earlier duplicate(s)
    """

    name = "fix_duplicate_schema_fields"
    type = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:
        await super().query_init(db=db, **kwargs)
        query = """
WITH default_branch, tail(fields_reverse_chron) AS fields_to_delete
UNWIND fields_to_delete AS field_to_delete
CALL (field_to_delete, default_branch) {
    MATCH (field_to_delete)-[r:IS_PART_OF {branch: default_branch}]-()
    DELETE r
    WITH field_to_delete
    MATCH (field_to_delete)-[:IS_RELATED {branch: default_branch}]-(rel:Relationship)
    WITH DISTINCT field_to_delete, rel
    MATCH (rel)-[r {branch: default_branch}]-()
    DELETE r
    WITH field_to_delete, rel
    OPTIONAL MATCH (rel)
    WHERE NOT exists((rel)--())
    DELETE rel
    WITH DISTINCT field_to_delete
    MATCH (field_to_delete)-[:HAS_ATTRIBUTE {branch: default_branch}]->(attr:Attribute)
    MATCH (attr)-[r {branch: default_branch}]-()
    DELETE r
    WITH field_to_delete, attr
    OPTIONAL MATCH (attr)
    WHERE NOT exists((attr)--())
    DELETE attr
    WITH DISTINCT field_to_delete
    OPTIONAL MATCH (field_to_delete)
    WHERE NOT exists((field_to_delete)--())
    DELETE field_to_delete
}
        """
        self.add_to_query(query)


def display_duplicate_schema_fields(duplicate_schema_fields: list[SchemaFieldDetails]) -> None:
    console = Console()

    table = Table(title="Duplicate Schema Fields on Default Branch")

    table.add_column("Schema Kind")
    table.add_column("Schema UUID")
    table.add_column("Field Name")
    table.add_column("Field Type")

    for duplicate_schema_field in duplicate_schema_fields:
        table.add_row(
            duplicate_schema_field.schema_kind,
            duplicate_schema_field.schema_uuid,
            duplicate_schema_field.field_name,
            duplicate_schema_field.field_type.value,
        )

    console.print(table)


async def clean_duplicate_schema_fields(db: InfrahubDatabase, fix: bool = False) -> bool:
    """
    Identify any attributes or relationships that are duplicated in a schema on the default branch
    If fix is True, runs cypher queries to hard delete the earlier duplicate
    """

    duplicate_schema_fields_query = await GetDuplicateSchemaFields.init(db=db)
    await duplicate_schema_fields_query.execute(db=db)
    duplicate_schema_fields = duplicate_schema_fields_query.get_schema_field_details()

    if not duplicate_schema_fields:
        rprint(f"{SUCCESS_BADGE} No duplicate schema fields found")
        return True

    display_duplicate_schema_fields(duplicate_schema_fields)

    if not fix:
        rprint(f"{FAILED_BADGE} Use the --fix flag to fix the duplicate schema fields")
        return False

    fix_duplicate_schema_fields_query = await FixDuplicateSchemaFields.init(db=db)
    await fix_duplicate_schema_fields_query.execute(db=db)
    rprint(f"{SUCCESS_BADGE} Duplicate schema fields deleted from the default branch")
    return True
