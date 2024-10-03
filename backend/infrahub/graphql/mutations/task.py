from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from graphene import Boolean, Enum, Field, InputObjectType, List, Mutation, ObjectType, String
from graphene.types.uuid import UUID
from infrahub_sdk.utils import extract_fields_first_node

from infrahub.core.constants import TaskConclusion as PyTaskConclusion
from infrahub.core.manager import NodeManager
from infrahub.core.task import Task, TaskLog
from infrahub.core.timestamp import current_timestamp
from infrahub.database import retry_db_transaction
from infrahub.exceptions import NodeNotFoundError
from infrahub.graphql.types.task_log import RelatedTaskLogCreateInput

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext

TaskConclusion = Enum.from_enum(PyTaskConclusion)


class TaskCreateInput(InputObjectType):
    id = UUID(required=False)
    title = String(required=True)
    created_by = String(required=False)
    conclusion = TaskConclusion(required=True)
    related_node = String(required=False)
    logs = List(RelatedTaskLogCreateInput, required=False)


class TaskUpdateInput(InputObjectType):
    id = UUID(required=True)
    title = String(required=False)
    conclusion = TaskConclusion(required=False)
    logs = List(RelatedTaskLogCreateInput, required=False)


class TaskFields(ObjectType):
    id = Field(String)
    title = Field(String)
    conclusion = Field(TaskConclusion)


class TaskCreate(Mutation):
    class Arguments:
        data = TaskCreateInput(required=True)

    ok = Boolean()
    object = Field(TaskFields)

    @classmethod
    @retry_db_transaction(name="task_create")
    async def mutate(
        cls,
        root: dict,  # pylint: disable=unused-argument
        info: GraphQLResolveInfo,
        data: TaskCreateInput,
    ) -> TaskCreate:
        context: GraphqlContext = info.context

        account_id = str(data.created_by) if data.created_by else None

        if not (
            related_node := await NodeManager.get_one(db=context.db, id=str(data.related_node), branch=context.branch)
        ):
            raise NodeNotFoundError(
                node_type="related_node",
                identifier=str(data.related_node),
                message="The indicated related node was not found in the database",
            )
        fields = await extract_fields_first_node(info)
        task_id = uuid.uuid4()

        if data.id:
            task_id = uuid.UUID(str(data.id))

        async with context.db.start_transaction() as db:
            task = Task(
                uuid=task_id,
                title=str(data.title),
                account_id=account_id,
                conclusion=data.conclusion,
                related_node=related_node,
            )
            await task.save(db=db)
            if data.logs:
                for log in data.logs:
                    task_log = TaskLog(message=str(log.message), severity=log.severity, task_id=str(task_id))
                    await task_log.save(db=db)

        result: dict[str, Any] = {"ok": True}

        if "object" in fields:
            result["object"] = await task.to_graphql(fields=fields["object"])

        return cls(**result)


class TaskUpdate(Mutation):
    class Arguments:
        data = TaskUpdateInput(required=True)

    ok = Boolean()
    object = Field(TaskFields)

    @classmethod
    @retry_db_transaction(name="task_update")
    async def mutate(
        cls,
        root: dict,  # pylint: disable=unused-argument
        info: GraphQLResolveInfo,
        data: TaskUpdateInput,
    ) -> TaskUpdate:
        context: GraphqlContext = info.context
        task_id = str(data.id)
        task = await Task.get(id=task_id, db=context.db)

        fields = await extract_fields_first_node(info)

        if not task:
            raise NodeNotFoundError(node_type="Task", identifier=task_id, message="The requested Task was not found")

        if data.title:
            task.title = str(data.title)

        if data.conclusion:
            task.conclusion = data.conclusion

        task.updated_at = current_timestamp()
        async with context.db.start_transaction() as db:
            await task.save(db=db)

            if data.logs:
                for log in data.logs:
                    task_log = TaskLog(message=str(log.message), severity=log.severity, task_id=task_id)
                    await task_log.save(db=db)

        result: dict[str, Any] = {"ok": True}

        if "object" in fields:
            result["object"] = await task.to_graphql(fields=fields["object"])

        return cls(**result)
