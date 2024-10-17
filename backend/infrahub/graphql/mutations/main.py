from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Union

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
from infrahub.events import EventMeta, NodeMutatedEvent
from infrahub.exceptions import ValidationError
from infrahub.log import get_log_data, get_logger
from infrahub.worker import WORKER_IDENTITY

from .node_getter.by_default_filter import MutationNodeGetterByDefaultFilter
from .node_getter.by_hfid import MutationNodeGetterByHfid
from .node_getter.by_id import MutationNodeGetterById

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

    from ..initialization import GraphqlContext
    from .node_getter.interface import MutationNodeGetterInterface

# pylint: disable=unused-argument

log = get_logger()


# ------------------------------------------
# Infrahub GraphQLType
# ------------------------------------------
class InfrahubMutationOptions(MutationOptions):
    schema: Optional[NodeSchema] = None


class InfrahubMutationMixin:
    @classmethod
    async def mutate(cls, root: dict, info: GraphQLResolveInfo, data: InputObjectType, *args: Any, **kwargs):
        context: GraphqlContext = info.context

        obj = None
        mutation = None
        action = MutationAction.UNDEFINED
        validate_mutation_permissions(operation=cls.__name__, account_session=context.account_session)

        if "Create" in cls.__name__:
            obj, mutation = await cls.mutate_create(
                info=info, branch=context.branch, data=data, at=context.at, **kwargs
            )
            action = MutationAction.ADDED
        elif "Update" in cls.__name__:
            obj, mutation = await cls.mutate_update(
                info=info, branch=context.branch, data=data, at=context.at, **kwargs
            )
            action = MutationAction.UPDATED
        elif "Upsert" in cls.__name__:
            node_manager = NodeManager()
            node_getters = [
                MutationNodeGetterById(db=context.db, node_manager=node_manager),
                MutationNodeGetterByHfid(db=context.db, node_manager=node_manager),
                MutationNodeGetterByDefaultFilter(db=context.db, node_manager=node_manager),
            ]
            obj, mutation, created = await cls.mutate_upsert(
                info=info, branch=context.branch, data=data, at=context.at, node_getters=node_getters, **kwargs
            )
            if created:
                action = MutationAction.ADDED
            else:
                action = MutationAction.UPDATED
        elif "Delete" in cls.__name__:
            obj, mutation = await cls.mutate_delete(
                info=info, branch=context.branch, data=data, at=context.at, **kwargs
            )
            action = MutationAction.REMOVED
        else:
            raise ValueError(
                f"Unexpected class Name: {cls.__name__}, should end with Create, Update, Upsert, or Delete"
            )

        # Reset the time of the query to guarantee that all resolvers executed after this point will account for the changes
        context.at = Timestamp()

        # Get relevant macros based on the current change
        # schema_branch = registry.schema.get_schema_branch(name=context.branch.name)
        # macros = schema_branch.get_impacted_macros(kind=obj.get_kind(), updates=data.keys())

        if config.SETTINGS.broker.enable and context.background:
            log_data = get_log_data()
            request_id = log_data.get("request_id", "")

            graphql_payload = await obj.to_graphql(db=context.db, filter_sensitive=True)

            event = NodeMutatedEvent(
                branch=context.branch.name,
                kind=obj._schema.kind,
                node_id=obj.id,
                data=graphql_payload,
                action=action,
                meta=EventMeta(initiator_id=WORKER_IDENTITY, request_id=request_id),
            )

            context.background.add_task(context.service.event.send, event)

            # Add event
            # if macros:
            #    event = SomeMacroEvent(branch=context.branch.name, kind=obj.get_kind(), node_id=obj.id, action=action, macros=macros)
            #    context.background.add_task(context.service.event.send, event)

        return mutation

    @classmethod
    async def _get_profile_ids(cls, db: InfrahubDatabase, obj: Node) -> set[str]:
        if not hasattr(obj, "profiles"):
            return set()
        profile_rels = await obj.profiles.get_relationships(db=db)
        return {pr.peer_id for pr in profile_rels}

    @classmethod
    async def _refresh_for_profile_update(
        cls, db: InfrahubDatabase, branch: Branch, obj: Node, previous_profile_ids: Optional[set[str]] = None
    ) -> Node:
        if not hasattr(obj, "profiles"):
            return obj
        current_profile_ids = await cls._get_profile_ids(db=db, obj=obj)
        if previous_profile_ids is None or previous_profile_ids != current_profile_ids:
            return await NodeManager.get_one_by_id_or_default_filter(
                db=db,
                kind=cls._meta.schema.kind,
                id=obj.get_id(),
                branch=branch,
                include_owner=True,
                include_source=True,
            )
        return obj

    @classmethod
    async def mutate_create(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        at: str,
        database: Optional[InfrahubDatabase] = None,
    ) -> tuple[Node, Self]:
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

        if await cls._get_profile_ids(db=db, obj=obj):
            obj = await cls._refresh_for_profile_update(db=db, branch=branch, obj=obj)

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
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        at: str,
        database: Optional[InfrahubDatabase] = None,
        node: Optional[Node] = None,
    ) -> tuple[Node, Self]:
        context: GraphqlContext = info.context
        db = database or context.db

        obj = node or await NodeManager.find_object(
            db=db, kind=cls._meta.schema.kind, id=data.get("id"), hfid=data.get("hfid"), branch=branch, at=at
        )

        try:
            if db.is_transaction:
                obj = await cls.mutate_update_object(db=db, info=info, data=data, branch=branch, obj=obj)
                result = await cls.mutate_update_to_graphql(db=db, info=info, obj=obj)
            else:
                async with db.start_transaction() as dbt:
                    obj = await cls.mutate_update_object(db=dbt, info=info, data=data, branch=branch, obj=obj)
                    result = await cls.mutate_update_to_graphql(db=dbt, info=info, obj=obj)
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

        return obj, result

    @classmethod
    async def mutate_update_object(
        cls,
        db: InfrahubDatabase,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        obj: Node,
    ) -> Node:
        context: GraphqlContext = info.context
        component_registry = get_component_registry()
        node_constraint_runner = await component_registry.get_component(NodeConstraintRunner, db=db, branch=branch)

        before_mutate_profile_ids = await cls._get_profile_ids(db=db, obj=obj)
        await obj.from_graphql(db=db, data=data)
        fields_to_validate = list(data)
        await node_constraint_runner.check(node=obj, field_filters=fields_to_validate)
        node_id = data.get("id", obj.id)
        fields = list(data.keys())
        if "id" in fields:
            fields.remove("id")
        if "hfid" in fields:
            fields.remove("hfid")
        validate_mutation_permissions_update_node(
            operation=cls.__name__, node_id=node_id, account_session=context.account_session, fields=fields
        )

        await obj.save(db=db)
        obj = await cls._refresh_for_profile_update(
            db=db, branch=branch, obj=obj, previous_profile_ids=before_mutate_profile_ids
        )
        return obj

    @classmethod
    async def mutate_update_to_graphql(
        cls,
        db: InfrahubDatabase,
        info: GraphQLResolveInfo,
        obj: Node,
    ) -> Self:
        fields_object = await extract_fields(info.field_nodes[0].selection_set)
        fields_object = fields_object.get("object", {})
        result = {"ok": True}
        if fields_object:
            result["object"] = await obj.to_graphql(db=db, fields=fields_object)
        return cls(**result)

    @classmethod
    @retry_db_transaction(name="object_upsert")
    async def mutate_upsert(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        at: str,
        node_getters: list[MutationNodeGetterInterface],
        database: Optional[InfrahubDatabase] = None,
    ) -> tuple[Node, Self, bool]:
        schema_name = cls._meta.schema.kind

        context: GraphqlContext = info.context
        db = database or context.db

        node_schema = db.schema.get(name=schema_name, branch=branch)

        node = None
        for getter in node_getters:
            node = await getter.get_node(node_schema=node_schema, data=data, branch=branch, at=at)
            if node:
                break

        if node:
            updated_obj, mutation = await cls.mutate_update(
                info=info, data=data, branch=branch, at=at, database=db, node=node
            )
            return updated_obj, mutation, False
        # We need to convert the InputObjectType into a dict in order to remove hfid that isn't a valid input when creating the object
        data_dict = dict(data)
        if "hfid" in data:
            del data_dict["hfid"]
        created_obj, mutation = await cls.mutate_create(info=info, data=data_dict, branch=branch, at=at)
        return created_obj, mutation, True

    @classmethod
    @retry_db_transaction(name="object_delete")
    async def mutate_delete(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        at: str,
    ) -> tuple[Node, Self]:
        context: GraphqlContext = info.context

        obj = await NodeManager.find_object(
            db=context.db, kind=cls._meta.schema.kind, id=data.get("id"), hfid=data.get("hfid"), branch=branch, at=at
        )

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
