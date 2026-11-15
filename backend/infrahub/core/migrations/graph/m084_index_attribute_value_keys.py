from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.constants.database import ATTRIBUTE_VALUE_KEY_LENGTH, IndexType
from infrahub.core.migrations.shared import ArbitraryMigration, MigrationInput, MigrationResult
from infrahub.core.query import Query, QueryType
from infrahub.database import DatabaseType
from infrahub.database.index import IndexItem
from infrahub.database.neo4j import IndexManagerNeo4j

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

VALUE_KEY_INDEX = IndexItem(
    name="attr_value_key", label="AttributeValue", properties=["value_key"], type=IndexType.RANGE
)


class SetAttributeValueKeysQuery(Query):
    """Set the key of every non-indexed string value that has none."""

    name = "set_attribute_value_keys"
    type: QueryType = QueryType.WRITE
    insert_return = False
    raise_error_if_empty = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["value_key_length"] = ATTRIBUTE_VALUE_KEY_LENGTH
        query = """
        MATCH (av:AttributeValue)
        WHERE NOT av:AttributeValueIndexed AND av.value_key IS NULL AND av.value IS :: STRING
        CALL (av) {
            SET av.value_key = left(av.value, $value_key_length)
        } IN TRANSACTIONS
        """
        self.add_to_query(query)


class CountAttributeValuesWithoutKeyQuery(Query):
    name = "count_attribute_values_without_key"
    type: QueryType = QueryType.READ
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
        MATCH (av:AttributeValue)
        WHERE NOT av:AttributeValueIndexed AND av.value_key IS NULL AND av.value IS :: STRING
        RETURN count(av) AS missing_keys
        """
        self.add_to_query(query)
        self.return_labels = ["missing_keys"]

    def get_missing_keys(self) -> int:
        result = self.get_result()
        return result.get_as_type("missing_keys", return_type=int) if result else 0


class Migration084(ArbitraryMigration):
    """Give every value without the AttributeValueIndexed label an indexed key.

    A write looks for an equal value of a large kind (TextArea, JSON, List) before creating one, and without an
    index that lookup reads every attribute value of the database. Non-string values keep no key and are not reused.
    """

    name: str = "084_index_attribute_value_keys"
    description: str = "Index the values of large attribute kinds by a key"
    minimum_version: int = 83

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        result = MigrationResult()

        if db.db_type != DatabaseType.NEO4J:
            return result

        try:
            query = await SetAttributeValueKeysQuery.init(db=db)
            await query.execute(db=db)
            index_manager = IndexManagerNeo4j(db=db)
            index_manager.init(nodes=[VALUE_KEY_INDEX], rels=[])
            await index_manager.add()
        # reported through the result so the runner prints it against this migration
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"Unable to index the attribute value keys: {exc}")

        return result

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:
        result = MigrationResult()

        if db.db_type != DatabaseType.NEO4J:
            return result

        query = await CountAttributeValuesWithoutKeyQuery.init(db=db)
        await query.execute(db=db)
        if missing_keys := query.get_missing_keys():
            result.errors.append(f"{missing_keys} non-indexed attribute values have no key")

        index_manager = IndexManagerNeo4j(db=db)
        existing = {(info.label, tuple(info.properties), info.type) for info in await index_manager.list()}
        if (VALUE_KEY_INDEX.label, tuple(VALUE_KEY_INDEX.properties), VALUE_KEY_INDEX.type) not in existing:
            result.errors.append("range index on AttributeValue(value_key) is missing")

        return result
