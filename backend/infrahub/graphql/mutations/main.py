from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from graphene import InputObjectType, Mutation
from graphene.types.mutation import MutationOptions
from infrahub_sdk.utils import extract_fields
from typing_extensions import Self

from infrahub import config, lock
from infrahub.core.constants import InfrahubKind, MutationAction
from infrahub.core.constraint.node.runner import NodeConstraintRunner
from infrahub.core.manager import NodeManager
from infrahub.core.node.create import (
    create_node,
    get_profile_ids,
    refresh_for_profile_update,
)
from infrahub.core.schema import MainSchemaTypes, NodeSchema
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.profile_schema import ProfileSchema
from infrahub.core.schema.template_schema import TemplateSchema
from infrahub.core.timestamp import Timestamp
from infrahub.database import retry_db_transaction
from infrahub.dependencies.registry import get_component_registry
from infrahub.events.generator import generate_node_mutation_events
from infrahub.exceptions import HFIDViolatedError, InitializationError
from infrahub.graphql.context import apply_external_context
from infrahub.lock import InfrahubMultiLock, build_object_lock_name
from infrahub.log import get_log_data, get_logger

from .node_getter.by_default_filter import MutationNodeGetterByDefaultFilter

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.types.context import ContextInput

    from ..initialization import GraphqlContext


log = get_logger()

KINDS_CONCURRENT_MUTATIONS_NOT_ALLOWED = [InfrahubKind.GENERICGROUP]


@dataclass
class DeleteResult:
    node: Node
    mutation: InfrahubMutationMixin
    deleted_nodes: list[Node] = field(default_factory=list)


# ------------------------------------------
# Infrahub GraphQLType
# ------------------------------------------
class InfrahubMutationOptions(MutationOptions):
    schema: MainSchemaTypes | None = None

    @property
    def active_schema(self) -> MainSchemaTypes:
        if self.schema:
            return self.schema
        raise InitializationError("This class is not initialized with a schema")


class InfrahubMutationMixin:
    _meta: InfrahubMutationOptions

    @classmethod
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: InputObjectType,
        context: ContextInput | None = None,
        **kwargs: dict[str, Any],
    ) -> Self:
        graphql_context: GraphqlContext = info.context
        await apply_external_context(graphql_context=graphql_context, context_input=context)

        obj = None
        mutation = None
        action = MutationAction.UNDEFINED
        deleted_nodes: list[Node] = []

        if "Create" in cls.__name__:
            obj, mutation = await cls.mutate_create(info=info, branch=graphql_context.branch, data=data)
            action = MutationAction.CREATED
        elif "Update" in cls.__name__:
            obj, mutation = await cls.mutate_update(info=info, branch=graphql_context.branch, data=data, **kwargs)
            action = MutationAction.UPDATED
        elif "Upsert" in cls.__name__:
            node_manager = NodeManager()
            node_getter_default_filter = MutationNodeGetterByDefaultFilter(
                db=graphql_context.db, node_manager=node_manager
            )
            obj, mutation, created = await cls.mutate_upsert(
                info=info,
                branch=graphql_context.branch,
                data=data,
                node_getter_default_filter=node_getter_default_filter,
                **kwargs,
            )
            if created:
                action = MutationAction.CREATED
            else:
                action = MutationAction.UPDATED
        elif "Delete" in cls.__name__:
            delete_result = await cls.mutate_delete(info=info, branch=graphql_context.branch, data=data, **kwargs)
            obj = delete_result.node
            mutation = delete_result.mutation
            deleted_nodes = delete_result.deleted_nodes

            action = MutationAction.DELETED
        else:
            raise ValueError(
                f"Unexpected class Name: {cls.__name__}, should end with Create, Update, Upsert, or Delete"
            )

        # Reset the time of the query to guarantee that all resolvers executed after this point will account for the changes
        graphql_context.at = Timestamp()

        if config.SETTINGS.broker.enable and graphql_context.background and obj.node_changelog.has_changes:
            log_data = get_log_data()
            request_id = log_data.get("request_id", "")

            events = await generate_node_mutation_events(
                node=obj,
                deleted_nodes=deleted_nodes,
                db=graphql_context.db,
                branch=graphql_context.branch,
                context=graphql_context.get_context(),
                request_id=request_id,
                action=action,
            )

            for event in events:
                graphql_context.background.add_task(graphql_context.active_service.event.send, event)

        return mutation

    @classmethod
    async def _call_mutate_create_object(cls, data: InputObjectType, db: InfrahubDatabase, branch: Branch) -> Node:
        """
        Wrapper around mutate_create_object to potentially activate locking.
        """
        schema_branch = db.schema.get_schema_branch(name=branch.name)
        lock_names = _get_kind_lock_names_on_object_mutation(
            kind=cls._meta.active_schema.kind, branch=branch, schema_branch=schema_branch
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
        database: InfrahubDatabase | None = None,
    ) -> tuple[Node, Self]:
        graphql_context: GraphqlContext = info.context
        db = database or graphql_context.db
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
        schema = cls._meta.active_schema
        if isinstance(schema, GenericSchema):
            raise ValueError(f"Node of generic schema `{schema.name=}` can not be instantiated.")
        return await create_node(
            data=dict(data),
            db=db,
            branch=branch,
            schema=schema,
        )

    @classmethod
    async def mutate_create_to_graphql(cls, info: GraphQLResolveInfo, db: InfrahubDatabase, obj: Node) -> Self:
        fields = await extract_fields(info.field_nodes[0].selection_set)
        result: dict[str, Any] = {"ok": True}
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
        skip_uniqueness_check: bool = False,
    ) -> tuple[Node, Self]:
        """
        Wrapper around mutate_update to potentially activate locking and call it within a database transaction.
        """

        schema_branch = db.schema.get_schema_branch(name=branch.name)
        lock_names = _get_kind_lock_names_on_object_mutation(
            kind=cls._meta.active_schema.kind, branch=branch, schema_branch=schema_branch
        )

        if db.is_transaction:
            if lock_names:
                async with InfrahubMultiLock(lock_registry=lock.registry, locks=lock_names):
                    obj = await cls.mutate_update_object(
                        db=db, info=info, data=data, branch=branch, obj=obj, skip_uniqueness_check=skip_uniqueness_check
                    )
            else:
                obj = await cls.mutate_update_object(
                    db=db, info=info, data=data, branch=branch, obj=obj, skip_uniqueness_check=skip_uniqueness_check
                )
            result = await cls.mutate_update_to_graphql(db=db, info=info, obj=obj)
            return obj, result

        async with db.start_transaction() as dbt:
            if lock_names:
                async with InfrahubMultiLock(lock_registry=lock.registry, locks=lock_names):
                    obj = await cls.mutate_update_object(
                        db=dbt,
                        info=info,
                        data=data,
                        branch=branch,
                        obj=obj,
                        skip_uniqueness_check=skip_uniqueness_check,
                    )
            else:
                obj = await cls.mutate_update_object(
                    db=dbt, info=info, data=data, branch=branch, obj=obj, skip_uniqueness_check=skip_uniqueness_check
                )
            result = await cls.mutate_update_to_graphql(db=dbt, info=info, obj=obj)
            return obj, result

    @classmethod
    @retry_db_transaction(name="object_update")
    async def mutate_update(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        database: InfrahubDatabase | None = None,
        node: Node | None = None,
    ) -> tuple[Node, Self]:
        graphql_context: GraphqlContext = info.context
        db = database or graphql_context.db

        obj = node or await NodeManager.find_object(
            db=db, kind=cls._meta.active_schema.kind, id=data.get("id"), hfid=data.get("hfid"), branch=branch
        )

        obj, result = await cls._call_mutate_update(info=info, data=data, db=db, branch=branch, obj=obj)

        return obj, result

    @classmethod
    async def mutate_update_object(
        cls,
        db: InfrahubDatabase,
        info: GraphQLResolveInfo,  # noqa: ARG003
        data: InputObjectType,
        branch: Branch,
        obj: Node,
        skip_uniqueness_check: bool = False,
    ) -> Node:
        component_registry = get_component_registry()
        node_constraint_runner = await component_registry.get_component(NodeConstraintRunner, db=db, branch=branch)

        before_mutate_profile_ids = await get_profile_ids(db=db, obj=obj)
        await obj.from_graphql(db=db, data=data)
        fields_to_validate = list(data)
        await node_constraint_runner.check(
            node=obj, field_filters=fields_to_validate, skip_uniqueness_check=skip_uniqueness_check
        )

        fields = list(data.keys())
        for field_to_remove in ("id", "hfid"):
            if field_to_remove in fields:
                fields.remove(field_to_remove)

        await obj.save(db=db, fields=fields)

        obj = await refresh_for_profile_update(
            db=db,
            branch=branch,
            obj=obj,
            previous_profile_ids=before_mutate_profile_ids,
            schema=cls._meta.active_schema,
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
        result: dict[str, Any] = {"ok": True}
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
        node_getter_default_filter: MutationNodeGetterByDefaultFilter,
        database: InfrahubDatabase | None = None,
    ) -> tuple[Node, Self, bool]:
        """
        First, check whether payload contains data identifying the node, such as id, hfid, or relevant fields for
        default_filter. If not, we will try to create the node, but this creation might fail if payload contains
        hfid fields (not `hfid` field itself) that would match an existing node in the database. In that case,
        we would update the node without rerunning uniqueness constraint.
        """

        schema = cls._meta.active_schema
        schema_name = schema.kind

        graphql_context: GraphqlContext = info.context
        db = database or graphql_context.db
        dict_data = dict(data)
        node = None

        if "id" in dict_data:
            node = await NodeManager.get_one(
                db=db, id=dict_data["id"], kind=schema_name, branch=branch, raise_on_error=True
            )
            updated_obj, mutation = await cls._call_mutate_update(
                info=info,
                data=data,
                db=db,
                branch=branch,
                obj=node,
            )
            return updated_obj, mutation, False

        if not schema.human_friendly_id and schema.default_filter is not None:
            node = await node_getter_default_filter.get_node(node_schema=schema, data=data, branch=branch)

        if "hfid" in data:
            node = await NodeManager.get_one_by_hfid(db=db, hfid=dict_data["hfid"], kind=schema_name, branch=branch)

        if node is not None:
            updated_obj, mutation = await cls._call_mutate_update(
                info=info,
                data=data,
                db=db,
                branch=branch,
                obj=node,
            )
            return updated_obj, mutation, False

        try:
            dict_data.pop("hfid", "unused")  # `hfid` is invalid for creation.
            created_obj, mutation = await cls.mutate_create(info=info, data=dict_data, branch=branch)
            return created_obj, mutation, True
        except HFIDViolatedError as exc:
            # Only the HFID constraint has been violated, it means the node exists and we can update without rerunning constraints
            if len(exc.matching_nodes_ids) > 1:
                raise RuntimeError(f"Multiple {schema_name} nodes have the same hfid") from exc
            node_id = list(exc.matching_nodes_ids)[0]
            node = await NodeManager.get_one(db=db, id=node_id, kind=schema_name, branch=branch, raise_on_error=True)
            updated_obj, mutation = await cls._call_mutate_update(
                info=info,
                data=data,
                db=db,
                branch=branch,
                obj=node,
                skip_uniqueness_check=True,
            )
            return updated_obj, mutation, False

    @classmethod
    @retry_db_transaction(name="object_delete")
    async def mutate_delete(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
    ) -> DeleteResult:
        graphql_context: GraphqlContext = info.context

        obj = await NodeManager.find_object(
            db=graphql_context.db,
            kind=cls._meta.active_schema.kind,
            id=data.get("id"),
            hfid=data.get("hfid"),
            branch=branch,
        )

        async with graphql_context.db.start_transaction() as db:
            deleted = await NodeManager.delete(db=db, branch=branch, nodes=[obj])

        deleted_str = ", ".join([f"{d.get_kind()}({d.get_id()})" for d in deleted])
        log.info(f"nodes deleted: {deleted_str}")

        ok = True

        return DeleteResult(node=obj, mutation=cls(ok=ok), deleted_nodes=deleted)


class InfrahubMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(
        cls,
        schema: NodeSchema | GenericSchema | ProfileSchema | TemplateSchema | None = None,
        _meta: InfrahubMutationOptions | None = None,
        **options: dict[str, Any],
    ) -> None:
        # Make sure schema is a valid NodeSchema Node Class
        if not isinstance(schema, NodeSchema | GenericSchema | ProfileSchema | TemplateSchema):
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
