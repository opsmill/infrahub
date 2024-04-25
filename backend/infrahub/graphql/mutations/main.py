from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Tuple, Union

from graphene import InputObjectType, Mutation
from graphene.types.mutation import MutationOptions
from infrahub_sdk.utils import extract_fields
from typing_extensions import Self

from infrahub import config
from infrahub.auth import (
    validate_mutation_permissions,
    validate_mutation_permissions_update_node,
)
from infrahub.core import registry
from infrahub.core.constants import MutationAction
from infrahub.core.constraint.node.runner import NodeConstraintRunner
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.profile_schema import ProfileSchema
from infrahub.core.timestamp import Timestamp
from infrahub.database import retry_db_transaction
from infrahub.dependencies.registry import get_component_registry
from infrahub.exceptions import NodeNotFoundError, ValidationError
from infrahub.log import get_log_data, get_logger
from infrahub.message_bus import Meta, messages
from infrahub.services import services
from infrahub.worker import WORKER_IDENTITY

from .node_getter.by_default_filter import MutationNodeGetterByDefaultFilter
from .node_getter.by_id import MutationNodeGetterById

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

    from .. import GraphqlContext
    from .node_getter.interface import MutationNodeGetterInterface

# pylint: disable=unused-argument

log = get_logger()


# ------------------------------------------
# Infrahub GraphQLType
# ------------------------------------------
class InfrahubMutationOptions(MutationOptions):
    schema = None


class InfrahubMutationMixin:
    @classmethod
    async def mutate(cls, root: dict, info: GraphQLResolveInfo, *args, **kwargs):
        context: GraphqlContext = info.context

        obj = None
        mutation = None
        action = MutationAction.UNDEFINED
        validate_mutation_permissions(operation=cls.__name__, account_session=context.account_session)

        if "Create" in cls.__name__:
            obj, mutation = await cls.mutate_create(
                root=root, info=info, branch=context.branch, at=context.at, *args, **kwargs
            )
            action = MutationAction.ADDED
        elif "Update" in cls.__name__:
            obj, mutation = await cls.mutate_update(
                root=root, info=info, branch=context.branch, at=context.at, *args, **kwargs
            )
            action = MutationAction.UPDATED
        elif "Upsert" in cls.__name__:
            node_manager = NodeManager()
            node_getters = [
                MutationNodeGetterById(context.db, node_manager),
                MutationNodeGetterByDefaultFilter(context.db, node_manager),
            ]
            obj, mutation, created = await cls.mutate_upsert(
                root=root, info=info, branch=context.branch, at=context.at, node_getters=node_getters, *args, **kwargs
            )
            if created:
                action = MutationAction.ADDED
            else:
                action = MutationAction.UPDATED
        elif "Delete" in cls.__name__:
            obj, mutation = await cls.mutate_delete(
                root=root, info=info, branch=context.branch, at=context.at, *args, **kwargs
            )
            action = MutationAction.REMOVED
        else:
            raise ValueError(
                f"Unexpected class Name: {cls.__name__}, should end with Create, Update, Upsert, or Delete"
            )

        # Reset the time of the query to guarantee that all resolvers executed after this point will account for the changes
        context.at = Timestamp()

        if config.SETTINGS.broker.enable and context.background:
            log_data = get_log_data()
            request_id = log_data.get("request_id", "")

            data = await obj.to_graphql(db=context.db, filter_sensitive=True)

            message = messages.EventNodeMutated(
                branch=context.branch.name,
                kind=obj._schema.kind,
                node_id=obj.id,
                data=data,
                action=action.value,
                meta=Meta(initiator_id=WORKER_IDENTITY, request_id=request_id),
            )
            context.background.add_task(services.send, message)

        return mutation

    @classmethod
    async def mutate_create(
        cls,
        root: dict,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        at: str,
        database: Optional[InfrahubDatabase] = None,
    ) -> Tuple[Node, Self]:
        context: GraphqlContext = info.context
        db = database or context.db
        obj = await cls.mutate_create_object(data=data, db=db, branch=branch, at=at)
        result = await cls.mutate_create_to_graphql(info=info, db=db, obj=obj)
        return obj, result

    @classmethod
    @retry_db_transaction(name="object_create")
    async def mutate_create_object(
        cls,
        data: InputObjectType,
        db: InfrahubDatabase,
        branch: Branch,
        at: str,
    ) -> Node:
        component_registry = get_component_registry()
        node_constraint_runner = await component_registry.get_component(NodeConstraintRunner, db=db, branch=branch)
        node_class = Node
        if cls._meta.schema.kind in registry.node:
            node_class = registry.node[cls._meta.schema.kind]

        try:
            obj = await node_class.init(db=db, schema=cls._meta.schema, branch=branch, at=at)
            await obj.new(db=db, **data)
            fields_to_validate = list(data)
            await node_constraint_runner.check(node=obj, field_filters=fields_to_validate)

            if db.is_transaction:
                await obj.save(db=db)
            else:
                async with db.start_transaction() as dbt:
                    await obj.save(db=dbt)

        except ValidationError as exc:
            raise ValueError(str(exc)) from exc
        return obj

    @classmethod
    async def mutate_create_to_graphql(cls, info: GraphQLResolveInfo, db: InfrahubDatabase, obj: Node) -> Self:
        fields = await extract_fields(info.field_nodes[0].selection_set)
        result = {"ok": True}
        if "object" in fields:
            result["object"] = await obj.to_graphql(db=db, fields=fields.get("object", {}))
        return cls(**result)

    @classmethod
    @retry_db_transaction(name="object_update")
    async def mutate_update(
        cls,
        root: dict,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        at: str,
        database: Optional[InfrahubDatabase] = None,
        node: Optional[Node] = None,
    ):
        context: GraphqlContext = info.context
        db = database or context.db
        component_registry = get_component_registry()
        node_constraint_runner = await component_registry.get_component(NodeConstraintRunner, db=db, branch=branch)

        obj = node or await NodeManager.get_one_by_id_or_default_filter(
            db=db,
            schema_name=cls._meta.schema.kind,
            id=data.get("id"),
            branch=branch,
            at=at,
            include_owner=True,
            include_source=True,
        )

        fields_object = await extract_fields(info.field_nodes[0].selection_set)
        fields_object = fields_object.get("object", {})
        result = {"ok": True}
        try:
            await obj.from_graphql(db=db, data=data)
            fields_to_validate = list(data)
            await node_constraint_runner.check(node=obj, field_filters=fields_to_validate)
            node_id = data.get("id", obj.id)
            fields = list(data.keys())
            if "id" in fields:
                fields.remove("id")
            validate_mutation_permissions_update_node(
                operation=cls.__name__, node_id=node_id, account_session=context.account_session, fields=fields
            )

            if db.is_transaction:
                await obj.save(db=db)
                if fields_object:
                    result["object"] = await obj.to_graphql(db=db, fields=fields_object)

            else:
                async with db.start_transaction() as dbt:
                    await obj.save(db=dbt)
                    if fields_object:
                        result["object"] = await obj.to_graphql(db=dbt, fields=fields_object)

        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

        return obj, cls(**result)

    @classmethod
    @retry_db_transaction(name="object_upsert")
    async def mutate_upsert(
        cls,
        root: dict,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        at: str,
        node_getters: List[MutationNodeGetterInterface],
        database: Optional[InfrahubDatabase] = None,
    ) -> Tuple[Node, Self, bool]:
        schema_name = cls._meta.schema.kind
        node_schema = registry.schema.get(name=schema_name, branch=branch)

        node = None
        for getter in node_getters:
            node = await getter.get_node(node_schema=node_schema, data=data, branch=branch, at=at)
            if node:
                break

        if node:
            updated_obj, mutation = await cls.mutate_update(
                root=root, info=info, data=data, branch=branch, at=at, database=database, node=node
            )
            return updated_obj, mutation, False
        created_obj, mutation = await cls.mutate_create(root=root, info=info, data=data, branch=branch, at=at)
        return created_obj, mutation, True

    @classmethod
    @retry_db_transaction(name="object_delete")
    async def mutate_delete(
        cls,
        root,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        at: str,
    ):
        context: GraphqlContext = info.context

        if not (obj := await NodeManager.get_one(db=context.db, id=data.get("id"), branch=branch, at=at)):
            raise NodeNotFoundError(branch, cls._meta.schema.kind, data.get("id"))

        try:
            async with context.db.start_transaction() as db:
                deleted = await NodeManager.delete(db=db, at=at, branch=branch, nodes=[obj])
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

        deleted_str = ", ".join([f"{d.get_kind()}({d.get_id()})" for d in deleted])
        log.info(f"nodes deleted: {deleted_str}")

        ok = True

        return obj, cls(ok=ok)


class InfrahubMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(  # pylint: disable=arguments-differ
        cls, schema: Optional[Union[NodeSchema, GenericSchema, ProfileSchema]] = None, _meta=None, **options
    ) -> None:
        # Make sure schema is a valid NodeSchema Node Class
        if not isinstance(schema, (NodeSchema, GenericSchema, ProfileSchema)):
            raise ValueError(f"You need to pass a valid NodeSchema in '{cls.__name__}.Meta', received '{schema}'")

        if not _meta:
            _meta = InfrahubMutationOptions(cls)

        _meta.schema = schema

        super().__init_subclass_with_meta__(_meta=_meta, **options)
