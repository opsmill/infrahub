from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.constants.database import IndexType
from infrahub.core.graph.schema import get_attribute_value_key
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
UPDATE_BATCH_SIZE = 1000


class AttributeValuesWithoutKeyQuery(Query):
    """List the values without the AttributeValueIndexed label that have no key yet."""

    name = "attribute_values_without_key"
    type: QueryType = QueryType.READ

    def __init__(self, **kwargs: Any) -> None:
        # A stable order keeps the pages of the read from skipping or repeating a value.
        super().__init__(order_by=["element_id"], **kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
        MATCH (av:AttributeValue)
        WHERE NOT av:AttributeValueIndexed AND av.value_key IS NULL
        WITH elementId(av) AS element_id
        """
        self.add_to_query(query)
        self.return_labels = ["element_id"]

    def get_element_ids(self) -> list[str]:
        return [result.get_as_type("element_id", return_type=str) for result in self.get_results()]


class AttributeValuesByIdQuery(Query):
    name = "attribute_values_by_id"
    type: QueryType = QueryType.READ

    def __init__(self, element_ids: list[str], **kwargs: Any) -> None:
        self.element_ids = element_ids
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["element_ids"] = self.element_ids
        query = """
        UNWIND $element_ids AS element_id
        MATCH (av:AttributeValue)
        WHERE elementId(av) = element_id
        WITH element_id, av.value AS value
        """
        self.add_to_query(query)
        self.return_labels = ["element_id", "value"]

    def get_value_keys(self) -> list[dict[str, str]]:
        return [
            {
                "element_id": result.get_as_type("element_id", return_type=str),
                "value_key": get_attribute_value_key(result.get("value")),
            }
            for result in self.get_results()
        ]


class SetAttributeValueKeysQuery(Query):
    name = "set_attribute_value_keys"
    type: QueryType = QueryType.WRITE
    insert_return = False
    raise_error_if_empty = False

    def __init__(self, value_keys: list[dict[str, str]], **kwargs: Any) -> None:
        self.value_keys = value_keys
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["value_keys"] = self.value_keys
        query = """
        UNWIND $value_keys AS value_key
        MATCH (av:AttributeValue)
        WHERE elementId(av) = value_key.element_id
        SET av.value_key = value_key.value_key
        """
        self.add_to_query(query)


class Migration084(ArbitraryMigration):
    """Give every value of a large attribute kind an indexed hash of the value.

    A write looks for an equal value of a large kind (TextArea, JSON, List) before creating one, and without an
    index that lookup reads every attribute value of the database. Cypher cannot compute the hash, so the keys are
    computed here in batches.
    """

    name: str = "084_index_attribute_value_keys"
    description: str = "Index the values of large attribute kinds by a hash"
    minimum_version: int = 83

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        result = MigrationResult()

        if db.db_type != DatabaseType.NEO4J:
            return result

        try:
            ids_query = await AttributeValuesWithoutKeyQuery.init(db=db)
            await ids_query.execute(db=db)
            element_ids = ids_query.get_element_ids()
            for start in range(0, len(element_ids), UPDATE_BATCH_SIZE):
                values_query = await AttributeValuesByIdQuery.init(
                    db=db, element_ids=element_ids[start : start + UPDATE_BATCH_SIZE]
                )
                await values_query.execute(db=db)
                set_query = await SetAttributeValueKeysQuery.init(db=db, value_keys=values_query.get_value_keys())
                await set_query.execute(db=db)

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

        ids_query = await AttributeValuesWithoutKeyQuery.init(db=db)
        await ids_query.execute(db=db)
        if missing_keys := len(ids_query.get_element_ids()):
            result.errors.append(f"{missing_keys} non-indexed attribute values have no key")

        index_manager = IndexManagerNeo4j(db=db)
        existing = {(info.label, tuple(info.properties), info.type) for info in await index_manager.list()}
        if (VALUE_KEY_INDEX.label, tuple(VALUE_KEY_INDEX.properties), VALUE_KEY_INDEX.type) not in existing:
            result.errors.append("range index on AttributeValue(value_key) is missing")

        return result
