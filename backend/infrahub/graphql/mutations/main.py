from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Union

from graphene import InputObjectType, Mutation
from graphene.types.mutation import MutationOptions
from infrahub_sdk.utils import extract_fields
from typing_extensions import Self

from infrahub import config, lock
from infrahub.core import registry
from infrahub.core.constants import InfrahubKind, MutationAction
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
from infrahub.lock import InfrahubMultiLock, build_object_lock_name
from infrahub.log import get_log_data, get_logger
from infrahub.worker import WORKER_IDENTITY

from .node_getter.by_default_filter import MutationNodeGetterByDefaultFilter
from .node_getter.by_hfid import MutationNodeGetterByHfid
from .node_getter.by_id import MutationNodeGetterById

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

    from ..initialization import GraphqlContext
    from .node_getter.interface import MutationNodeGetterInterface

# pylint: disable=unused-argument

log = get_logger()

KINDS_CONCURRENT_MUTATIONS_NOT_ALLOWED = [InfrahubKind.GENERICGROUP]


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

        if "Create" in cls.__name__:
            obj, mutation = await cls.mutate_create(info=info, branch=context.branch, data=data, **kwargs)
            action = MutationAction.ADDED
        elif "Update" in cls.__name__:
            obj, mutation = await cls.mutate_update(info=info, branch=context.branch, data=data, **kwargs)
            action = MutationAction.UPDATED
        elif "Upsert" in cls.__name__:
            node_manager = NodeManager()
            node_getters = [
                MutationNodeGetterById(db=context.db, node_manager=node_manager),
                MutationNodeGetterByHfid(db=context.db, node_manager=node_manager),
                MutationNodeGetterByDefaultFilter(db=context.db, node_manager=node_manager),
            ]
            obj, mutation, created = await cls.mutate_upsert(
                info=info, branch=context.branch, data=data, node_getters=node_getters, **kwargs
            )
            if created:
                action = MutationAction.ADDED
            else:
                action = MutationAction.UPDATED
        elif "Delete" in cls.__name__:
            obj, mutation = await cls.mutate_delete(info=info, branch=context.branch, data=data, **kwargs)
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

            graphql_payload = await obj.to_graphql(db=context.db, filter_sensitive=True)
            event = NodeMutatedEvent(
                branch=context.branch.name,
                kind=obj._schema.kind,
                node_id=obj.id,
                data=graphql_payload,
                action=action,
                fields=_get_data_fields(data),
                meta=EventMeta(initiator_id=WORKER_IDENTITY, request_id=request_id),
            )

            context.background.add_task(context.active_service.event.send, event)

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
    async def _call_mutate_create_object(cls, data: InputObjectType, db: InfrahubDatabase, branch: Branch):
        """
        Wrapper around mutate_create_object to potentially activate locking.
        """
        schema_branch = db.schema.get_schema_branch(name=branch.name)
        lock_names = _get_kind_lock_names_on_object_mutation(
            kind=cls._meta.schema.kind, branch=branch, schema_branch=schema_branch
        )
        if lock_names:
            async with InfrahubMultiLock(lock_registry=lock.registry, locks=lock_names):
                return await cls.mutate_create_object(data=data, db=db, branch=branch)

        return await cls.mutate_create_object(data=data, db=db, branch=branch)

    @classmethod
    async def mutate_create(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        database: Optional[InfrahubDatabase] = None,
    ) -> tuple[Node, Self]:
        context: GraphqlContext = info.context
        db = database or context.db
        obj = await cls._call_mutate_create_object(data=data, db=db, branch=branch)
        result = await cls.mutate_create_to_graphql(info=info, db=db, obj=obj)
        return obj, result

    @classmethod
    @retry_db_transaction(name="object_create")
    async def mutate_create_object(
        cls,
        data: InputObjectType,
        db: InfrahubDatabase,
        branch: Branch,
    ) -> Node:
        component_registry = get_component_registry()
        node_constraint_runner = await component_registry.get_component(NodeConstraintRunner, db=db, branch=branch)
        node_class = Node
        if cls._meta.schema.kind in registry.node:
            node_class = registry.node[cls._meta.schema.kind]

        try:
            obj = await node_class.init(db=db, schema=cls._meta.schema, branch=branch)
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
    async def _call_mutate_update(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        db: InfrahubDatabase,
        obj: Node,
    ) -> tuple[Node, Self]:
        """
        Wrapper around mutate_update to potentially activate locking and call it within a database transaction.
        """

        schema_branch = db.schema.get_schema_branch(name=branch.name)
        lock_names = _get_kind_lock_names_on_object_mutation(
            kind=cls._meta.schema.kind, branch=branch, schema_branch=schema_branch
        )

        if db.is_transaction:
            if lock_names:
                async with InfrahubMultiLock(lock_registry=lock.registry, locks=lock_names):
                    obj = await cls.mutate_update_object(db=db, info=info, data=data, branch=branch, obj=obj)
            else:
                obj = await cls.mutate_update_object(db=db, info=info, data=data, branch=branch, obj=obj)
            result = await cls.mutate_update_to_graphql(db=db, info=info, obj=obj)
            return obj, result

        async with db.start_transaction() as dbt:
            if lock_names:
                async with InfrahubMultiLock(lock_registry=lock.registry, locks=lock_names):
                    obj = await cls.mutate_update_object(db=dbt, info=info, data=data, branch=branch, obj=obj)
            else:
                obj = await cls.mutate_update_object(db=dbt, info=info, data=data, branch=branch, obj=obj)
            result = await cls.mutate_update_to_graphql(db=dbt, info=info, obj=obj)
            return obj, result

    @classmethod
    @retry_db_transaction(name="object_update")
    async def mutate_update(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        database: Optional[InfrahubDatabase] = None,
        node: Optional[Node] = None,
    ) -> tuple[Node, Self]:
        context: GraphqlContext = info.context
        db = database or context.db

        obj = node or await NodeManager.find_object(
            db=db, kind=cls._meta.schema.kind, id=data.get("id"), hfid=data.get("hfid"), branch=branch
        )

        try:
            obj, result = await cls._call_mutate_update(info=info, data=data, db=db, branch=branch, obj=obj)
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

        return obj, result

    @classmethod
    async def mutate_update_object(
        cls, db: InfrahubDatabase, info: GraphQLResolveInfo, data: InputObjectType, branch: Branch, obj: Node
    ) -> Node:
        component_registry = get_component_registry()
        node_constraint_runner = await component_registry.get_component(NodeConstraintRunner, db=db, branch=branch)

        before_mutate_profile_ids = await cls._get_profile_ids(db=db, obj=obj)
        await obj.from_graphql(db=db, data=data)
        fields_to_validate = list(data)
        await node_constraint_runner.check(node=obj, field_filters=fields_to_validate)

        fields = list(data.keys())
        for field in ("id", "hfid"):
            if field in fields:
                fields.remove(field)

        await obj.save(db=db, fields=fields)
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
        node_getters: list[MutationNodeGetterInterface],
        database: Optional[InfrahubDatabase] = None,
    ) -> tuple[Node, Self, bool]:
        schema_name = cls._meta.schema.kind

        context: GraphqlContext = info.context
        db = database or context.db

        node_schema = db.schema.get(name=schema_name, branch=branch)

        node = None
        for getter in node_getters:
            node = await getter.get_node(node_schema=node_schema, data=data, branch=branch)
            if node:
                break

        if node:
            updated_obj, mutation = await cls.mutate_update(info=info, data=data, branch=branch, database=db, node=node)
            return updated_obj, mutation, False
        # We need to convert the InputObjectType into a dict in order to remove hfid that isn't a valid input when creating the object
        data_dict = dict(data)
        if "hfid" in data:
            del data_dict["hfid"]
        created_obj, mutation = await cls.mutate_create(info=info, data=data_dict, branch=branch)
        return created_obj, mutation, True

    @classmethod
    @retry_db_transaction(name="object_delete")
    async def mutate_delete(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
    ) -> tuple[Node, Self]:
        context: GraphqlContext = info.context

        obj = await NodeManager.find_object(
            db=context.db, kind=cls._meta.schema.kind, id=data.get("id"), hfid=data.get("hfid"), branch=branch
        )

        try:
            async with context.db.start_transaction() as db:
                deleted = await NodeManager.delete(db=db, branch=branch, nodes=[obj])
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


def _get_kinds_to_lock_on_object_mutation(kind: str, schema_branch: SchemaBranch) -> list[str]:
    """
    Return kinds for which we want to lock during creating / updating an object of a given schema node.
    Lock should be performed on schema kind and its generics having a uniqueness_constraint defined.
    If a generic uniqueness constraint is the same as the node schema one,
    it means node schema overrided this constraint, in which case we only need to lock on the generic.
    """

    node_schema = schema_branch.get(name=kind)

    schema_uc = None
    kinds = []
    if node_schema.uniqueness_constraints:
        kinds.append(node_schema.kind)
        schema_uc = node_schema.uniqueness_constraints

    if node_schema.is_generic_schema:
        return kinds

    generics_kinds = node_schema.inherit_from

    node_schema_kind_removed = False
    for generic_kind in generics_kinds:
        generic_uc = schema_branch.get(name=generic_kind).uniqueness_constraints
        if generic_uc:
            kinds.append(generic_kind)
            if not node_schema_kind_removed and generic_uc == schema_uc:
                # Check whether we should remove original schema kind as it simply overrides uniqueness_constraint
                # of a generic
                kinds.pop(0)
                node_schema_kind_removed = True
    return kinds


def _should_kind_be_locked_on_any_branch(kind: str, schema_branch: SchemaBranch) -> bool:
    """
    Check whether kind or any kind generic is in KINDS_TO_LOCK_ON_ANY_BRANCH.
    """

    if kind in KINDS_CONCURRENT_MUTATIONS_NOT_ALLOWED:
        return True

    node_schema = schema_branch.get(name=kind)
    if node_schema.is_generic_schema:
        return False

    for generic_kind in node_schema.inherit_from:
        if generic_kind in KINDS_CONCURRENT_MUTATIONS_NOT_ALLOWED:
            return True
    return False


def _get_kind_lock_names_on_object_mutation(kind: str, branch: Branch, schema_branch: SchemaBranch) -> list[str]:
    """
    Return objects kind for which we want to avoid concurrent mutation (create/update). Except for some specific kinds,
    concurrent mutations are only allowed on non-main branch as objects validations will be performed at least when merging in main branch.
    """

    if not branch.is_default and not _should_kind_be_locked_on_any_branch(kind, schema_branch):
        return []

    lock_kinds = _get_kinds_to_lock_on_object_mutation(kind, schema_branch)
    lock_names = [build_object_lock_name(kind) for kind in lock_kinds]
    return lock_names


def _get_data_fields(data: InputObjectType) -> list[str]:
    return [field for field in data.keys() if field not in ["id", "hfid"]]
