from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generator, Sequence

from infrahub.core.branch.models import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query, QueryType
from infrahub.core.timestamp import Timestamp
from infrahub.log import get_logger

from ..shared import ArbitraryMigration, SchemaMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()


class GetInheritedSchemaFieldIds(Query):
    """Get the IDs of any SchemaAttribute or SchemaRelationship with an active inherited=TRUE value on any branch"""

    name = "get_inherited_schema_field_ids"
    type = QueryType.READ

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params["at"] = self.at.to_string()
        query = """
        // ------------------------
        // find all active inherited=true Attribute nodes
        // ------------------------
        MATCH (attr:Attribute {name: "inherited"})-[r_val:HAS_VALUE]->(:AttributeValue {value: true})
        WHERE r_val.from <= $at AND (r_val.to IS NULL OR r_val.to >= $at)
        AND r_val.status = "active"
        WITH DISTINCT attr
        // ------------------------
        // find all SchemaAttribute and SchemaRelationships nodes linked to the inherited=true Attribute nodes
        // ------------------------
        WITH DISTINCT attr
        MATCH (attr)<-[r_attr:HAS_ATTRIBUTE]-(schema_field)
        WHERE ("SchemaAttribute" IN labels(schema_field) OR "SchemaRelationship" IN labels(schema_field))
        AND r_attr.from <= $at
        AND (r_attr.to IS NULL OR r_attr.to >= $at)
        AND r_attr.status = "active"
        """
        self.add_to_query(query)
        self.return_labels = ["schema_field.uuid AS schema_field_id"]

    def get_schema_field_ids(self) -> Generator[str, None, None]:
        for result in self.get_results():
            yield result.get_as_str(label="schema_field_id")


class Migration023(ArbitraryMigration):
    name: str = "023_duplicate_inherited_schema_fields"
    minimum_version: int = 22
    migrations: Sequence[SchemaMigration] = []

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        result = MigrationResult()
        return result

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        """
        For every SchemaAttribute or SchemaRelationship on every branch:
         - if it has inherited = True, delete it
        """
        at = Timestamp()
        schema_field_query = await GetInheritedSchemaFieldIds.init(db=db, at=at)
        await schema_field_query.execute(db=db)
        schema_field_ids = list(schema_field_query.get_schema_field_ids())

        all_branches = await Branch.get_list(db=db)
        for branch in all_branches:
            schema_fields_map = await NodeManager.get_many(db=db, branch=branch, ids=schema_field_ids)
            for schema_field_obj in schema_fields_map.values():
                if schema_field_obj.inherited.value is True:
                    await schema_field_obj.delete(db=db, at=at)
        return MigrationResult()
