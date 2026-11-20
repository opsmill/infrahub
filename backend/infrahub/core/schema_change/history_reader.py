from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query, QueryType
from infrahub.core.schema_change.cypher_names import CYPHER_NAMES

if TYPE_CHECKING:
    from collections.abc import Generator, Mapping, Sequence

    from infrahub.core.query import CypherValue, QueryResult
    from infrahub.core.schema_change.enums import SchemaChangeStatus
    from infrahub.core.schema_change.models import SchemaChange, SchemaChangeApplication, SchemaChangeMigration
    from infrahub.core.schema_change.operations import SchemaOperation
    from infrahub.core.schema_change.record_serializer import SchemaChangeRecordSerializer
    from infrahub.database import InfrahubDatabase

type StoredProperties = Mapping[str, CypherValue]


def _properties(value: CypherValue, label: str) -> StoredProperties:
    if not isinstance(value, dict):
        raise ValueError(f"The column {label} does not hold the properties of a record")
    return value


def _optional_properties(value: CypherValue, label: str) -> StoredProperties | None:
    if value is None:
        return None
    return _properties(value=value, label=label)


def _property_list(result: QueryResult, label: str) -> tuple[StoredProperties, ...]:
    return tuple(_properties(value=item, label=label) for item in result.get_list(label=label))


@dataclass(frozen=True)
class SchemaChangeListQueryResult:
    schema_change: StoredProperties
    parent: StoredProperties | None


class SchemaChangeListQuery(Query):
    """Return one page of the schema changes of a branch, the most recently created first."""

    name = "schema-change-list"
    type = QueryType.READ
    insert_return = False
    insert_limit = False

    def __init__(
        self, branch_name: str, statuses: Sequence[SchemaChangeStatus] | None, limit: int, **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self.limit = limit
        self.statuses = statuses
        self.params["branch_name"] = branch_name
        if statuses is not None:
            self.params["statuses"] = [status.value for status in statuses]

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["page_offset"] = self.offset or 0
        self.params["page_limit"] = self.limit

        self.add_to_query("MATCH (schema_change:%(schema_change_label)s {branch: $branch_name})" % CYPHER_NAMES)
        if self.statuses is not None:
            self.add_to_query("WHERE schema_change.status IN $statuses")
        # Loads and mutations create and apply their schema changes under the schema lock, so on one branch the order
        # of creation is also the order of the versions.
        query = (
            """
        WITH schema_change
        ORDER BY schema_change.created_at DESC, schema_change.uuid DESC
        SKIP $page_offset
        LIMIT $page_limit
        OPTIONAL MATCH (schema_change)-[:%(has_parent)s]->(parent:%(schema_change_label)s)
        RETURN schema_change {.*} AS schema_change_record, parent {.*} AS parent_record
        ORDER BY schema_change.created_at DESC, schema_change.uuid DESC
        """
            % CYPHER_NAMES
        )
        self.add_to_query(query)
        self.return_labels = ["schema_change_record", "parent_record"]

    def get_data(self) -> Generator[SchemaChangeListQueryResult, None, None]:
        for result in self.get_results():
            yield SchemaChangeListQueryResult(
                schema_change=_properties(value=result.get(label="schema_change_record"), label="schema_change_record"),
                parent=_optional_properties(value=result.get(label="parent_record"), label="parent_record"),
            )


class SchemaChangeCountQuery(Query):
    """Count the schema changes of a branch, with an optional status filter."""

    name = "schema-change-count"
    type = QueryType.READ
    insert_return = False

    def __init__(self, branch_name: str, statuses: Sequence[SchemaChangeStatus] | None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.limit = 1
        self.statuses = statuses
        self.params["branch_name"] = branch_name
        if statuses is not None:
            self.params["statuses"] = [status.value for status in statuses]

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.add_to_query("MATCH (schema_change:%(schema_change_label)s {branch: $branch_name})" % CYPHER_NAMES)
        if self.statuses is not None:
            self.add_to_query("WHERE schema_change.status IN $statuses")
        self.add_to_query("RETURN count(schema_change) AS count")
        self.return_labels = ["count"]

    def get_data(self) -> int:
        result = self.get_result()
        if result is None:
            return 0
        return result.get_as_type(label="count", return_type=int)


@dataclass(frozen=True)
class RecordPageQueryResult:
    parent_id: str
    """The `uuid` of the schema change or the application that the records belong to."""

    count: int
    records: tuple[StoredProperties, ...]


class RecordPageQuery(Query):
    """Return one page of the child records of each parent of a set, with the number of child records of each parent.

    A subclass states the pattern of its records in `cypher`, which returns the columns `parent_id`, `count` and
    `records`.
    """

    type = QueryType.READ
    insert_return = False
    insert_limit = False
    cypher: str

    def __init__(self, parent_ids: Sequence[str], limit: int, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.limit = limit
        self.params["parent_ids"] = list(parent_ids)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["page_offset"] = self.offset or 0
        self.params["page_limit"] = self.limit
        self.add_to_query(self.cypher % CYPHER_NAMES)
        self.return_labels = ["parent_id", "count", "records"]

    def get_data(self) -> Generator[RecordPageQueryResult, None, None]:
        for result in self.get_results():
            yield RecordPageQueryResult(
                parent_id=result.get_as_type(label="parent_id", return_type=str),
                count=result.get_as_type(label="count", return_type=int),
                records=_property_list(result=result, label="records"),
            )


class SchemaChangeOperationPageQuery(RecordPageQuery):
    """Return one page of the operations of each schema change of a set, in the order of position."""

    name = "schema-change-operation-page"
    cypher = """
        MATCH (schema_change:%(schema_change_label)s)
        WHERE schema_change.uuid IN $parent_ids
        CALL (schema_change) {
            MATCH (schema_change)-[:%(has_operation)s]->(counted:%(operation_label)s)
            RETURN count(counted) AS count
        }
        CALL (schema_change) {
            MATCH (schema_change)-[:%(has_operation)s]->(stored_operation:%(operation_label)s)
            WITH stored_operation
            ORDER BY stored_operation.position
            SKIP $page_offset
            LIMIT $page_limit
            RETURN collect(stored_operation {.*}) AS records
        }
        RETURN schema_change.uuid AS parent_id, count, records
        """


class SchemaChangeApplicationPageQuery(RecordPageQuery):
    """Return one page of the applications of each schema change of a set, in the order of `at`, then `uuid`."""

    name = "schema-change-application-page"
    cypher = """
        MATCH (schema_change:%(schema_change_label)s)
        WHERE schema_change.uuid IN $parent_ids
        CALL (schema_change) {
            MATCH (schema_change)-[:%(has_application)s]->(counted:%(application_label)s)
            RETURN count(counted) AS count
        }
        CALL (schema_change) {
            MATCH (schema_change)-[:%(has_application)s]->(application:%(application_label)s)
            WITH application
            ORDER BY application.at, application.uuid
            SKIP $page_offset
            LIMIT $page_limit
            RETURN collect(application {.*}) AS records
        }
        RETURN schema_change.uuid AS parent_id, count, records
        """


class SchemaChangeMigrationPageQuery(RecordPageQuery):
    """Return one page of the migration records of each application of a set, in the order of position."""

    name = "schema-change-migration-page"
    cypher = """
        MATCH (application:%(application_label)s)
        WHERE application.uuid IN $parent_ids
        CALL (application) {
            MATCH (application)-[:%(has_migration)s]->(counted:%(migration_label)s)
            RETURN count(counted) AS count
        }
        CALL (application) {
            MATCH (application)-[:%(has_migration)s]->(record:%(migration_label)s)
            WITH record
            ORDER BY record.position, record.uuid
            SKIP $page_offset
            LIMIT $page_limit
            RETURN collect(record {.*}) AS records
        }
        RETURN application.uuid AS parent_id, count, records
        """


@dataclass(frozen=True)
class SchemaChangeHistoryEntry:
    schema_change: SchemaChange
    parent: SchemaChange | None


@dataclass(frozen=True)
class SchemaChangeHistoryPage:
    count: int
    """The number of schema changes that match, on all pages."""

    entries: list[SchemaChangeHistoryEntry]


@dataclass(frozen=True)
class StoredSchemaOperation:
    position: int
    operation: SchemaOperation


@dataclass(frozen=True)
class SchemaOperationPage:
    count: int
    """The number of operations of the schema change, on all pages."""

    operations: list[StoredSchemaOperation]


@dataclass(frozen=True)
class SchemaChangeApplicationPage:
    count: int
    """The number of applications of the schema change, on all pages."""

    applications: list[SchemaChangeApplication]


@dataclass(frozen=True)
class SchemaChangeMigrationPage:
    count: int
    """The number of migration records of the application, on all pages."""

    migrations: list[SchemaChangeMigration]


class SchemaChangeHistoryReader:
    """The paged reads of the schema change history of a branch.

    The reads for a set of schema changes or applications return a key, the `uuid` of the record, for each ID
    that names a stored record.
    """

    def __init__(self, db: InfrahubDatabase, serializer: SchemaChangeRecordSerializer) -> None:
        self.db = db
        self.serializer = serializer

    async def list_schema_changes(
        self, *, branch: str, limit: int, offset: int, statuses: Sequence[SchemaChangeStatus] | None = None
    ) -> SchemaChangeHistoryPage:
        """Return one page of the schema changes of a branch, the most recently created first."""
        list_query = await SchemaChangeListQuery.init(
            db=self.db, branch_name=branch, statuses=statuses, limit=limit, offset=offset
        )
        await list_query.execute(db=self.db)

        return SchemaChangeHistoryPage(
            count=await self.count_schema_changes(branch=branch, statuses=statuses),
            entries=[
                SchemaChangeHistoryEntry(
                    schema_change=self.serializer.schema_change_from_properties(properties=row.schema_change),
                    parent=self.serializer.schema_change_from_properties(properties=row.parent)
                    if row.parent is not None
                    else None,
                )
                for row in list_query.get_data()
            ],
        )

    async def count_schema_changes(self, *, branch: str, statuses: Sequence[SchemaChangeStatus] | None = None) -> int:
        """Return the number of schema changes of a branch, on all pages."""
        count_query = await SchemaChangeCountQuery.init(db=self.db, branch_name=branch, statuses=statuses)
        await count_query.execute(db=self.db)
        return count_query.get_data()

    async def list_operations(
        self, *, schema_change_ids: Sequence[str], limit: int, offset: int
    ) -> dict[str, SchemaOperationPage]:
        """Return one page of the operations of each schema change, in the order of position."""
        query = await SchemaChangeOperationPageQuery.init(
            db=self.db, parent_ids=schema_change_ids, limit=limit, offset=offset
        )
        await query.execute(db=self.db)

        pages: dict[str, SchemaOperationPage] = {}
        for row in query.get_data():
            records = [self.serializer.operation_from_properties(properties=properties) for properties in row.records]
            pages[row.parent_id] = SchemaOperationPage(
                count=row.count,
                operations=[
                    StoredSchemaOperation(
                        position=record.position, operation=self.serializer.record_to_operation(record=record)
                    )
                    for record in records
                ],
            )
        return pages

    async def list_applications(
        self, *, schema_change_ids: Sequence[str], limit: int, offset: int
    ) -> dict[str, SchemaChangeApplicationPage]:
        """Return one page of the applications of each schema change, in the order of `at`, then `uuid`."""
        query = await SchemaChangeApplicationPageQuery.init(
            db=self.db, parent_ids=schema_change_ids, limit=limit, offset=offset
        )
        await query.execute(db=self.db)
        return {
            row.parent_id: SchemaChangeApplicationPage(
                count=row.count,
                applications=[
                    self.serializer.application_from_properties(properties=properties) for properties in row.records
                ],
            )
            for row in query.get_data()
        }

    async def list_migrations(
        self, *, application_ids: Sequence[str], limit: int, offset: int
    ) -> dict[str, SchemaChangeMigrationPage]:
        """Return one page of the migration records of each application, in the order of position."""
        query = await SchemaChangeMigrationPageQuery.init(
            db=self.db, parent_ids=application_ids, limit=limit, offset=offset
        )
        await query.execute(db=self.db)
        return {
            row.parent_id: SchemaChangeMigrationPage(
                count=row.count,
                migrations=[
                    self.serializer.migration_from_properties(properties=properties) for properties in row.records
                ],
            )
            for row in query.get_data()
        }
