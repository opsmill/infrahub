from copy import deepcopy

from infrahub.core.constants import SchemaPathType
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
