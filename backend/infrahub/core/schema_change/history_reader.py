from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query, QueryType
from infrahub.core.schema_change.enums import SchemaChangeEdgeType, SchemaChangeRecordLabel, SchemaChangeStatus

if TYPE_CHECKING:
    from collections.abc import Generator, Mapping, Sequence

    from infrahub.core.query import CypherValue, QueryResult
    from infrahub.core.schema_change.models import SchemaChange, SchemaChangeApplication, SchemaChangeMigration
    from infrahub.core.schema_change.operations import SchemaOperation
    from infrahub.core.schema_change.record_serializer import SchemaChangeRecordSerializer
    from infrahub.database import InfrahubDatabase

type StoredProperties = Mapping[str, CypherValue]

CYPHER_NAMES = {
    "schema_change_label": SchemaChangeRecordLabel.SCHEMA_CHANGE.value,
    "operation_label": SchemaChangeRecordLabel.OPERATION.value,
    "application_label": SchemaChangeRecordLabel.APPLICATION.value,
    "migration_label": SchemaChangeRecordLabel.MIGRATION.value,
    "has_operation": SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_OPERATION.value,
    "has_application": SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_APPLICATION.value,
    "has_parent": SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_PARENT.value,
    "has_migration": SchemaChangeEdgeType.SCHEMA_APPLICATION_HAS_MIGRATION.value,
}
"""The labels and edge types that the queries write into their text; none of them comes from user input."""


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
    """Return one page of the schema changes of a branch: the applied ones by version, then the others by creation."""

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
        self.params["applied_status"] = SchemaChangeStatus.APPLIED.value
        if statuses is not None:
            self.params["statuses"] = [status.value for status in statuses]

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["page_offset"] = self.offset or 0
        self.params["page_limit"] = self.limit

        self.add_to_query("MATCH (schema_change:%(schema_change_label)s {branch: $branch_name})" % CYPHER_NAMES)
        if self.statuses is not None:
            self.add_to_query("WHERE schema_change.status IN $statuses")
        query = (
            """
        WITH schema_change, CASE WHEN schema_change.status = $applied_status THEN 0 ELSE 1 END AS status_rank
        ORDER BY status_rank, schema_change.version, schema_change.created_at, schema_change.uuid
        SKIP $page_offset
        LIMIT $page_limit
        OPTIONAL MATCH (schema_change)-[:%(has_parent)s]->(parent:%(schema_change_label)s)
        RETURN schema_change {.*} AS schema_change_record, parent {.*} AS parent_record
        ORDER BY status_rank, schema_change.version, schema_change.created_at, schema_change.uuid
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
class SchemaChangeOperationPageQueryResult:
    schema_change_id: str
    count: int
    operations: tuple[StoredProperties, ...]


class SchemaChangeOperationPageQuery(Query):
    """Return one page of the operations of each schema change of a set, in the order of position, with their count."""

    name = "schema-change-operation-page"
    type = QueryType.READ
    insert_return = False
    insert_limit = False

    def __init__(self, schema_change_ids: Sequence[str], limit: int, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.limit = limit
        self.params["schema_change_ids"] = list(schema_change_ids)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["page_offset"] = self.offset or 0
        self.params["page_limit"] = self.limit
        query = (
            """
        MATCH (schema_change:%(schema_change_label)s)
        WHERE schema_change.uuid IN $schema_change_ids
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
            RETURN collect(stored_operation {.*}) AS operations
        }
        RETURN schema_change.uuid AS schema_change_id, count, operations
        """
            % CYPHER_NAMES
        )
        self.add_to_query(query)
        self.return_labels = ["schema_change_id", "count", "operations"]

    def get_data(self) -> Generator[SchemaChangeOperationPageQueryResult, None, None]:
        for result in self.get_results():
            yield SchemaChangeOperationPageQueryResult(
                schema_change_id=result.get_as_type(label="schema_change_id", return_type=str),
                count=result.get_as_type(label="count", return_type=int),
                operations=_property_list(result=result, label="operations"),
            )


@dataclass(frozen=True)
class SchemaChangeApplicationListQueryResult:
    schema_change_id: str
    application: StoredProperties | None
    """`None` for a schema change that has no application."""

    migrations: tuple[StoredProperties, ...]


class SchemaChangeApplicationListQuery(Query):
    """Return the applications of each schema change of a set, each with its migration records in the order of position."""

    name = "schema-change-application-list"
    type = QueryType.READ
    insert_return = False

    def __init__(self, schema_change_ids: Sequence[str], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.params["schema_change_ids"] = list(schema_change_ids)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = (
            """
        MATCH (schema_change:%(schema_change_label)s)
        WHERE schema_change.uuid IN $schema_change_ids
        OPTIONAL MATCH (schema_change)-[:%(has_application)s]->(application:%(application_label)s)
        CALL (application) {
            OPTIONAL MATCH (application)-[:%(has_migration)s]->(record:%(migration_label)s)
            WITH record
            ORDER BY record.position
            RETURN collect(record {.*}) AS migrations
        }
        RETURN schema_change.uuid AS schema_change_id, application {.*} AS application_record, migrations
        ORDER BY schema_change.uuid, application.at, application.uuid
        """
            % CYPHER_NAMES
        )
        self.add_to_query(query)
        self.return_labels = ["schema_change_id", "application_record", "migrations"]

    def get_data(self) -> Generator[SchemaChangeApplicationListQueryResult, None, None]:
        for result in self.get_results():
            yield SchemaChangeApplicationListQueryResult(
                schema_change_id=result.get_as_type(label="schema_change_id", return_type=str),
                application=_optional_properties(
                    value=result.get(label="application_record"), label="application_record"
                ),
                migrations=_property_list(result=result, label="migrations"),
            )


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
class SchemaChangeApplicationRecord:
    application: SchemaChangeApplication
    migrations: list[SchemaChangeMigration]


class SchemaChangeHistoryReader:
    """The paged reads of the schema change history of a branch.

    The reads for a set of schema changes return a key, the `uuid` of the schema change, for each ID
    that names a stored schema change.
    """

    def __init__(self, db: InfrahubDatabase, serializer: SchemaChangeRecordSerializer) -> None:
        self.db = db
        self.serializer = serializer

    async def list_schema_changes(
        self, *, branch: str, limit: int, offset: int, statuses: Sequence[SchemaChangeStatus] | None = None
    ) -> SchemaChangeHistoryPage:
        """Return one page of the schema changes of a branch: the applied ones by version, then the others by creation."""
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
            db=self.db, schema_change_ids=schema_change_ids, limit=limit, offset=offset
        )
        await query.execute(db=self.db)

        pages: dict[str, SchemaOperationPage] = {}
        for row in query.get_data():
            records = [
                self.serializer.operation_from_properties(properties=properties) for properties in row.operations
            ]
            pages[row.schema_change_id] = SchemaOperationPage(
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
        self, *, schema_change_ids: Sequence[str]
    ) -> dict[str, list[SchemaChangeApplicationRecord]]:
        """Return the applications of each schema change, each with its migration records in the order of position."""
        query = await SchemaChangeApplicationListQuery.init(db=self.db, schema_change_ids=schema_change_ids)
        await query.execute(db=self.db)

        applications: dict[str, list[SchemaChangeApplicationRecord]] = {}
        for row in query.get_data():
            records = applications.setdefault(row.schema_change_id, [])
            if row.application is None:
                continue
            records.append(
                SchemaChangeApplicationRecord(
                    application=self.serializer.application_from_properties(properties=row.application),
                    migrations=[
                        self.serializer.migration_from_properties(properties=migration) for migration in row.migrations
                    ],
                )
            )
        return applications
