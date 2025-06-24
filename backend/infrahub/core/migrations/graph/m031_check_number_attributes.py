from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from infrahub import config
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.initialization import initialization
from infrahub.core.migrations.shared import InternalSchemaMigration, MigrationResult, SchemaMigration
from infrahub.core.path import SchemaPath
from infrahub.core.schema import GenericSchema, NodeSchema
from infrahub.core.schema.attribute_parameters import NumberAttributeParameters
from infrahub.core.validators.attribute.min_max import AttributeNumberChecker
from infrahub.core.validators.enum import ConstraintIdentifier
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.lock import initialize_lock
from infrahub.log import get_logger
from infrahub.types import Number

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()


class Migration031(InternalSchemaMigration):
    """
    Some nodes with invalid number attributes may have been created as min/max/excluded_values were not working properly.
    This migration indicates corrupted nodes. If strict mode is disabled, both this migration and min/max/excludes_values constraints are disabled,
    so that users can carry one with their corrupted data without any failure.
    """

    name: str = "031_check_number_attributes"
    minimum_version: int = 30
    migrations: Sequence[SchemaMigration] = []

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        """Retrieve all number attributes that have a min/max/excluded_values
        For any of these attributes, check if corresponding existing nodes are valid."""

        if not config.SETTINGS.main.schema_strict_mode:
            return MigrationResult()

        # load schemas from database into registry
        initialize_lock()
        await initialization(db=db)

        node_id_to_error_message = {}

        branches = await Branch.get_list(db=db)
        for branch in branches:  # noqa
            schema_branch = await registry.schema.load_schema_from_db(db=db, branch=branch)
            for node_schema_kind in schema_branch.node_names:
                schema = schema_branch.get_node(name=node_schema_kind, duplicate=False)
                if not isinstance(schema, (NodeSchema, GenericSchema)):
                    continue

                for attr in schema.attributes:
                    if attr.kind != Number.label:
                        continue

                    # Check if the attribute has a min/max/excluded_values being violated
                    if isinstance(attr.parameters, NumberAttributeParameters) and (
                        attr.parameters.min_value is not None
                        or attr.parameters.max_value is not None
                        or attr.parameters.excluded_values
                    ):
                        request = SchemaConstraintValidatorRequest(
                            branch=branch,
                            constraint_name=ConstraintIdentifier.ATTRIBUTE_PARAMETERS_MIN_VALUE_UPDATE.value,
                            node_schema=schema,
                            schema_path=SchemaPath(
                                path_type=SchemaPathType.ATTRIBUTE, schema_kind=schema.kind, field_name=attr.name
                            ),
                            schema_branch=db.schema.get_schema_branch(name=registry.default_branch),
                        )

                        constraint_checker = AttributeNumberChecker(db=db, branch=branch)
                        grouped_data_paths = await constraint_checker.check(request)
                        data_paths = grouped_data_paths[0].get_all_data_paths()
                        for data_path in data_paths:
                            # Avoid having duplicated error messages for nodes present on multiple branches.
                            if data_path.node_id not in node_id_to_error_message:
                                node_id_to_error_message[data_path.node_id] = (
                                    f"Node {data_path.node_id} on branch {branch.name} "
                                    f"has an invalid Number attribute {data_path.field_name}: {data_path.value}"
                                )

        if len(node_id_to_error_message) == 0:
            return MigrationResult()

        error_str = (
            "Following nodes attributes values must be updated to not violate corresponding min_value, "
            "max_value or excluded_values schema constraints"
        )
        errors_messages = list(node_id_to_error_message.values())
        return MigrationResult(errors=[error_str] + errors_messages)

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        result = MigrationResult()
        return result
