import asyncio
from copy import deepcopy

from infrahub.core.constants import SchemaPathType
from infrahub.core.migrations.schema.models import SchemaApplyMigrationData, SchemaMigrationPathResponseData
from infrahub.core.models import SchemaUpdateMigrationInfo
from infrahub.core.path import SchemaPath
from infrahub.core.schema import GenericSchema, MainSchemaTypes
from infrahub.core.schema.schema_branch import SchemaBranch
from tests.helpers.schema.car import CAR
from tests.helpers.schema.device import INTERFACE, PHYSICAL_INTERFACE, VIRTUAL_INTERFACE
from tests.helpers.schema.manufacturer import MANUFACTURER
from tests.helpers.schema.person import PERSON

CAR_KINDS = frozenset({"TestingCar", "ProfileTestingCar", "TemplateTestingCar"})
PERSON_KINDS = frozenset({"TestingPerson", "ProfileTestingPerson", "TemplateTestingPerson"})
MANUFACTURER_KINDS = frozenset({"TestingManufacturer", "ProfileTestingManufacturer", "TemplateTestingManufacturer"})
INTERFACE_KINDS = frozenset(
    {
        "TestingInterface",
        "ProfileTestingInterface",
        "TemplateTestingInterface",
        "TestingPhysicalInterface",
        "ProfileTestingPhysicalInterface",
        "TemplateTestingPhysicalInterface",
        "TestingVirtualInterface",
        "ProfileTestingVirtualInterface",
        "TemplateTestingVirtualInterface",
    }
)


def path_migration(
    migration_name: str,
    schema_kind: str,
    path_type: SchemaPathType = SchemaPathType.ATTRIBUTE,
    field_name: str | None = None,
    property_name: str | None = None,
) -> SchemaUpdateMigrationInfo:
    return SchemaUpdateMigrationInfo(
        migration_name=migration_name,
        path=SchemaPath(
            path_type=path_type, schema_kind=schema_kind, field_name=field_name, property_name=property_name
        ),
    )


def interface_used_by(used_by: list[str]) -> GenericSchema:
    interface = deepcopy(INTERFACE)
    interface.used_by = used_by
    return interface


def schema_branch(*schemas: MainSchemaTypes) -> SchemaBranch:
    branch = SchemaBranch(cache={}, name="test")
    for schema in schemas:
        branch.set(name=schema.kind, schema=deepcopy(schema))
    return branch


def full_schema_branch() -> SchemaBranch:
    """Cars with their peers, and the interface generic used by the physical and the virtual interfaces."""
    return schema_branch(
        CAR,
        PERSON,
        MANUFACTURER,
        interface_used_by(used_by=["TestingPhysicalInterface", "TestingVirtualInterface"]),
        PHYSICAL_INTERFACE,
        VIRTUAL_INTERFACE,
    )


START = "start"
END = "end"


class RecordingMigrator:
    """Record when each migration starts and ends, yielding to other tasks in between."""

    def __init__(self, errors_by_field: dict[str, list[str]]) -> None:
        self.errors_by_field = errors_by_field
        self.events: list[tuple[str, str, str | None]] = []

    async def migrate(
        self, migration: SchemaUpdateMigrationInfo, data: SchemaApplyMigrationData
    ) -> SchemaMigrationPathResponseData:
        path = migration.path
        self.events.append((START, path.schema_kind, path.field_name))
        await asyncio.sleep(0)
        self.events.append((END, path.schema_kind, path.field_name))
        return SchemaMigrationPathResponseData(
            migration_name=migration.migration_name,
            schema_path=path,
            errors=self.errors_by_field.get(path.field_name or "", []),
            nbr_migrations_executed=1,
        )


class FailingMigrator(RecordingMigrator):
    """Raise while a migration of one of the given fields runs, after yielding to other tasks once."""

    def __init__(self, failing_fields: set[str]) -> None:
        super().__init__(errors_by_field={})
        self.failing_fields = failing_fields

    async def migrate(
        self, migration: SchemaUpdateMigrationInfo, data: SchemaApplyMigrationData
    ) -> SchemaMigrationPathResponseData:
        path = migration.path
        if path.field_name in self.failing_fields:
            self.events.append((START, path.schema_kind, path.field_name))
            await asyncio.sleep(0)
            raise RuntimeError(f"migration failed: {path.field_name}")
        return await super().migrate(migration=migration, data=data)


AUTO_KINDS = frozenset({"TestingAuto", "ProfileTestingAuto", "TemplateTestingAuto"})


def renamed_car_schema_branches() -> tuple[SchemaBranch, SchemaBranch]:
    """Return a previous and a new schema in which `TestingCar` is renamed `TestingAuto`, and both sides of its owner relationship are removed."""
    car = deepcopy(CAR)
    car.id = "car-id"
    person = deepcopy(PERSON)
    person.id = "person-id"
    auto = deepcopy(car)
    auto.name = "Auto"
    auto.relationships = [relationship for relationship in auto.relationships if relationship.name != "owner"]
    person_without_cars = deepcopy(person)
    person_without_cars.relationships = [
        relationship for relationship in person_without_cars.relationships if relationship.name != "cars"
    ]
    return schema_branch(car, person, MANUFACTURER), schema_branch(auto, person_without_cars, MANUFACTURER)
