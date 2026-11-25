from __future__ import annotations

import math
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
KEY_PENDING_LABEL = "AttributeValueKeyPending"


class AttributeValuesWithoutKeyQuery(Query):
    """Match the values without the AttributeValueIndexed label that have no key yet."""

    name = "attribute_values_without_key"
    type: QueryType = QueryType.READ

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
        MATCH (av:AttributeValue)
        WHERE NOT av:AttributeValueIndexed AND av.value_key IS NULL
        """
        self.add_to_query(query)
        self.return_labels = ["elementId(av) AS element_id"]


class MarkAttributeValuesWithoutKeyQuery(Query):
    """Label the values without the AttributeValueIndexed label that have no key yet.

    The writes are batched, so this query cannot run inside an explicit transaction.
    """

    name = "mark_attribute_values_without_key"
    type: QueryType = QueryType.WRITE
    insert_return = False
    insert_limit = False

    def __init__(self, batch_size: int, **kwargs: Any) -> None:
        self.batch_size = batch_size
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["batch_size"] = self.batch_size
        query = """
        MATCH (av:AttributeValue)
        WHERE NOT av:AttributeValueIndexed AND av.value_key IS NULL
        CALL (av) {
            SET av:%(pending_label)s
        } IN TRANSACTIONS OF $batch_size ROWS
        """ % {"pending_label": KEY_PENDING_LABEL}
        self.add_to_query(query)


class AttributeValuesPendingKeyQuery(Query):
    """Read the values labelled as waiting for a key."""

    name = "attribute_values_pending_key"
    type: QueryType = QueryType.READ

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.add_to_query("MATCH (av:%(pending_label)s)" % {"pending_label": KEY_PENDING_LABEL})
        # The count query leaves out the RETURN clause, so counting does not read the values projected here.
        self.return_labels = ["elementId(av) AS element_id", "av.value AS value"]

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
        MATCH (av:%(pending_label)s)
        WHERE elementId(av) = value_key.element_id
        SET av.value_key = value_key.value_key
        REMOVE av:%(pending_label)s
        """ % {"pending_label": KEY_PENDING_LABEL}
        self.add_to_query(query)


class Migration084(ArbitraryMigration):
    """Give every value of a large attribute kind an indexed hash of the value.

    A write looks for an equal value of a large kind (TextArea, JSON, List) before creating one, and without an
    index that lookup reads every attribute value of the database. Cypher cannot compute the hash, so the keys are
    computed here in batches. The values without a key are labelled first, so that each batch reads only the
    values still waiting for a key, and a run that stops part way leaves the label for the next run to finish.
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
            mark_query = await MarkAttributeValuesWithoutKeyQuery.init(db=db, batch_size=UPDATE_BATCH_SIZE)
            await mark_query.execute(db=db)

            count_query = await AttributeValuesPendingKeyQuery.init(db=db)
            pending_keys = await count_query.count(db=db)
            # The number of batches is fixed up front so that a write that keys nothing cannot repeat forever.
            for _ in range(math.ceil(pending_keys / UPDATE_BATCH_SIZE)):
                # Keying a value removes its label, so each read returns the next values without an offset.
                values_query = await AttributeValuesPendingKeyQuery.init(db=db, limit=UPDATE_BATCH_SIZE)
                await values_query.execute(db=db)
                value_keys = values_query.get_value_keys()
                set_query = await SetAttributeValueKeysQuery.init(db=db, value_keys=value_keys)
                await set_query.execute(db=db)
                if len(value_keys) < UPDATE_BATCH_SIZE:
                    break

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

        count_query = await AttributeValuesWithoutKeyQuery.init(db=db)
        if missing_keys := await count_query.count(db=db):
            result.errors.append(f"{missing_keys} non-indexed attribute values have no key")

        pending_query = await AttributeValuesPendingKeyQuery.init(db=db)
        if pending_keys := await pending_query.count(db=db):
            result.errors.append(f"{pending_keys} attribute values still carry the {KEY_PENDING_LABEL} label")

        index_manager = IndexManagerNeo4j(db=db)
        existing = {(info.label, tuple(info.properties), info.type) for info in await index_manager.list()}
        if (VALUE_KEY_INDEX.label, tuple(VALUE_KEY_INDEX.properties), VALUE_KEY_INDEX.type) not in existing:
            result.errors.append("range index on AttributeValue(value_key) is missing")

        return result
