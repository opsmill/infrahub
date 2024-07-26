from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query, QueryType

from ..shared import GraphMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class Migration012Query01(Query):
    """Add `CoreGenericAccount` inheritance for `CoreAccount`."""

    name = "migration_012_01"
    type: QueryType = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:
        query = """
        MATCH (account:CoreAccount)
        SET account:CoreGenericAccount
        """
        self.add_to_query(query)


class Migration012Query02(Query):
    """Add `CoreGenericAccount` inheritance for `CoreAccount` in the schema."""

    name = "migration_012_02"
    type: QueryType = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:
        query = """
        MATCH (n:SchemaNode)-[]->(:Attribute {name: "name"})-[]->(v:AttributeValue)
        WHERE v.value = "Account"
        CALL {
            WITH n
            MATCH (n)-[]->(:Attribute {name: "namespace"})-[]->(nv:AttributeValue)
            WHERE nv.value = "Core"
            RETURN n AS core_account
        }
        CALL {
            WITH core_account
            MATCH (core_account)-[]->(:Attribute {name: "inherit_from"})-[]->(inherit_from_value:AttributeValue)
            SET inherit_from_value.value = '["LineageOwner","LineageSource", "CoreGenericAccount"]'
        }
        """
        self.add_to_query(query)


class Migration012(GraphMigration):
    """
    * Add `CoreGenericAccount` to labels of `CoreAccount` nodes
    * Add `CoreGenericAccount` to `inherit_from` value of `SchemaNode` with name value `Account`
    * Rename `coreaccount__internalaccounttoken` relationship to `coregenericaccount__internalaccounttoken`
    * Rename `type` attribute to `account_type`
    """

    name: str = "012_add_account_generic"
    queries: Sequence[type[Query]] = [Migration012Query01, Migration012Query02]
    minimum_version: int = 11

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:
        return MigrationResult()
