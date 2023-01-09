from graphene import (
    Boolean,
    Field,
    InputObjectType,
    Int,
    List,
    Mutation,
    String,
)
from graphene.types.generic import GenericScalar
from graphene.types.mutation import MutationOptions

from neo4j import AsyncSession

import infrahub.config as config
from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.exceptions import BranchNotFound, NodeNotFound
from infrahub.message_bus.events import (
    send_event,
    InfrahubDataMessage,
    DataMessageAction,
    InfrahubBranchMessage,
    BranchMessageAction,
    InfrahubGitRPC,
    GitMessageAction,
)
from infrahub.message_bus.rpc import InfrahubRpcClient

from .query import BranchType
from .utils import extract_fields


# ------------------------------------------
# Infrahub GraphQLType
# ------------------------------------------
class InfrahubMutationOptions(MutationOptions):
    schema = None


class InfrahubMutationMixin:
    @classmethod
    async def mutate(cls, root, info, *args, **kwargs):

        at = info.context.get("infrahub_at")
        branch = info.context.get("infrahub_branch")
        # account = info.context.get("infrahub_account", None)

        action = None
        if "Create" in cls.__name__:
            obj, mutation = await cls.mutate_create(root, info, branch=branch, at=at, *args, **kwargs)
            action = DataMessageAction.CREATE
        elif "Update" in cls.__name__:
            obj, mutation = await cls.mutate_update(root, info, branch=branch, at=at, *args, **kwargs)
            action = DataMessageAction.UPDATE
        elif "Delete" in cls.__name__:
            obj, mutation = await cls.mutate_delete(root, info, branch=branch, at=at, *args, **kwargs)
            action = DataMessageAction.DELETE

        if config.SETTINGS.broker.enable and info.context.get("background"):
            info.context.get("background").add_task(send_event, InfrahubDataMessage(action=action, node=obj))

        return mutation

    @classmethod
    async def mutate_create(cls, root, info, data, branch=None, at=None):

        session: AsyncSession = info.context.get("infrahub_session")

        obj = await Node.init(session=session, schema=cls._meta.schema, branch=branch, at=at)
        await obj.new(session=session, **data)
        await obj.save(session=session)

        fields = await extract_fields(info.field_nodes[0].selection_set)
        ok = True

        return obj, cls(object=await obj.to_graphql(session=session, fields=fields.get("object", {})), ok=ok)

    @classmethod
    async def mutate_update(cls, root, info, data, branch=None, at=None):

        session: AsyncSession = info.context.get("infrahub_session")

        if not (obj := await NodeManager.get_one(session=session, id=data.get("id"), branch=branch, at=at)):
            raise NodeNotFound(branch, cls._meta.schema.kind, data.get("id"))

        await obj.from_graphql(session=session, data=data)
        await obj.save(session=session)

        ok = True

        fields = await extract_fields(info.field_nodes[0].selection_set)

        return obj, cls(object=await obj.to_graphql(session=session, fields=fields.get("object", {})), ok=ok)

    @classmethod
    async def mutate_delete(cls, root, info, data, branch=None, at=None):

        session: AsyncSession = info.context.get("infrahub_session")

        if not (obj := await NodeManager.get_one(session=session, id=data.get("id"), branch=branch, at=at)):
            raise NodeNotFound(branch, cls._meta.schema.kind, data.get("id"))

        await obj.delete(session=session)
        ok = True

        return obj, cls(ok=ok)


class InfrahubMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(cls, schema: NodeSchema = None, _meta=None, **options):

        # Make sure schema is a valid NodeSchema Node Class
        if not isinstance(schema, NodeSchema):
            raise ValueError(f"You need to pass a valid NodeSchema in '{cls.__name__}.Meta', received '{schema}'")

        if not _meta:
            _meta = InfrahubMutationOptions(cls)

        _meta.schema = schema

        super().__init_subclass_with_meta__(_meta=_meta, **options)


class InfrahubRepositoryMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(cls, schema: NodeSchema = None, _meta=None, **options):

        # Make sure schema is a valid NodeSchema Node Class
        if not isinstance(schema, NodeSchema):
            raise ValueError(f"You need to pass a valid NodeSchema in '{cls.__name__}.Meta', received '{schema}'")

        if not _meta:
            _meta = InfrahubMutationOptions(cls)

        _meta.schema = schema

        super().__init_subclass_with_meta__(_meta=_meta, **options)

    @classmethod
    async def mutate_create(cls, root, info, data, branch=None, at=None):

        session: AsyncSession = info.context.get("infrahub_session")
        rpc_client: InfrahubRpcClient = info.context.get("infrahub_rpc_client")

        # Create the new repository in the database.
        obj = await Node.init(session=session, schema=cls._meta.schema, branch=branch, at=at)
        await obj.new(session=session, **data)
        await obj.save(session=session)

        fields = await extract_fields(info.field_nodes[0].selection_set)

        # Create the new repository in the filesystem.
        resp = await rpc_client.call(InfrahubGitRPC(action=GitMessageAction.REPO_ADD, repository=obj))

        # TODO Validate that the creation of the repository went as expected
        ok = True

        return obj, cls(object=await obj.to_graphql(session=session, fields=fields.get("object", {})), ok=ok)


# --------------------------------------------------------------------------------


class BaseAttributeInput(InputObjectType):
    is_visible = Boolean(required=False)
    is_protected = Boolean(required=False)
    source = String(required=False)
    owner = String(required=False)


class StringAttributeInput(BaseAttributeInput):
    value = String(required=False)


class IntAttributeInput(BaseAttributeInput):
    value = Int(required=False)


class BoolAttributeInput(BaseAttributeInput):
    value = Boolean(required=False)


class AnyAttributeInput(BaseAttributeInput):
    value = GenericScalar(required=False)


# --------------------------------------------------
# Mutations Specific to Branch
# --------------------------------------------------
class BranchCreateInput(InputObjectType):
    id = String(required=False)
    name = String(required=True)
    description = String(required=False)
    origin_branch = String(required=False)
    branched_from = String(required=False)
    is_data_only = Boolean(required=False)


class BranchCreate(Mutation):
    class Arguments:
        data = BranchCreateInput(required=True)
        background_execution = Boolean(required=False)

    ok = Boolean()
    object = Field(BranchType)

    @classmethod
    async def mutate(cls, root, info, data, background_execution=False):

        session: AsyncSession = info.context.get("infrahub_session")
        rpc_client: InfrahubRpcClient = info.context.get("infrahub_rpc_client")

        # Check if the branch already exist
        try:
            await Branch.get_by_name(session=session, name=data["name"])
            raise ValueError(f"The branch {data['name']}, already exist")
        except BranchNotFound:
            pass

        obj = Branch(**data)
        await obj.save(session=session)

        if not obj.is_data_only:
            # Query all repositories and add a branch on each one of them too
            repositories = await NodeManager.query(session=session, schema="Repository")

            for repo in repositories:
                resp = await rpc_client.call(
                    message=InfrahubGitRPC(
                        action=GitMessageAction.BRANCH_ADD, repository=repo, params={"branch_name": obj.name}
                    ),
                    wait_for_response=not background_execution,
                )
                # TODO need to validate that everything go as expected
                # TODO need to run all repos in //

        ok = True

        fields = await extract_fields(info.field_nodes[0].selection_set)

        # Generate Event in message bus
        if config.SETTINGS.broker.enable and info.context.get("background"):
            info.context.get("background").add_task(
                send_event, InfrahubBranchMessage(action=BranchMessageAction.CREATE, branch=obj.name)
            )

        return cls(object=await obj.to_graphql(fields=fields.get("object", {})), ok=ok)


class BranchNameInput(InputObjectType):
    name = String(required=False)


class BranchRebase(Mutation):
    class Arguments:
        data = BranchNameInput(required=True)

    ok = Boolean()
    object = Field(BranchType)

    @classmethod
    async def mutate(cls, root, info, data):

        session: AsyncSession = info.context.get("infrahub_session")

        obj = await Branch.get_by_name(session=session, name=data["name"])
        await obj.rebase(session=session)

        fields = await extract_fields(info.field_nodes[0].selection_set)

        ok = True

        if config.SETTINGS.broker.enable and info.context.get("background"):
            info.context.get("background").add_task(
                send_event, InfrahubBranchMessage(action=BranchMessageAction.REBASE, branch=obj.name)
            )

        return cls(object=await obj.to_graphql(fields=fields.get("object", {})), ok=ok)


class BranchValidate(Mutation):
    class Arguments:
        data = BranchNameInput(required=True)

    ok = Boolean()
    messages = List(String)
    object = Field(BranchType)

    @classmethod
    async def mutate(cls, root, info, data):

        session: AsyncSession = info.context.get("infrahub_session")

        obj = await Branch.get_by_name(session=session, name=data["name"])
        ok, messages = await obj.validate(session=session)

        fields = await extract_fields(info.field_nodes[0].selection_set)

        return cls(object=await obj.to_graphql(fields=fields.get("object", {})), messages=messages, ok=ok)


class BranchMerge(Mutation):
    class Arguments:
        data = BranchNameInput(required=True)

    ok = Boolean()
    object = Field(BranchType)

    @classmethod
    async def mutate(cls, root, info, data):

        session: AsyncSession = info.context.get("infrahub_session")

        obj = await Branch.get_by_name(session=session, name=data["name"])
        await obj.merge(session=session)

        fields = await extract_fields(info.field_nodes[0].selection_set)

        ok = True

        if config.SETTINGS.broker.enable and info.context.get("background"):
            info.context.get("background").add_task(
                send_event, InfrahubBranchMessage(action=BranchMessageAction.MERGE, branch=obj.name)
            )

        return cls(object=await obj.to_graphql(fields=fields.get("object", {})), ok=ok)
