from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from graphene import InputObjectType, Mutation
from graphene.types.mutation import MutationOptions
from infrahub_sdk.utils import extract_fields_first_node
from typing_extensions import Self

from infrahub import config, lock
from infrahub.core.constants import MutationAction
from infrahub.core.constraint.node.runner import NodeConstraintRunner
from infrahub.core.manager import NodeManager
from infrahub.core.node.create import create_node, get_profile_ids
from infrahub.core.schema import MainSchemaTypes, NodeSchema
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.profile_schema import ProfileSchema
from infrahub.core.schema.template_schema import TemplateSchema
from infrahub.core.timestamp import Timestamp
from infrahub.database import retry_db_transaction
from infrahub.dependencies.registry import get_component_registry
from infrahub.events.generator import generate_node_mutation_events
from infrahub.exceptions import HFIDViolatedError, InitializationError, NodeNotFoundError
from infrahub.graphql.context import apply_external_context
from infrahub.graphql.field_extractor import extract_graphql_fields
from infrahub.lock import InfrahubMultiLock
from infrahub.log import get_log_data, get_logger
from infrahub.profiles.node_applier import NodeProfilesApplier

from ...core.node.lock_utils import get_kind_lock_names_on_object_mutation
from .node_getter.by_default_filter import MutationNodeGetterByDefaultFilter

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.types.context import ContextInput

    from ..initialization import GraphqlContext


log = get_logger()


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
    async def mutate_create(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        database: InfrahubDatabase | None = None,
        override_data: dict[str, Any] | None = None,
    ) -> tuple[Node, Self]:
        db = database or info.context.db
        schema = cls._meta.active_schema

        create_data = dict(data)
        create_data.update(override_data or {})

        obj = await create_node(
            data=create_data,
            db=db,
            branch=branch,
            schema=schema,
        )

        graphql_response = await build_graphql_response(info=info, db=db, obj=obj)
        return obj, cls(**graphql_response)

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
        lock_names = get_kind_lock_names_on_object_mutation(
            kind=cls._meta.active_schema.kind, branch=branch, schema_branch=schema_branch, data=dict(data)
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

        await obj.from_graphql(db=db, data=data)
        fields_to_validate = list(data)
        await node_constraint_runner.check(
            node=obj, field_filters=fields_to_validate, skip_uniqueness_check=skip_uniqueness_check
        )

        fields = list(data.keys())
        for field_to_remove in ("id", "hfid"):
            if field_to_remove in fields:
                fields.remove(field_to_remove)

        after_mutate_profile_ids = await get_profile_ids(db=db, obj=obj)
        if after_mutate_profile_ids or (not after_mutate_profile_ids and obj.uses_profiles()):
            node_profiles_applier = NodeProfilesApplier(db=db, branch=branch)
            updated_field_names = await node_profiles_applier.apply_profiles(node=obj)
            fields += updated_field_names
        await obj.save(db=db, fields=fields)

        return obj

    @classmethod
    async def mutate_update_to_graphql(
        cls,
        db: InfrahubDatabase,
        info: GraphQLResolveInfo,
        obj: Node,
    ) -> Self:
        fields_object = extract_graphql_fields(info=info)
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
            # This is a hack to avoid sitatuions where a node has an attribute or relationship called "pop"
            # which would have overridden the `pop` method of the InputObjectType object and as such would have
            # caused an error when trying to call `data.pop("hfid", None)`.
            # TypeError: 'NoneType' object is not callable
            data._pop = dict.pop.__get__(data, dict)
            data._pop("hfid", None)  # `hfid` is invalid for creation.
            created_obj, mutation = await cls.mutate_create(info=info, data=data, branch=branch)
            return created_obj, mutation, True
        except HFIDViolatedError as exc:
            # Only the HFID constraint has been violated, it means the node exists and we can update without rerunning constraints
            if len(exc.matching_nodes_ids) > 1:
                raise RuntimeError(f"Multiple {schema_name} nodes have the same hfid") from exc
            node_id = list(exc.matching_nodes_ids)[0]

            try:
                node = await NodeManager.get_one(
                    db=db, id=node_id, kind=schema_name, branch=branch, raise_on_error=True
                )
            except NodeNotFoundError as exc:
                if branch.is_default:
                    raise
                raise NodeNotFoundError(
                    node_type=exc.node_type,
                    identifier=exc.identifier,
                    branch_name=branch.name,
                    message=(
                        f"Node {exc.identifier} / {exc.node_type} uses this human-friendly ID, but does not exist on"
                        f" this branch. Please rebase this branch to access {exc.identifier} / {exc.node_type}"
                    ),
                ) from exc
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
    async def _delete_obj(cls, graphql_context: GraphqlContext, branch: Branch, obj: Node) -> list[Node]:
        db = graphql_context.db
        async with db.start_transaction() as dbt:
            deleted = await NodeManager.delete(db=dbt, branch=branch, nodes=[obj])
        deleted_str = ", ".join([f"{d.get_kind()}({d.get_id()})" for d in deleted])
        log.info(f"nodes deleted: {deleted_str}")
        return deleted

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

        deleted = await cls._delete_obj(graphql_context=graphql_context, branch=branch, obj=obj)

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


def _get_data_fields(data: InputObjectType) -> list[str]:
    return [field for field in data.keys() if field not in ["id", "hfid"]]


async def build_graphql_response(info: GraphQLResolveInfo, db: InfrahubDatabase, obj: Node) -> dict:
    fields = await extract_fields_first_node(info)
    result: dict[str, Any] = {"ok": True}
    if "object" in fields:
        result["object"] = await obj.to_graphql(db=db, fields=fields.get("object", {}))
    return result
