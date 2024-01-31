from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from graphene import Boolean, Enum, Field, InputObjectType, Mutation, ObjectType, String
from graphene.types.uuid import UUID as GrapheneUUID
from infrahub_sdk.utils import extract_fields_first_node

from infrahub.core.constants import Severity as PySeverity
from infrahub.core.task_log import TaskLog

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.database import InfrahubDatabase

Severity = Enum.from_enum(PySeverity)


class LogCreateInput(InputObjectType):
    message = String(required=True)
    severity = Severity(required=True)
    task_id = GrapheneUUID(required=True)


class LogFields(ObjectType):
    id = Field(String)


class TaskLogCreate(Mutation):
    class Arguments:
        data = LogCreateInput(required=True)

    ok = Boolean()
    object = Field(LogFields)

    @classmethod
    async def mutate(
        cls,
        root: dict,  # pylint: disable=unused-argument
        info: GraphQLResolveInfo,
        data: LogCreateInput,
    ) -> TaskLogCreate:
        db: InfrahubDatabase = info.context.get("infrahub_database")

        fields = await extract_fields_first_node(info)

        async with db.start_transaction() as db:
            log = TaskLog(task_id=str(data.task_id), message=str(data.message), severity=data.severity)
            await log.save(db=db)

        result: Dict[str, Any] = {"ok": True}

        if "object" in fields:
            result["object"] = await log.to_graphql(fields=fields["object"])

        return cls(**result)
