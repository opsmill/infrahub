from __future__ import annotations

from infrahub_sdk.batch import InfrahubBatch
from prefect import flow

from infrahub.message_bus.messages.schema_validator_path import (
    SchemaValidatorPathData,
)
from infrahub.message_bus.operations.schema.validator import schema_path_validate
from infrahub.services import services

from .models.validate_migration import SchemaValidateMigrationData  # noqa: TCH001


@flow
async def schema_validate_migrations(message: SchemaValidateMigrationData) -> list[str]:
    batch = InfrahubBatch(return_exceptions=True)
    error_messages: list[str] = []
    service = services.service

    if not message.constraints:
        return error_messages

    for constraint in message.constraints:
        service.log.info(
            f"Preparing validator for constraint {constraint.constraint_name!r} ({constraint.routing_key})",
            branch=message.branch.name,
            constraint_name=constraint.constraint_name,
            routing_key=constraint.routing_key,
        )

        msg = SchemaValidatorPathData(
            branch=message.branch,
            constraint_name=constraint.constraint_name,
            node_schema=message.schema_branch.get(name=constraint.path.schema_kind),
            schema_path=constraint.path,
        )
        batch.add(task=schema_path_validate, message=msg)

    async for _, result in batch.execute():
        for violation in result.violations:
            error_messages.append(violation.message)

    return error_messages
