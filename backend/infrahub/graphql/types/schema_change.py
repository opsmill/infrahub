from __future__ import annotations

from graphene import ID, DateTime, Enum, Field, Int, List, NonNull, ObjectType, String
from graphene.types.generic import GenericScalar

from infrahub.core.constants import SchemaPathType as SchemaPathTypeEnum
from infrahub.core.schema_change.constants import (
    SCHEMA_CHANGE_APPLICATIONS_DEFAULT_LIMIT,
    SCHEMA_CHANGE_APPLICATIONS_MAX_LIMIT,
    SCHEMA_CHANGE_MIGRATIONS_DEFAULT_LIMIT,
    SCHEMA_CHANGE_MIGRATIONS_MAX_LIMIT,
    SCHEMA_CHANGE_OPERATIONS_DEFAULT_LIMIT,
    SCHEMA_CHANGE_OPERATIONS_MAX_LIMIT,
)
from infrahub.core.schema_change.enums import SchemaChangeApplicationStatus as SchemaChangeApplicationStatusEnum
from infrahub.core.schema_change.enums import SchemaChangeMigrationStatus as SchemaChangeMigrationStatusEnum
from infrahub.core.schema_change.enums import SchemaChangeSource as SchemaChangeSourceEnum
from infrahub.core.schema_change.enums import SchemaChangeStatus as SchemaChangeStatusEnum
from infrahub.core.schema_change.enums import SchemaOperationNodeType as SchemaOperationNodeTypeEnum
from infrahub.core.schema_change.enums import SchemaOperationSection as SchemaOperationSectionEnum
from infrahub.core.schema_change.enums import SchemaOperationType as SchemaOperationTypeEnum
from infrahub.graphql.resolvers.schema_change import (
    schema_change_applications_resolver,
    schema_change_migrations_resolver,
    schema_change_operations_resolver,
)

# Keep each description a single line: graphql-core's SDL printer dedents multi-line descriptions
# differently across versions, which makes the generated schema.graphql environment-dependent.
SchemaChangeStatus = Enum.from_enum(
    SchemaChangeStatusEnum,
    description="Status of a schema change of a branch.",
)

SchemaChangeSource = Enum.from_enum(
    SchemaChangeSourceEnum,
    description="What made a schema change: a user's schema load or dropdown or enum change, or the core schema update of an upgrade.",
)

SchemaChangeApplicationStatus = Enum.from_enum(
    SchemaChangeApplicationStatusEnum,
    description="Status of one application of a schema change to a branch.",
)

SchemaChangeMigrationStatus = Enum.from_enum(
    SchemaChangeMigrationStatusEnum,
    description="Status of one migration that an application of a schema change runs on the data of its branch.",
)

SchemaOperationType = Enum.from_enum(
    SchemaOperationTypeEnum,
    description="Type of a schema operation: add, remove or change a property of a kind, or of an attribute or relationship.",
)

SchemaOperationNodeType = Enum.from_enum(
    SchemaOperationNodeTypeEnum,
    description="Whether a kind that a schema operation adds is a node or a generic.",
)

SchemaOperationSection = Enum.from_enum(
    SchemaOperationSectionEnum,
    description="Whether the element of a schema operation is an attribute or a relationship.",
)

SchemaPathType = Enum.from_enum(
    SchemaPathTypeEnum,
    description="Whether a schema path names a kind, an attribute or a relationship.",
)


class InfrahubSchemaChangeParent(ObjectType):
    """The applied schema change that a schema change follows."""

    id = ID(required=True)
    name = String(required=True)
    version = Int(required=True)
    branch = String(required=True)


class InfrahubSchemaChangeOperation(ObjectType):
    """One operation of a schema change; the operations apply in the order of `position`."""

    position = Int(required=True, description="Order in which the operation applies, from 0.")
    operation_type = Field(SchemaOperationType, required=True)
    kind = String(required=True)
    node_type = Field(SchemaOperationNodeType, required=False, description="Set for NODE_ADD.")
    section = Field(SchemaOperationSection, required=False, description="Set for the three ELEMENT types.")
    element_name = String(
        required=False,
        description=(
            "Name of the attribute or relationship. Set for the three ELEMENT types; "
            "for a rename, the name before the operation."
        ),
    )
    property_name = String(
        required=False, description="Name of the property, dotted when nested. Set for the two PROPERTY types."
    )
    value = GenericScalar(
        required=False,
        description=(
            "New value for a PROPERTY type, full definition for an ADD type. An added attribute or relationship "
            "also holds the order_weight that processing gave it when the file sets none."
        ),
    )
    previous_value = GenericScalar(
        required=False, description="Value before the change. Set for the two PROPERTY types."
    )


class InfrahubSchemaChangeOperationEdge(ObjectType):
    node = Field(InfrahubSchemaChangeOperation, required=True)


class InfrahubSchemaChangeOperations(ObjectType):
    """One page of the operations of a schema change."""

    count = Int(required=True, description="Number of operations of the schema change.")
    edges = List(of_type=NonNull(InfrahubSchemaChangeOperationEdge), required=True)


class InfrahubSchemaChangeMigration(ObjectType):
    """One migration that an application of a schema change runs on the data of its branch."""

    id = ID(required=True)
    position = Int(required=True, description="Order in the list of migrations of the application, from 0.")
    migration_name = String(required=True, description='For example "node.attribute.add".')
    path = String(
        required=True, description='Text form of the schema path, for example "schema/DcimCloudDevice/serial".'
    )
    path_type = Field(SchemaPathType, required=True)
    schema_kind = String(required=True)
    field_name = String(required=False)
    property_name = String(required=False)
    status = Field(SchemaChangeMigrationStatus, required=True)
    errors = List(of_type=NonNull(String), required=True)
    updated_at = DateTime(required=True, description="Time of the last status change.")


class InfrahubSchemaChangeMigrationEdge(ObjectType):
    node = Field(InfrahubSchemaChangeMigration, required=True)


class InfrahubSchemaChangeMigrations(ObjectType):
    """One page of the migration records of an application of a schema change, in the order of `position`."""

    count = Int(required=True, description="Number of migration records of the application.")
    edges = List(of_type=NonNull(InfrahubSchemaChangeMigrationEdge), required=True)


class InfrahubSchemaChangeApplication(ObjectType):
    """One time a schema change was applied to a branch."""

    id = ID(required=True)
    status = Field(SchemaChangeApplicationStatus, required=True)
    branch = String(required=True, description="Branch the schema change was applied to.")
    at = DateTime(required=True, description="Timestamp of the graph writes of this application.")
    error = String(required=False, description="Set when the status is FAILED.")
    created_at = DateTime(required=True)
    updated_at = DateTime(required=True)
    migrations = Field(
        InfrahubSchemaChangeMigrations,
        required=True,
        limit=Int(
            description=(
                f"Number of migration records to return. Default {SCHEMA_CHANGE_MIGRATIONS_DEFAULT_LIMIT}, "
                f"maximum {SCHEMA_CHANGE_MIGRATIONS_MAX_LIMIT}, minimum 1."
            )
        ),
        offset=Int(description="Number of migration records to skip. Minimum 0."),
        resolver=schema_change_migrations_resolver,
    )


class InfrahubSchemaChangeApplicationEdge(ObjectType):
    node = Field(InfrahubSchemaChangeApplication, required=True)


class InfrahubSchemaChangeApplications(ObjectType):
    """One page of the applications of a schema change, in the order of `at`."""

    count = Int(required=True, description="Number of applications of the schema change.")
    edges = List(of_type=NonNull(InfrahubSchemaChangeApplicationEdge), required=True)


class InfrahubSchemaChangeNode(ObjectType):
    """One change to the schema of a branch, made of one or more operations."""

    id = ID(required=True)
    name = String(
        required=True,
        description='"<version, five digits>_<summary>", or the summary when there is no version.',
    )
    summary = String(required=True)
    version = Int(required=False, description="Null unless the status is APPLIED.")
    status = Field(SchemaChangeStatus, required=True)
    source = Field(SchemaChangeSource, required=True)
    branch = String(required=True)
    created_at = DateTime(required=True)
    updated_at = DateTime(required=True, description="Time of the last change of the record.")
    applied_at = DateTime(
        required=False,
        description="Timestamp at which the schema was written to the branch. Null unless the status is APPLIED.",
    )
    parent = Field(
        InfrahubSchemaChangeParent,
        required=False,
        description=(
            "The applied schema change that this one follows. Null for the first schema change of main, for a "
            "branch's first schema change when main has none, and for a schema change without a version."
        ),
    )
    operations = Field(
        InfrahubSchemaChangeOperations,
        required=True,
        limit=Int(
            description=(
                f"Number of operations to return. Default {SCHEMA_CHANGE_OPERATIONS_DEFAULT_LIMIT}, "
                f"maximum {SCHEMA_CHANGE_OPERATIONS_MAX_LIMIT}, minimum 1."
            )
        ),
        offset=Int(description="Number of operations to skip. Minimum 0."),
        resolver=schema_change_operations_resolver,
    )
    applications = Field(
        InfrahubSchemaChangeApplications,
        required=True,
        limit=Int(
            description=(
                f"Number of applications to return. Default {SCHEMA_CHANGE_APPLICATIONS_DEFAULT_LIMIT}, "
                f"maximum {SCHEMA_CHANGE_APPLICATIONS_MAX_LIMIT}, minimum 1."
            )
        ),
        offset=Int(description="Number of applications to skip. Minimum 0."),
        resolver=schema_change_applications_resolver,
    )


class InfrahubSchemaChangeEdge(ObjectType):
    node = Field(InfrahubSchemaChangeNode, required=True)


class InfrahubSchemaChanges(ObjectType):
    """One page of the schema changes of a branch."""

    count = Int(required=True, description="Number of schema changes that match, on all pages.")
    edges = List(of_type=NonNull(InfrahubSchemaChangeEdge), required=True)
