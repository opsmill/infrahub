from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import SYSTEM_USER_ID
from infrahub.core.schema_change.enums import (
    SchemaChangeEdgeType,
    SchemaChangeMigrationStatus,
    SchemaChangeStatus,
    SchemaOperationNodeType,
    SchemaOperationSection,
    SchemaOperationType,
)
from infrahub.core.schema_change.factory import build_schema_change_history_reader, build_schema_change_repository
from infrahub.core.schema_change.operations import SchemaOperation
from infrahub.core.timestamp import Timestamp
from tests.helpers.schema_change import (
    BranchHistorySeed,
    MigrationSeed,
    attribute_migration,
    count_schema_change_record_edges_to_root,
    seed_schema_change_history,
)

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

BRANCH_NAME = "main"
EDGE_PROPERTIES_OF_BRANCH_AWARE_GRAPH = frozenset({"branch", "from", "to", "status"})


async def _read_record_edges(db: InfrahubDatabase) -> list[tuple[str, str, str, list[str]]]:
    """Return each edge between two records as its type, the labels of both ends and its property names."""
    results = await db.execute_query(
        query="""
        MATCH (source)-[edge]->(destination)
        WHERE type(edge) IN $edge_types
        RETURN type(edge) AS edge_type, labels(source)[0] AS source_label,
            labels(destination)[0] AS destination_label, keys(edge) AS edge_keys
        """,
        params={"edge_types": [edge_type.value for edge_type in SchemaChangeEdgeType]},
        name="test_schema_change_record_edges",
    )
    return sorted(
        (
            str(result.get("edge_type")),
            str(result.get("source_label")),
            str(result.get("destination_label")),
            sorted(result.get("edge_keys")),
        )
        for result in results
    )


async def _read_edges_of_schema_change(db: InfrahubDatabase, schema_change_id: str) -> list[tuple[str, str, str]]:
    """Return each edge that leaves a schema change, as its type, the label of its end and what identifies that end."""
    results = await db.execute_query(
        query="""
        MATCH (:SchemaChange {uuid: $schema_change_id})-[edge]->(destination)
        RETURN type(edge) AS edge_type, labels(destination)[0] AS destination_label,
            coalesce(toString(destination.position), destination.uuid) AS destination_identifier
        """,
        params={"schema_change_id": schema_change_id},
        name="test_schema_change_edges_of_one",
    )
    return sorted(
        (
            str(result.get("edge_type")),
            str(result.get("destination_label")),
            str(result.get("destination_identifier")),
        )
        for result in results
    )


async def test_create_schema_change_stores_operations_in_order_and_links_the_records(
    db: InfrahubDatabase, empty_database: None
) -> None:
    history = await seed_schema_change_history(
        db=db, branches=[BranchHistorySeed(branch=BRANCH_NAME, changes=[SchemaChangeStatus.APPLIED])]
    )
    parent_id = history.schema_changes[0].id
    operations = [
        SchemaOperation(
            operation_type=SchemaOperationType.NODE_ADD,
            kind="TestBoat",
            node_type=SchemaOperationNodeType.NODE,
            value={"name": "Boat", "namespace": "Test"},
        ),
        SchemaOperation(
            operation_type=SchemaOperationType.ELEMENT_REMOVE,
            kind="TestCar",
            section=SchemaOperationSection.ATTRIBUTES,
            element_name="color",
        ),
        SchemaOperation(
            operation_type=SchemaOperationType.NODE_PROPERTY,
            kind="TestCar",
            property_name="generate_profile",
            value=False,
            previous_value=True,
        ),
    ]
    repository = build_schema_change_repository(db=db)
    at = Timestamp()

    created = await repository.create_schema_change(
        branch=BRANCH_NAME, operations=operations, at=at, user_id=SYSTEM_USER_ID
    )
    await repository.create_migration_records(application_id=created.application_id, migrations=[attribute_migration()])
    await repository.mark_applied(
        schema_change_id=created.schema_change_id,
        application_id=created.application_id,
        version=2,
        parent_id=parent_id,
        applied_at=at,
        user_id=SYSTEM_USER_ID,
    )

    reader = build_schema_change_history_reader(db=db)
    pages = await reader.list_operations(schema_change_ids=[created.schema_change_id], limit=10, offset=0)
    page = pages[created.schema_change_id]
    assert page.count == 3
    assert [(stored.position, stored.operation) for stored in page.operations] == [
        (0, operations[0]),
        (1, operations[1]),
        (2, operations[2]),
    ]
    assert await _read_edges_of_schema_change(db=db, schema_change_id=created.schema_change_id) == sorted(
        [
            (SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_OPERATION.value, "SchemaChangeOperation", "0"),
            (SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_OPERATION.value, "SchemaChangeOperation", "1"),
            (SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_OPERATION.value, "SchemaChangeOperation", "2"),
            (
                SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_APPLICATION.value,
                "SchemaChangeApplication",
                created.application_id,
            ),
            (SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_PARENT.value, "SchemaChange", parent_id),
        ]
    )
    applications = await reader.list_applications(schema_change_ids=[created.schema_change_id])
    assert [str(record.application.uuid) for record in applications[created.schema_change_id]] == [
        created.application_id
    ]
    assert [migration.position for migration in applications[created.schema_change_id][0].migrations] == [0]


async def test_edges_between_records_have_no_branch_property_and_no_record_is_linked_to_the_root(
    db: InfrahubDatabase, empty_database: None
) -> None:
    await seed_schema_change_history(
        db=db,
        branches=[
            BranchHistorySeed(
                branch=BRANCH_NAME,
                changes=[SchemaChangeStatus.APPLIED, SchemaChangeStatus.APPLIED],
                nbr_operations=2,
                migrations=[MigrationSeed(migration=attribute_migration())],
            )
        ],
    )

    edges = await _read_record_edges(db=db)

    assert [(edge_type, source, destination) for edge_type, source, destination, _ in edges] == sorted(
        [
            (SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_OPERATION.value, "SchemaChange", "SchemaChangeOperation"),
            (SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_OPERATION.value, "SchemaChange", "SchemaChangeOperation"),
            (SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_OPERATION.value, "SchemaChange", "SchemaChangeOperation"),
            (SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_OPERATION.value, "SchemaChange", "SchemaChangeOperation"),
            (SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_APPLICATION.value, "SchemaChange", "SchemaChangeApplication"),
            (SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_APPLICATION.value, "SchemaChange", "SchemaChangeApplication"),
            (SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_PARENT.value, "SchemaChange", "SchemaChange"),
            (
                SchemaChangeEdgeType.SCHEMA_APPLICATION_HAS_MIGRATION.value,
                "SchemaChangeApplication",
                "SchemaChangeMigration",
            ),
            (
                SchemaChangeEdgeType.SCHEMA_APPLICATION_HAS_MIGRATION.value,
                "SchemaChangeApplication",
                "SchemaChangeMigration",
            ),
        ]
    )
    assert [
        (edge_type, sorted(EDGE_PROPERTIES_OF_BRANCH_AWARE_GRAPH.intersection(keys)))
        for edge_type, _, _, keys in edges
        if EDGE_PROPERTIES_OF_BRANCH_AWARE_GRAPH.intersection(keys)
    ] == []
    assert await count_schema_change_record_edges_to_root(db=db) == 0


async def _read_stored_properties(db: InfrahubDatabase, schema_change_id: str) -> dict[str, dict[str, object]]:
    """Return the properties of a schema change and of each record under it, without the uuid and the timestamps."""
    results = await db.execute_query(
        query="""
        MATCH (schema_change:SchemaChange {uuid: $schema_change_id})
        MATCH (schema_change)-[:SCHEMA_CHANGE_HAS_OPERATION]->(operation:SchemaChangeOperation)
        MATCH (schema_change)-[:SCHEMA_CHANGE_HAS_APPLICATION]->(application:SchemaChangeApplication)
        MATCH (application)-[:SCHEMA_APPLICATION_HAS_MIGRATION]->(migration:SchemaChangeMigration)
        RETURN properties(schema_change) AS schema_change, properties(operation) AS operation,
            properties(application) AS application, properties(migration) AS migration
        """,
        params={"schema_change_id": schema_change_id},
        name="test_schema_change_stored_properties",
    )
    (result,) = results
    ignored = {"uuid", "created_at", "updated_at", "at"}
    return {
        record: {key: value for key, value in dict(result.get(record)).items() if key not in ignored}
        for record in ("schema_change", "operation", "application", "migration")
    }


async def test_fields_that_are_not_set_are_missing_properties_and_the_text_null_is_kept(
    db: InfrahubDatabase, empty_database: None
) -> None:
    operation = SchemaOperation(
        operation_type=SchemaOperationType.ELEMENT_PROPERTY,
        kind="TestCar",
        section=SchemaOperationSection.ATTRIBUTES,
        element_name="NULL",
        property_name="description",
        value="NULL",
    )
    repository = build_schema_change_repository(db=db)
    created = await repository.create_schema_change(
        branch=BRANCH_NAME, operations=[operation], at=Timestamp(), user_id=SYSTEM_USER_ID
    )
    await repository.create_migration_records(
        application_id=created.application_id,
        migrations=[attribute_migration(migration_name="node.attribute.add", field_name="color")],
    )

    assert await _read_stored_properties(db=db, schema_change_id=created.schema_change_id) == {
        "schema_change": {
            "branch": BRANCH_NAME,
            "status": "running",
            "summary": "testcar_NULL_update",
            "format_version": 1,
            "created_by": SYSTEM_USER_ID,
            "updated_by": SYSTEM_USER_ID,
        },
        "operation": {
            "position": 0,
            "operation_type": "element_property",
            "kind": "TestCar",
            "section": "attributes",
            "element_name": "NULL",
            "property_name": "description",
            "value": '"NULL"',
            "created_by": SYSTEM_USER_ID,
        },
        "application": {
            "branch": BRANCH_NAME,
            "status": "running",
            "created_by": SYSTEM_USER_ID,
            "updated_by": SYSTEM_USER_ID,
        },
        "migration": {
            "position": 0,
            "migration_name": "node.attribute.add",
            "path_type": "attribute",
            "schema_kind": "TestCar",
            "field_name": "color",
            "status": "waiting",
            "errors": [],
        },
    }
    pages = await build_schema_change_history_reader(db=db).list_operations(
        schema_change_ids=[created.schema_change_id], limit=10, offset=0
    )
    assert [stored.operation for stored in pages[created.schema_change_id].operations] == [operation]


async def test_operation_values_keep_their_json_type_apart_from_a_value_not_set(
    db: InfrahubDatabase, empty_database: None
) -> None:
    def element_property(property_name: str, **values: object) -> SchemaOperation:
        return SchemaOperation.model_validate(
            {
                "operation_type": SchemaOperationType.ELEMENT_PROPERTY,
                "kind": "TestCar",
                "section": SchemaOperationSection.ATTRIBUTES,
                "element_name": "color",
                "property_name": property_name,
                **values,
            }
        )

    operations = [
        element_property("choices", value=["red", "blue"], previous_value=[]),
        element_property("parameters", value={"regex": "^[a-z]+$", "max_length": 10}, previous_value={}),
        element_property("optional", value=True, previous_value=False),
        element_property("label", value=None, previous_value="Color"),
        element_property("description", value="NULL", previous_value=None),
        element_property("order_weight"),
    ]
    repository = build_schema_change_repository(db=db)
    created = await repository.create_schema_change(
        branch=BRANCH_NAME, operations=operations, at=Timestamp(), user_id=SYSTEM_USER_ID
    )

    reader = build_schema_change_history_reader(db=db)
    pages = await reader.list_operations(schema_change_ids=[created.schema_change_id], limit=10, offset=0)

    assert [
        (
            stored.operation.property_name,
            stored.operation.has_value,
            stored.operation.value,
            stored.operation.has_previous_value,
            stored.operation.previous_value,
        )
        for stored in pages[created.schema_change_id].operations
    ] == [
        ("choices", True, ["red", "blue"], True, []),
        ("parameters", True, {"regex": "^[a-z]+$", "max_length": 10}, True, {}),
        ("optional", True, True, True, False),
        ("label", True, None, True, "Color"),
        ("description", True, "NULL", True, None),
        ("order_weight", False, None, False, None),
    ]


async def test_create_migration_records_stores_one_waiting_record_for_each_migration_in_order(
    db: InfrahubDatabase, empty_database: None
) -> None:
    history = await seed_schema_change_history(
        db=db, branches=[BranchHistorySeed(branch=BRANCH_NAME, changes=[SchemaChangeStatus.RUNNING])]
    )
    schema_change = history.schema_changes[0]
    migrations = [
        attribute_migration(migration_name="node.attribute.add", field_name="color"),
        attribute_migration(migration_name="attribute.kind.update", field_name="name"),
        attribute_migration(migration_name="node.attribute.add", field_name="color"),
    ]
    repository = build_schema_change_repository(db=db)

    await repository.create_migration_records(application_id=schema_change.application_id, migrations=migrations)

    reader = build_schema_change_history_reader(db=db)
    applications = await reader.list_applications(schema_change_ids=[schema_change.id])
    assert [
        (
            migration.position,
            migration.migration_name,
            migration.schema_kind,
            migration.field_name,
            migration.status,
            migration.nbr_migrations_executed,
            list(migration.errors),
        )
        for migration in applications[schema_change.id][0].migrations
    ] == [
        (0, "node.attribute.add", "TestCar", "color", SchemaChangeMigrationStatus.WAITING, None, []),
        (1, "attribute.kind.update", "TestCar", "name", SchemaChangeMigrationStatus.WAITING, None, []),
        (2, "node.attribute.add", "TestCar", "color", SchemaChangeMigrationStatus.WAITING, None, []),
    ]


async def test_set_migration_records_status_changes_only_the_records_named(
    db: InfrahubDatabase, empty_database: None
) -> None:
    history = await seed_schema_change_history(
        db=db,
        branches=[
            BranchHistorySeed(
                branch=BRANCH_NAME,
                changes=[SchemaChangeStatus.RUNNING],
                migrations=[
                    MigrationSeed(migration=attribute_migration()),
                    MigrationSeed(migration=attribute_migration()),
                    MigrationSeed(migration=attribute_migration()),
                ],
            )
        ],
    )
    schema_change = history.schema_changes[0]
    repository = build_schema_change_repository(db=db)

    await repository.set_migration_records_status(
        application_id=schema_change.application_id,
        positions=[0, 2],
        status=SchemaChangeMigrationStatus.FAILED,
        nbr_migrations_executed=3,
        errors=["first error", "second error"],
    )

    reader = build_schema_change_history_reader(db=db)
    applications = await reader.list_applications(schema_change_ids=[schema_change.id])
    assert [
        (migration.position, migration.status, migration.nbr_migrations_executed, list(migration.errors))
        for migration in applications[schema_change.id][0].migrations
    ] == [
        (0, SchemaChangeMigrationStatus.FAILED, 3, ["first error", "second error"]),
        (1, SchemaChangeMigrationStatus.WAITING, None, []),
        (2, SchemaChangeMigrationStatus.FAILED, 3, ["first error", "second error"]),
    ]
