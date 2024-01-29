from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict
from uuid import UUID

from graphene import Boolean, Enum, Field, InputObjectType, Mutation, ObjectType, String
from graphene.types.uuid import UUID as GrapheneUUID
from infrahub_sdk.utils import extract_fields_first_node

from infrahub.core.constants import TaskConclusion as PyTaskConclusion
from infrahub.core.manager import NodeManager
from infrahub.core.task import Task
from infrahub.exceptions import NodeNotFound

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.database import InfrahubDatabase

TaskConclusion = Enum.from_enum(PyTaskConclusion)


class TaskCreateInput(InputObjectType):
    id = GrapheneUUID(required=False)
    title = String(required=True)
    created_by = String(required=False)
    conclusion = TaskConclusion(required=True)
    related_node = String(required=False)


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
    async def mutate(
        cls,
        root: dict,  # pylint: disable=unused-argument
        info: GraphQLResolveInfo,
        data: TaskCreateInput,
    ) -> TaskCreate:
        branch = info.context.get("infrahub_branch")
        db: InfrahubDatabase = info.context.get("infrahub_database")

        account_id = str(data.created_by) if data.created_by else None

        related_node = None
        if data.related_node:
            if not (related_node := await NodeManager.get_one(db=db, id=str(data.related_node), branch=branch)):
                raise NodeNotFound(
                    node_type="related_node",
                    identifier=str(data.related_node),
                    message="The indicated related node was not found in the database",
                )
        fields = await extract_fields_first_node(info)
        task_id = None
        if data.id:
            task_id = UUID(str(data.id))
        async with db.start_transaction() as db:
            task = Task(
                uuid=task_id,
                title=str(data.title),
                account_id=account_id,
                conclusion=data.conclusion,
                related_node=related_node,
            )
            await task.save(db=db)

        result: Dict[str, Any] = {"ok": True}

        if "object" in fields:
            result["object"] = await task.to_graphql(fields=fields["object"])

        return cls(**result)
