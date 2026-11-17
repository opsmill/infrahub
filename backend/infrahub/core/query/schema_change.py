from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.constants import NULL_VALUE, SchemaPathType
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.query import Query, QueryType
from infrahub.core.schema_change.constants import (
    SchemaChangeApplicationStatus,
    SchemaChangeEdgeType,
    SchemaChangeMigrationStatus,
    SchemaChangeStatus,
    SchemaOperationNodeType,
    SchemaOperationSection,
    SchemaOperationType,
)
from infrahub.core.schema_change.models import (
    SchemaChange,
    SchemaChangeApplication,
    SchemaChangeMigration,
    SchemaChangeOperation,
)

if TYPE_CHECKING:
    from collections.abc import Generator, Mapping, Sequence

    from infrahub.core.query import CypherValue, QueryResult
    from infrahub.database import InfrahubDatabase


LABELS_AND_EDGE_TYPES = {
    "schema_change_label": SchemaChange.get_type(),
    "operation_label": SchemaChangeOperation.get_type(),
    "application_label": SchemaChangeApplication.get_type(),
    "migration_label": SchemaChangeMigration.get_type(),
    "is_part_of": DatabaseEdgeType.IS_PART_OF.value,
    "has_operation": SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_OPERATION.value,
    "has_application": SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_APPLICATION.value,
    "has_parent": SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_PARENT.value,
    "has_migration": SchemaChangeEdgeType.SCHEMA_APPLICATION_HAS_MIGRATION.value,
}
"""The labels and edge types that the queries write into their text; none of them comes from user input."""


@dataclass(frozen=True)
class StoredRecordMetadata:
    db_id: str
    uuid: str
    created_at: str | None
    created_by: str
    updated_at: str | None
    updated_by: str | None


@dataclass(frozen=True)
class SchemaChangeRecordData:
    metadata: StoredRecordMetadata
    branch: str
    status: SchemaChangeStatus
    version: int | None
    summary: str
    format_version: int
    applied_at: str | None


@dataclass(frozen=True)
class SchemaChangeOperationRecordData:
    metadata: StoredRecordMetadata
    position: int
    operation_type: SchemaOperationType
    kind: str
    node_type: SchemaOperationNodeType | None
    section: SchemaOperationSection | None
    element_name: str | None
    property_name: str | None
    value: str | None
    previous_value: str | None


@dataclass(frozen=True)
class SchemaChangeApplicationRecordData:
    metadata: StoredRecordMetadata
    branch: str
    status: SchemaChangeApplicationStatus
    at: str
    error: str | None


@dataclass(frozen=True)
class SchemaChangeMigrationRecordData:
    metadata: StoredRecordMetadata
    position: int
    migration_name: str
    path_type: SchemaPathType
    schema_kind: str
    field_name: str | None
    property_name: str | None
    status: SchemaChangeMigrationStatus
    nbr_migrations_executed: int | None
    errors: tuple[str, ...]


class StoredProperties:
    """The properties of one record as a query returned them, read with the type each one is stored with.

    A property whose value is the text `NULL` is read as `None`, as `StandardNode` stores `None`.
    """

    def __init__(self, label: str, properties: Mapping[str, CypherValue]) -> None:
        self.label = label
        self.properties = properties

    def text(self, key: str) -> str:
        """Return a text property.

        Raises:
            ValueError: When the property is not a text.

        """
        value = self.properties.get(key)
        if isinstance(value, str):
            return value
        raise ValueError(f"The property {key} of {self.label} is not a text")

    def optional_text(self, key: str) -> str | None:
        """Return a text property that may be not set.

        Raises:
            ValueError: When the property is set to something other than a text.

        """
        value = self.properties.get(key)
        if value is None or value == NULL_VALUE:
            return None
        if isinstance(value, str):
            return value
        raise ValueError(f"The property {key} of {self.label} is not a text")

    def integer(self, key: str) -> int:
        """Return an integer property.

        Raises:
            ValueError: When the property is not an integer.

        """
        value = self.properties.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        raise ValueError(f"The property {key} of {self.label} is not an integer")

    def optional_integer(self, key: str) -> int | None:
        """Return an integer property that may be not set.

        Raises:
            ValueError: When the property is set to something other than an integer.

        """
        value = self.properties.get(key)
        if value is None or value == NULL_VALUE:
            return None
        return self.integer(key=key)

    def texts(self, key: str) -> tuple[str, ...]:
        """Return a property that holds a list of texts.

        Raises:
            ValueError: When the property is not a list of texts.

        """
        value = self.properties.get(key)
        if not isinstance(value, list):
            raise ValueError(f"The property {key} of {self.label} is not a list")
        texts: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError(f"The property {key} of {self.label} holds an item that is not a text")
            texts.append(item)
        return tuple(texts)

    def metadata(self) -> StoredRecordMetadata:
        return StoredRecordMetadata(
            db_id=self.text(key="db_id"),
            uuid=self.text(key="uuid"),
            created_at=self.optional_text(key="created_at"),
            created_by=self.text(key="created_by"),
            updated_at=self.optional_text(key="updated_at"),
            updated_by=self.optional_text(key="updated_by"),
        )


def _read_properties(value: CypherValue, label: str) -> StoredProperties:
    if not isinstance(value, dict):
        raise ValueError(f"The column {label} does not hold the properties of a record")
    return StoredProperties(label=label, properties=value)


def _read_optional_properties(value: CypherValue, label: str) -> StoredProperties | None:
    if value is None:
        return None
    return _read_properties(value=value, label=label)


def _read_schema_change(properties: StoredProperties) -> SchemaChangeRecordData:
    return SchemaChangeRecordData(
        metadata=properties.metadata(),
        branch=properties.text(key="branch"),
        status=SchemaChangeStatus(properties.text(key="status")),
        version=properties.optional_integer(key="version"),
        summary=properties.text(key="summary"),
        format_version=properties.integer(key="format_version"),
        applied_at=properties.optional_text(key="applied_at"),
    )


def _read_operation(properties: StoredProperties) -> SchemaChangeOperationRecordData:
    node_type = properties.optional_text(key="node_type")
    section = properties.optional_text(key="section")
    return SchemaChangeOperationRecordData(
        metadata=properties.metadata(),
        position=properties.integer(key="position"),
        operation_type=SchemaOperationType(properties.text(key="operation_type")),
        kind=properties.text(key="kind"),
        node_type=SchemaOperationNodeType(node_type) if node_type is not None else None,
        section=SchemaOperationSection(section) if section is not None else None,
        element_name=properties.optional_text(key="element_name"),
        property_name=properties.optional_text(key="property_name"),
        value=properties.optional_text(key="value"),
        previous_value=properties.optional_text(key="previous_value"),
    )


def _read_application(properties: StoredProperties) -> SchemaChangeApplicationRecordData:
    return SchemaChangeApplicationRecordData(
        metadata=properties.metadata(),
        branch=properties.text(key="branch"),
        status=SchemaChangeApplicationStatus(properties.text(key="status")),
        at=properties.text(key="at"),
        error=properties.optional_text(key="error"),
    )


def _read_migration(properties: StoredProperties) -> SchemaChangeMigrationRecordData:
    return SchemaChangeMigrationRecordData(
        metadata=properties.metadata(),
        position=properties.integer(key="position"),
        migration_name=properties.text(key="migration_name"),
        path_type=SchemaPathType(properties.text(key="path_type")),
        schema_kind=properties.text(key="schema_kind"),
        field_name=properties.optional_text(key="field_name"),
        property_name=properties.optional_text(key="property_name"),
        status=SchemaChangeMigrationStatus(properties.text(key="status")),
        nbr_migrations_executed=properties.optional_integer(key="nbr_migrations_executed"),
        errors=properties.texts(key="errors"),
    )


def _read_record_list(result: QueryResult, label: str) -> list[StoredProperties]:
    return [_read_properties(value=item, label=label) for item in result.get_list(label=label)]


@dataclass(frozen=True)
class SchemaChangeCreateQueryResult:
    schema_change_id: str
    application_id: str


class SchemaChangeCreateQuery(Query):
    """Create a schema change, its operations and one application, each linked to the root."""

    name = "schema-change-create"
    type = QueryType.WRITE
    insert_return = False
    raise_error_if_empty = True

    def __init__(
        self,
        schema_change_properties: Mapping[str, Any],
        operation_properties: Sequence[Mapping[str, Any]],
        application_properties: Mapping[str, Any],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.params["schema_change"] = dict(schema_change_properties)
        self.params["operations"] = [dict(properties) for properties in operation_properties]
        self.params["application"] = dict(application_properties)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = (
            """
        MATCH (root:Root)
        CREATE (schema_change:%(schema_change_label)s $schema_change)-[:%(is_part_of)s]->(root)
        CREATE (application:%(application_label)s $application)-[:%(is_part_of)s]->(root)
        CREATE (schema_change)-[:%(has_application)s]->(application)
        WITH root, schema_change, application
        CALL (root, schema_change) {
            UNWIND $operations AS operation
            CREATE (stored_operation:%(operation_label)s)-[:%(is_part_of)s]->(root)
            SET stored_operation = operation
            CREATE (schema_change)-[:%(has_operation)s]->(stored_operation)
        }
        RETURN schema_change.uuid AS schema_change_id, application.uuid AS application_id
        """
            % LABELS_AND_EDGE_TYPES
        )
        self.add_to_query(query)
        self.return_labels = ["schema_change_id", "application_id"]

    def get_data(self) -> SchemaChangeCreateQueryResult:
        """Return the IDs of the records created.

        Raises:
            ValueError: When the query has not been executed.

        """
        result = self.get_result()
        if result is None:
            raise ValueError("The schema change was not created")
        return SchemaChangeCreateQueryResult(
            schema_change_id=result.get_as_type(label="schema_change_id", return_type=str),
            application_id=result.get_as_type(label="application_id", return_type=str),
        )


@dataclass(frozen=True)
class SchemaChangeMigrationCreateQueryResult:
    position: int
    record_id: str


class SchemaChangeMigrationCreateQuery(Query):
    """Create the migration records of an application, each linked to the root."""

    name = "schema-change-migration-create"
    type = QueryType.WRITE
    insert_return = False
    raise_error_if_empty = True

    def __init__(self, application_id: str, migration_properties: Sequence[Mapping[str, Any]], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.params["application_id"] = application_id
        self.params["migrations"] = [dict(properties) for properties in migration_properties]

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
        MATCH (root:Root)
        MATCH (application:%(application_label)s {uuid: $application_id})
        UNWIND $migrations AS migration
        CREATE (record:%(migration_label)s)-[:%(is_part_of)s]->(root)
        SET record = migration
        CREATE (application)-[:%(has_migration)s]->(record)
        RETURN record.position AS position, %(id_function)s(record) AS record_id
        """ % {**LABELS_AND_EDGE_TYPES, "id_function": db.get_id_function_name()}
        self.add_to_query(query)
        self.return_labels = ["position", "record_id"]

    def get_data(self) -> Generator[SchemaChangeMigrationCreateQueryResult, None, None]:
        for result in self.get_results():
            yield SchemaChangeMigrationCreateQueryResult(
                position=result.get_as_type(label="position", return_type=int),
                record_id=result.get_as_type(label="record_id", return_type=str),
            )


class SchemaChangeMigrationStatusUpdateQuery(Query):
    """Set the status, the result and the errors of the migration records selected by element ID."""

    name = "schema-change-migration-status-update"
    type = QueryType.WRITE
    insert_return = False

    def __init__(
        self,
        record_ids: Sequence[str],
        status: SchemaChangeMigrationStatus,
        nbr_migrations_executed: int | None,
        errors: Sequence[str],
        updated_at: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.params["record_ids"] = list(record_ids)
        self.params["status"] = status.value
        self.params["nbr_migrations_executed"] = (
            nbr_migrations_executed if nbr_migrations_executed is not None else NULL_VALUE
        )
        self.params["errors"] = list(errors)
        self.params["updated_at"] = updated_at

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
        MATCH (record:%(migration_label)s)
        WHERE %(id_function)s(record) IN $record_ids
        SET record.status = $status,
            record.nbr_migrations_executed = $nbr_migrations_executed,
            record.errors = $errors,
            record.updated_at = $updated_at
        """ % {**LABELS_AND_EDGE_TYPES, "id_function": db.get_id_function_name()}
        self.add_to_query(query)


class SchemaChangeMarkAppliedQuery(Query):
    """Set a schema change and its application to applied, with the version, the time and the parent."""

    name = "schema-change-mark-applied"
    type = QueryType.WRITE
    insert_return = False
    raise_error_if_empty = True

    def __init__(
        self,
        schema_change_id: str,
        application_id: str,
        version: int,
        parent_id: str | None,
        applied_at: str,
        updated_at: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.parent_id = parent_id
        self.params["schema_change_id"] = schema_change_id
        self.params["application_id"] = application_id
        self.params["parent_id"] = parent_id
        self.params["version"] = version
        self.params["applied_at"] = applied_at
        self.params["updated_at"] = updated_at
        self.params["updated_by"] = self.user_id
        self.params["schema_change_status"] = SchemaChangeStatus.APPLIED.value
        self.params["application_status"] = SchemaChangeApplicationStatus.APPLIED.value

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.add_to_query(
            """
            MATCH (schema_change:%(schema_change_label)s {uuid: $schema_change_id})
                -[:%(has_application)s]->(application:%(application_label)s {uuid: $application_id})
            """
            % LABELS_AND_EDGE_TYPES
        )
        if self.parent_id is not None:
            self.add_to_query("MATCH (parent:%(schema_change_label)s {uuid: $parent_id})" % LABELS_AND_EDGE_TYPES)
        self.add_to_query(
            """
            SET schema_change.status = $schema_change_status,
                schema_change.version = $version,
                schema_change.applied_at = $applied_at,
                schema_change.updated_at = $updated_at,
                schema_change.updated_by = $updated_by,
                application.status = $application_status,
                application.updated_at = $updated_at,
                application.updated_by = $updated_by
            """
        )
        if self.parent_id is not None:
            self.add_to_query("CREATE (schema_change)-[:%(has_parent)s]->(parent)" % LABELS_AND_EDGE_TYPES)
        self.add_to_query("RETURN schema_change.uuid AS schema_change_id")
        self.return_labels = ["schema_change_id"]


class SchemaChangeMarkFailedQuery(Query):
    """Set a schema change and its application to failed, and roll back the applied migration records."""

    name = "schema-change-mark-failed"
    type = QueryType.WRITE
    insert_return = False
    raise_error_if_empty = True

    def __init__(self, schema_change_id: str, application_id: str, error: str, updated_at: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.params["schema_change_id"] = schema_change_id
        self.params["application_id"] = application_id
        self.params["error"] = error
        self.params["updated_at"] = updated_at
        self.params["updated_by"] = self.user_id
        self.params["schema_change_status"] = SchemaChangeStatus.FAILED.value
        self.params["application_status"] = SchemaChangeApplicationStatus.FAILED.value
        self.params["applied_migration_status"] = SchemaChangeMigrationStatus.APPLIED.value
        self.params["rolled_back_migration_status"] = SchemaChangeMigrationStatus.ROLLED_BACK.value

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = (
            """
        MATCH (schema_change:%(schema_change_label)s {uuid: $schema_change_id})
            -[:%(has_application)s]->(application:%(application_label)s {uuid: $application_id})
        SET schema_change.status = $schema_change_status,
            schema_change.updated_at = $updated_at,
            schema_change.updated_by = $updated_by,
            application.status = $application_status,
            application.error = $error,
            application.updated_at = $updated_at,
            application.updated_by = $updated_by
        WITH schema_change, application
        CALL (application) {
            MATCH (application)-[:%(has_migration)s]->(record:%(migration_label)s {status: $applied_migration_status})
            SET record.status = $rolled_back_migration_status,
                record.updated_at = $updated_at
        }
        RETURN schema_change.uuid AS schema_change_id
        """
            % LABELS_AND_EDGE_TYPES
        )
        self.add_to_query(query)
        self.return_labels = ["schema_change_id"]


@dataclass(frozen=True)
class SchemaChangeVersionQueryResult:
    schema_change_id: str
    version: int


class SchemaChangeHighestVersionQuery(Query):
    """Return the applied schema change with the highest version on a branch."""

    name = "schema-change-highest-version"
    type = QueryType.READ
    insert_return = False

    def __init__(self, branch_name: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.limit = 1
        self.params["branch_name"] = branch_name
        self.params["applied_status"] = SchemaChangeStatus.APPLIED.value

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
        MATCH (schema_change:%(schema_change_label)s {branch: $branch_name, status: $applied_status})
        RETURN schema_change.uuid AS schema_change_id, schema_change.version AS version
        ORDER BY schema_change.version DESC, %(id_function)s(schema_change)
        """ % {**LABELS_AND_EDGE_TYPES, "id_function": db.get_id_function_name()}
        self.add_to_query(query)
        self.return_labels = ["schema_change_id", "version"]

    def get_data(self) -> SchemaChangeVersionQueryResult | None:
        result = self.get_result()
        if result is None:
            return None
        return SchemaChangeVersionQueryResult(
            schema_change_id=result.get_as_type(label="schema_change_id", return_type=str),
            version=result.get_as_type(label="version", return_type=int),
        )


class SchemaChangeHighestVersionAtQuery(Query):
    """Return the applied schema change with the highest version on a branch, among those applied at or before a time."""

    name = "schema-change-highest-version-at"
    type = QueryType.READ
    insert_return = False

    def __init__(self, branch_name: str, applied_at_or_before: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.limit = 1
        self.params["branch_name"] = branch_name
        self.params["applied_at_or_before"] = applied_at_or_before
        self.params["applied_status"] = SchemaChangeStatus.APPLIED.value

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
        MATCH (schema_change:%(schema_change_label)s {branch: $branch_name, status: $applied_status})
        WHERE schema_change.applied_at <= $applied_at_or_before
        RETURN schema_change.uuid AS schema_change_id, schema_change.version AS version
        ORDER BY schema_change.version DESC, %(id_function)s(schema_change)
        """ % {**LABELS_AND_EDGE_TYPES, "id_function": db.get_id_function_name()}
        self.add_to_query(query)
        self.return_labels = ["schema_change_id", "version"]

    def get_data(self) -> SchemaChangeVersionQueryResult | None:
        result = self.get_result()
        if result is None:
            return None
        return SchemaChangeVersionQueryResult(
            schema_change_id=result.get_as_type(label="schema_change_id", return_type=str),
            version=result.get_as_type(label="version", return_type=int),
        )


@dataclass(frozen=True)
class SchemaChangeListQueryResult:
    schema_change: SchemaChangeRecordData
    parent: SchemaChangeRecordData | None


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
        variables = {**LABELS_AND_EDGE_TYPES, "id_function": db.get_id_function_name()}

        self.add_to_query("MATCH (schema_change:%(schema_change_label)s {branch: $branch_name})" % variables)
        if self.statuses is not None:
            self.add_to_query("WHERE schema_change.status IN $statuses")
        query = (
            """
        WITH schema_change, CASE WHEN schema_change.status = $applied_status THEN 0 ELSE 1 END AS status_rank
        ORDER BY status_rank, schema_change.version, schema_change.created_at, %(id_function)s(schema_change)
        SKIP $page_offset
        LIMIT $page_limit
        OPTIONAL MATCH (schema_change)-[:%(has_parent)s]->(parent:%(schema_change_label)s)
        RETURN
            schema_change {.*, db_id: %(id_function)s(schema_change)} AS schema_change_record,
            CASE WHEN parent IS NULL THEN NULL ELSE parent {.*, db_id: %(id_function)s(parent)} END AS parent_record
        ORDER BY status_rank, schema_change.version, schema_change.created_at, %(id_function)s(schema_change)
        """
            % variables
        )
        self.add_to_query(query)
        self.return_labels = ["schema_change_record", "parent_record"]

    def get_data(self) -> Generator[SchemaChangeListQueryResult, None, None]:
        for result in self.get_results():
            parent = _read_optional_properties(value=result.get(label="parent_record"), label="parent_record")
            yield SchemaChangeListQueryResult(
                schema_change=_read_schema_change(
                    properties=_read_properties(
                        value=result.get(label="schema_change_record"), label="schema_change_record"
                    )
                ),
                parent=_read_schema_change(properties=parent) if parent is not None else None,
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
        self.add_to_query(
            "MATCH (schema_change:%(schema_change_label)s {branch: $branch_name})" % LABELS_AND_EDGE_TYPES
        )
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
    operations: tuple[SchemaChangeOperationRecordData, ...]


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
        query = """
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
            RETURN collect(stored_operation {.*, db_id: %(id_function)s(stored_operation)}) AS operations
        }
        RETURN schema_change.uuid AS schema_change_id, count, operations
        """ % {**LABELS_AND_EDGE_TYPES, "id_function": db.get_id_function_name()}
        self.add_to_query(query)
        self.return_labels = ["schema_change_id", "count", "operations"]

    def get_data(self) -> Generator[SchemaChangeOperationPageQueryResult, None, None]:
        for result in self.get_results():
            yield SchemaChangeOperationPageQueryResult(
                schema_change_id=result.get_as_type(label="schema_change_id", return_type=str),
                count=result.get_as_type(label="count", return_type=int),
                operations=tuple(
                    _read_operation(properties=properties)
                    for properties in _read_record_list(result=result, label="operations")
                ),
            )


@dataclass(frozen=True)
class SchemaChangeApplicationListQueryResult:
    schema_change_id: str
    application: SchemaChangeApplicationRecordData | None
    """`None` for a schema change that has no application."""

    migrations: tuple[SchemaChangeMigrationRecordData, ...]


class SchemaChangeApplicationListQuery(Query):
    """Return the applications of each schema change of a set, each with its migration records in the order of position."""

    name = "schema-change-application-list"
    type = QueryType.READ
    insert_return = False

    def __init__(self, schema_change_ids: Sequence[str], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.params["schema_change_ids"] = list(schema_change_ids)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
        MATCH (schema_change:%(schema_change_label)s)
        WHERE schema_change.uuid IN $schema_change_ids
        OPTIONAL MATCH (schema_change)-[:%(has_application)s]->(application:%(application_label)s)
        CALL (application) {
            OPTIONAL MATCH (application)-[:%(has_migration)s]->(record:%(migration_label)s)
            WITH record
            ORDER BY record.position
            RETURN collect(record {.*, db_id: %(id_function)s(record)}) AS migrations
        }
        RETURN
            schema_change.uuid AS schema_change_id,
            CASE WHEN application IS NULL THEN NULL
                ELSE application {.*, db_id: %(id_function)s(application)} END AS application_record,
            migrations
        ORDER BY schema_change.uuid, application.at, %(id_function)s(application)
        """ % {**LABELS_AND_EDGE_TYPES, "id_function": db.get_id_function_name()}
        self.add_to_query(query)
        self.return_labels = ["schema_change_id", "application_record", "migrations"]

    def get_data(self) -> Generator[SchemaChangeApplicationListQueryResult, None, None]:
        for result in self.get_results():
            application = _read_optional_properties(
                value=result.get(label="application_record"), label="application_record"
            )
            yield SchemaChangeApplicationListQueryResult(
                schema_change_id=result.get_as_type(label="schema_change_id", return_type=str),
                application=_read_application(properties=application) if application is not None else None,
                migrations=tuple(
                    _read_migration(properties=properties)
                    for properties in _read_record_list(result=result, label="migrations")
                ),
            )


class SchemaChangeDeleteByBranchQuery(Query):
    """Delete up to a batch of the schema changes of a branch, each with its operations, applications and migration records.

    Run repeatedly until it deletes nothing.
    """

    name = "schema-change-delete-by-branch"
    type = QueryType.WRITE
    insert_return = False
    insert_limit = False

    def __init__(self, branch_name: str, batch_size: int, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.params["branch_name"] = branch_name
        self.params["batch_size"] = batch_size

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = (
            """
        MATCH (schema_change:%(schema_change_label)s {branch: $branch_name})
        WITH schema_change
        LIMIT $batch_size
        CALL (schema_change) {
            MATCH (schema_change)-[:%(has_operation)s|%(has_application)s|%(has_migration)s*1..2]->(record)
            DETACH DELETE record
        }
        DETACH DELETE schema_change
        RETURN count(*) AS nbr_deleted
        """
            % LABELS_AND_EDGE_TYPES
        )
        self.add_to_query(query)
        self.return_labels = ["nbr_deleted"]

    def get_data(self) -> int:
        """Return the number of schema changes deleted."""
        result = self.get_result()
        if result is None:
            return 0
        return result.get_as_type(label="nbr_deleted", return_type=int)
