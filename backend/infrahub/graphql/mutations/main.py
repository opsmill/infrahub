from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from graphene import InputObjectType, Mutation
from graphene.types.mutation import MutationOptions

from infrahub import config
from infrahub.auth import (
    validate_mutation_permissions,
    validate_mutation_permissions_update_node,
)
from infrahub.core import registry
from infrahub.core.constants import MutationAction
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.exceptions import NodeNotFound, ValidationError
from infrahub.log import get_log_data, get_logger
from infrahub.message_bus import Meta, messages
from infrahub.services import services
from infrahub.worker import WORKER_IDENTITY

from ..utils import extract_fields

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.auth import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

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
        at = info.context.get("infrahub_at")
        branch = info.context.get("infrahub_branch")
        account_session: AccountSession = info.context.get("account_session", None)
        db: InfrahubDatabase = info.context.get("infrahub_database")

        obj = None
        mutation = None
        action = MutationAction.UNDEFINED
        validate_mutation_permissions(operation=cls.__name__, account_session=account_session)

        if "Create" in cls.__name__:
            obj, mutation = await cls.mutate_create(root=root, info=info, branch=branch, at=at, *args, **kwargs)
            action = MutationAction.ADDED
        elif "Update" in cls.__name__:
            obj, mutation = await cls.mutate_update(root=root, info=info, branch=branch, at=at, *args, **kwargs)
            action = MutationAction.UPDATED
        elif "Upsert" in cls.__name__:
            obj, mutation, created = await cls.mutate_upsert(
                root=root, info=info, branch=branch, at=at, *args, **kwargs
            )
            if created:
                action = MutationAction.ADDED
            else:
                action = MutationAction.UPDATED
        elif "Delete" in cls.__name__:
            obj, mutation = await cls.mutate_delete(root=root, info=info, branch=branch, at=at, *args, **kwargs)
            action = MutationAction.REMOVED
        else:
            raise ValueError(
                f"Unexpected class Name: {cls.__name__}, should end with Create, Update, Upsert, or Delete"
            )

        if config.SETTINGS.broker.enable and info.context.get("background"):
            log_data = get_log_data()
            request_id = log_data.get("request_id", "")

            data = await obj.to_graphql(db=db)
            message = messages.EventNodeMutated(
                branch=branch.name,
                kind=obj._schema.kind,
                node_id=obj.id,
                data=data,
                action=action.value,
                meta=Meta(initiator_id=WORKER_IDENTITY, request_id=request_id),
            )
            info.context.get("background").add_task(services.send, message)

        return mutation

    @classmethod
    async def mutate_create(
        cls,
        root: dict,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        at: str,
    ):
        db: InfrahubDatabase = info.context.get("infrahub_database")

        node_class = Node
        if cls._meta.schema.kind in registry.node:
            node_class = registry.node[cls._meta.schema.kind]

        try:
            obj = await node_class.init(db=db, schema=cls._meta.schema, branch=branch, at=at)
            await obj.new(db=db, **data)
            await cls.validate_constraints(db=db, node=obj, branch=branch)

            async with db.start_transaction() as db:
                await obj.save(db=db)

        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

        fields = await extract_fields(info.field_nodes[0].selection_set)
        ok = True

        return obj, cls(object=await obj.to_graphql(db=db, fields=fields.get("object", {})), ok=ok)

    @classmethod
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
        db: InfrahubDatabase = database or info.context.get("infrahub_database")
        account_session: AccountSession = info.context.get("account_session", None)

        obj = node or await NodeManager.get_one_by_id_or_default_filter(
            db=db,
            schema_name=cls._meta.schema.kind,
            id=data.get("id"),
            branch=branch,
            at=at,
            include_owner=True,
            include_source=True,
        )

        try:
            await obj.from_graphql(db=db, data=data)

            # Check if the new object is conform with the uniqueness constraints
            for unique_attr in cls._meta.schema.unique_attributes:
                attr = getattr(obj, unique_attr.name)
                nodes = await NodeManager.query(
                    schema=cls._meta.schema,
                    filters={f"{unique_attr.name}__value": attr.value},
                    fields={},
                    db=db,
                    branch=branch,
                    at=at,
                )
                if [node for node in nodes if node.id != obj.id]:
                    raise ValidationError(
                        {unique_attr.name: f"An object already exist with this value: {unique_attr.name}: {attr.value}"}
                    )
            node_id = data.pop("id", obj.id)
            fields = list(data.keys())
            validate_mutation_permissions_update_node(
                operation=cls.__name__, node_id=node_id, account_session=account_session, fields=fields
            )

            if db.is_transaction:
                await obj.save(db=db)
            else:
                async with db.start_transaction() as dbt:
                    await obj.save(db=dbt)

        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

        ok = True

        fields = await extract_fields(info.field_nodes[0].selection_set)

        return obj, cls(object=await obj.to_graphql(db=db, fields=fields.get("object", {})), ok=ok)

    @classmethod
    async def mutate_upsert(
        cls,
        root: dict,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        at: str,
        database: Optional[InfrahubDatabase] = None,
    ):
        schema_name = cls._meta.schema.kind
        node_schema = registry.get_node_schema(name=schema_name, branch=branch)
        db: InfrahubDatabase = database or info.context.get("infrahub_database")

        node_by_id = await _get_node_by_id(node_schema=node_schema, db=db, data=data, branch=branch, at=at)
        node_by_default_filter = await _get_node_by_default_filter(
            node_schema=node_schema, db=db, data=data, branch=branch, at=at
        )

        node = node_by_id or node_by_default_filter

        if node:
            updated_obj, mutation = await cls.mutate_update(root, info, data, branch, at, database, node)
            return updated_obj, mutation, False
        created_obj, mutation = await cls.mutate_create(root, info, data, branch, at)
        return created_obj, mutation, True

    @classmethod
    async def mutate_delete(
        cls,
        root,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        at: str,
    ):
        db: InfrahubDatabase = info.context.get("infrahub_database")

        if not (obj := await NodeManager.get_one(db=db, id=data.get("id"), branch=branch, at=at)):
            raise NodeNotFound(branch, cls._meta.schema.kind, data.get("id"))

        async with db.start_transaction() as db:
            await obj.delete(db=db, at=at)

        ok = True

        return obj, cls(ok=ok)

    @classmethod
    async def validate_constraints(cls, db: InfrahubDatabase, node: Node, branch: Optional[str] = None) -> None:
        """Check if the new object is conform with the uniqueness constraints."""
        for unique_attr in cls._meta.schema.unique_attributes:
            attr = getattr(node, unique_attr.name)
            nodes = await NodeManager.query(
                schema=cls._meta.schema,
                filters={f"{unique_attr.name}__value": attr.value},
                fields={},
                db=db,
                branch=branch,
            )
            if nodes:
                raise ValidationError(
                    {unique_attr.name: f"An object already exist with this value: {unique_attr.name}: {attr.value}"}
                )


class InfrahubMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(cls, schema: NodeSchema = None, _meta=None, **options):  # pylint: disable=arguments-differ
        # Make sure schema is a valid NodeSchema Node Class
        if not isinstance(schema, NodeSchema):
            raise ValueError(f"You need to pass a valid NodeSchema in '{cls.__name__}.Meta', received '{schema}'")

        if not _meta:
            _meta = InfrahubMutationOptions(cls)

        _meta.schema = schema

        super().__init_subclass_with_meta__(_meta=_meta, **options)


async def _get_node_by_default_filter(
    node_schema: NodeSchema,
    db: InfrahubDatabase,
    data: InputObjectType,
    branch: Branch,
    at: str,
) -> Optional[Node]:
    node = None
    default_filter_value = None
    if not node_schema.default_filter:
        return node
    this_datum = data
    for filter_key in node_schema.default_filter.split("__"):
        if filter_key not in this_datum:
            break
        this_datum = this_datum[filter_key]
    default_filter_value = this_datum
    if not default_filter_value:
        return node
    nodes = await NodeManager.query(
        db=db,
        schema=node_schema,
        limit=2,
        filters={node_schema.default_filter: default_filter_value},
        branch=branch,
        at=at,
    )
    if len(nodes) > 1:
        raise NodeNotFound(
            branch_name=branch.name,
            node_type=node_schema.kind,
            identifier=default_filter_value,
            message=f"Unable to find node {default_filter_value!r}, {len(nodes)} nodes returned, expected 1",
        )
    if len(nodes) == 1:
        node = nodes[0]
    return node


async def _get_node_by_id(
    node_schema: NodeSchema,
    db: InfrahubDatabase,
    data: InputObjectType,
    branch: Branch,
    at: str,
) -> Optional[Node]:
    node = None
    if "id" not in data:
        return node
    node = await NodeManager.get_one(id=data["id"], db=db, at=at, branch=branch)
    if node and node.get_kind() != node_schema.kind:
        raise NodeNotFound(
            branch_name=branch.name,
            node_type=node_schema.kind,
            identifier=data["id"],
            message=f"Node with id {data['id']} exists, but it is a {node.get_kind()}, not {node_schema.kind}",
        )
    return node
