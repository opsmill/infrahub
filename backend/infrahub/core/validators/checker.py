from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, List

from infrahub.message_bus.messages import MESSAGE_MAP, RESPONSE_MAP, InfrahubResponse

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema_manager import SchemaBranch, SchemaUpdateConstraintInfo
    from infrahub.services import InfrahubServices


async def schema_validators_checker(
    branch: Branch, schema: SchemaBranch, constraints: List[SchemaUpdateConstraintInfo], service: InfrahubServices
) -> List[str]:
    tasks = []
    error_messages: List[str] = []

    if not constraints:
        return error_messages

    for constraint in constraints:
        service.log.info(
            f"Preparing validator for constraint {constraint.constraint_name!r} ({constraint.routing_key})",
            branch=branch.name,
            constraint_name=constraint.constraint_name,
            routing_key=constraint.routing_key,
        )
        message_class = MESSAGE_MAP.get(constraint.routing_key, None)
        response_class = RESPONSE_MAP.get(constraint.routing_key, None)

        if not message_class:
            raise ValueError(
                f"Unable to find the message for {constraint.constraint_name!r} ({constraint.routing_key})"
            )
        if not response_class:
            raise ValueError(
                f"Unable to find the response for {constraint.constraint_name!r} ({constraint.routing_key})"
            )

        message = message_class(  # type: ignore[call-arg]
            branch=branch,
            constraint_name=constraint.constraint_name,
            node_schema=schema.get(name=constraint.path.schema_kind),
            schema_path=constraint.path,
        )
        tasks.append(service.message_bus.rpc(message=message, response_class=response_class))

    if not tasks:
        return error_messages

    responses: list[InfrahubResponse] = await asyncio.gather(*tasks)

    for response in responses:
        if not response.passed:
            if response.initial_message:
                error_messages.append(
                    f"Unable to execute the validator for {response.initial_message.get('constraint_name')!r}: "
                    + ", ".join(response.errors)
                )
            else:
                error_messages.append("Unknown error while executing the validators:" + ", ".join(response.errors))
            continue

        for violation in response.data.violations:  # type: ignore[union-attr]
            error_messages.append(violation.message)

    return error_messages
