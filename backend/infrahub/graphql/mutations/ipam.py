import ipaddress
from ipaddress import IPv4Interface
from typing import TYPE_CHECKING, Any

from graphene import InputObjectType, Mutation
from graphql import GraphQLResolveInfo
from typing_extensions import Self

from infrahub import lock
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.ipam.reconciler import IpamReconciler
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.database import InfrahubDatabase, retry_db_transaction
from infrahub.exceptions import NodeNotFoundError, ValidationError
from infrahub.lock import InfrahubMultiLock
from infrahub.log import get_logger

from ...core.node.create import create_node
from ...core.node.lock_utils import build_object_lock_name, get_lock_names_on_object_mutation
from .main import DeleteResult, InfrahubMutationMixin, InfrahubMutationOptions, build_graphql_response
from .node_getter.by_default_filter import MutationNodeGetterByDefaultFilter

if TYPE_CHECKING:
    from infrahub.graphql.initialization import GraphqlContext

log = get_logger()


async def validate_namespace(
    db: InfrahubDatabase,
    branch: Branch | str | None,
    data: InputObjectType,
    existing_namespace_id: str | None = None,
) -> str:
    """Validate or set (if not present) the namespace to pass to the mutation and return its ID."""
    namespace_id: str | None = None
    if "ip_namespace" not in data or not data["ip_namespace"]:
        namespace_id = existing_namespace_id or registry.default_ipnamespace
        data["ip_namespace"] = {"id": namespace_id}
    elif "id" in data["ip_namespace"]:
        namespace = await registry.manager.get_one(
            db=db, branch=branch, kind=InfrahubKind.IPNAMESPACE, id=data["ip_namespace"]["id"]
        )
        namespace_id = namespace.id
    elif "hfid" in data["ip_namespace"]:
        namespace = await registry.manager.get_one_by_hfid(
            db=db, branch=branch, kind=InfrahubKind.IPNAMESPACE, hfid=data["ip_namespace"]["hfid"], raise_on_error=True
        )
        namespace_id = namespace.id
    else:
        raise ValidationError(
            "A valid ip_namespace must be provided or ip_namespace should be left empty in order to use the default value."
        )
    return namespace_id


class InfrahubIPNamespaceMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(
        cls,
        schema: NodeSchema,
        _meta: Any | None = None,
        **options: dict[str, Any],
    ) -> None:
        # Make sure schema is a valid NodeSchema Node Class
        if not isinstance(schema, NodeSchema):
            raise ValueError(f"You need to pass a valid NodeSchema in '{cls.__name__}.Meta', received '{schema}'")

        if not _meta:
            _meta = InfrahubMutationOptions(cls)
        _meta.schema = schema

        super().__init_subclass_with_meta__(_meta=_meta, **options)

    @classmethod
    async def mutate_delete(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
    ) -> DeleteResult:
        if data["id"] == registry.default_ipnamespace:
            raise ValueError("Cannot delete default IPAM namespace")

        return await super().mutate_delete(info=info, data=data, branch=branch)


class InfrahubIPAddressMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(
        cls,
        schema: NodeSchema,
        _meta: Any | None = None,
        **options: dict[str, Any],
    ) -> None:
        # Make sure schema is a valid NodeSchema Node Class
        if not isinstance(schema, NodeSchema):
            raise ValueError(f"You need to pass a valid NodeSchema in '{cls.__name__}.Meta', received '{schema}'")

        if not _meta:
            _meta = InfrahubMutationOptions(cls)
        _meta.schema = schema

        super().__init_subclass_with_meta__(_meta=_meta, **options)

    @staticmethod
    def _get_lock_names(namespace_id: str, branch: Branch) -> list[str]:
        if not branch.is_default:
            # Do not lock on other branches as reconciliation will be performed at least when merging in main branch.
            return []
        return [build_object_lock_name(InfrahubKind.IPADDRESS + "_" + namespace_id)]

    @classmethod
    async def _mutate_create_object_and_reconcile(
        cls,
        data: InputObjectType,
        branch: Branch,
        db: InfrahubDatabase,
        ip_address: IPv4Interface | ipaddress.IPv6Interface,
        namespace_id: str,
    ) -> Node:
        address = await create_node(
            data=dict(data),
            db=db,
            branch=branch,
            schema=cls._meta.active_schema,
        )

        reconciler = IpamReconciler(db=db, branch=branch)
        reconciled_address = await reconciler.reconcile(
            ip_value=ip_address, namespace=namespace_id, node_uuid=address.get_id()
        )
        return reconciled_address

    @classmethod
    @retry_db_transaction(name="ipaddress_create")
    async def mutate_create(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        database: InfrahubDatabase | None = None,
    ) -> tuple[Node, Self]:
        graphql_context: GraphqlContext = info.context
        db = database or graphql_context.db
        ip_address = ipaddress.ip_interface(data["address"]["value"])
        namespace_id = await validate_namespace(db=db, branch=branch, data=data)

        lock_names = cls._get_lock_names(namespace_id, branch)
        async with InfrahubMultiLock(lock_registry=lock.registry, locks=lock_names):
            async with db.start_transaction() as dbt:
                reconciled_address = await cls._mutate_create_object_and_reconcile(
                    data=data, branch=branch, db=dbt, ip_address=ip_address, namespace_id=namespace_id
                )
                graphql_response = await build_graphql_response(info=info, db=dbt, obj=reconciled_address)

        return reconciled_address, cls(**graphql_response)

    @classmethod
    async def _mutate_update_object_and_reconcile(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        db: InfrahubDatabase,
        address: Node,
        namespace_id: str,
    ) -> Node:
        address = await cls.mutate_update_object(db=db, info=info, data=data, branch=branch, obj=address)
        reconciler = IpamReconciler(db=db, branch=branch)
        ip_address = ipaddress.ip_interface(address.address.value)
        reconciled_address = await reconciler.reconcile(
            ip_value=ip_address, node_uuid=address.get_id(), namespace=namespace_id
        )
        return reconciled_address

    @classmethod
    @retry_db_transaction(name="ipaddress_update")
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

        address = node or await NodeManager.get_one_by_id_or_default_filter(
            db=db,
            kind=cls._meta.schema.kind,
            id=data.get("id"),
            branch=branch,
            include_owner=True,
            include_source=True,
        )
        namespace = await address.ip_namespace.get_peer(db)
        namespace_id = await validate_namespace(db=db, branch=branch, data=data, existing_namespace_id=namespace.id)

        # Prepare a clone to compute locks without triggering pool allocations
        preview_obj = await NodeManager.get_one_by_id_or_default_filter(
            db=db,
            kind=address.get_kind(),
            id=address.get_id(),
            branch=branch,
        )
        await preview_obj.from_graphql(db=db, data=data, process_pools=False)

        schema_branch = db.schema.get_schema_branch(name=branch.name)
        lock_names = get_lock_names_on_object_mutation(node=preview_obj, schema_branch=schema_branch)

        namespace_lock_names = cls._get_lock_names(namespace_id, branch)
        async with InfrahubMultiLock(lock_registry=lock.registry, locks=namespace_lock_names):
            # FIXME: do not lock when data does not contain uniqueness constraint fields or resource pool allocations
            async with InfrahubMultiLock(lock_registry=lock.registry, locks=lock_names, metrics=False):
                async with db.start_transaction() as dbt:
                    reconciled_address = await cls._mutate_update_object_and_reconcile(
                        info=info, data=data, branch=branch, address=address, namespace_id=namespace_id, db=dbt
                    )

                    result = await cls.mutate_update_to_graphql(db=dbt, info=info, obj=reconciled_address)

        return address, result

    @classmethod
    async def mutate_upsert(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        node_getter_default_filter: MutationNodeGetterByDefaultFilter,
        database: InfrahubDatabase | None = None,
    ) -> tuple[Node, Self, bool]:
        graphql_context: GraphqlContext = info.context
        db = database or graphql_context.db

        await validate_namespace(db=db, branch=branch, data=data)
        prefix, result, created = await super().mutate_upsert(
            info=info, data=data, branch=branch, node_getter_default_filter=node_getter_default_filter, database=db
        )

        return prefix, result, created

    @classmethod
    async def mutate_delete(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
    ) -> DeleteResult:
        return await super().mutate_delete(info=info, data=data, branch=branch)


class InfrahubIPPrefixMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(
        cls,
        schema: NodeSchema,
        _meta: Any | None = None,
        **options: dict[str, Any],
    ) -> None:
        # Make sure schema is a valid NodeSchema Node Class
        if not isinstance(schema, NodeSchema):
            raise ValueError(f"You need to pass a valid NodeSchema in '{cls.__name__}.Meta', received '{schema}'")

        if not _meta:
            _meta = InfrahubMutationOptions(cls)
        _meta.schema = schema

        super().__init_subclass_with_meta__(_meta=_meta, **options)

    @staticmethod
    def _get_lock_names(namespace_id: str) -> list[str]:
        # IPPrefix has some cardinality-one relationships involved (parent/child/ip_address),
        # so we need to lock on any branch to avoid creating multiple peers for these relationships
        # during concurrent ipam reconciliations.
        return [build_object_lock_name(InfrahubKind.IPPREFIX + "_" + namespace_id)]

    @classmethod
    async def _mutate_create_object_and_reconcile(
        cls,
        data: InputObjectType,
        branch: Branch,
        db: InfrahubDatabase,
        namespace_id: str,
    ) -> Node:
        prefix = await create_node(
            data=dict(data),
            db=db,
            branch=branch,
            schema=cls._meta.active_schema,
        )
        return await cls._reconcile_prefix(
            branch=branch, db=db, prefix=prefix, namespace_id=namespace_id, is_delete=False
        )

    @classmethod
    @retry_db_transaction(name="ipprefix_create")
    async def mutate_create(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        database: InfrahubDatabase | None = None,
    ) -> tuple[Node, Self]:
        graphql_context: GraphqlContext = info.context
        db = database or graphql_context.db
        namespace_id = await validate_namespace(db=db, branch=branch, data=data)

        lock_names = cls._get_lock_names(namespace_id)
        async with InfrahubMultiLock(lock_registry=lock.registry, locks=lock_names):
            async with db.start_transaction() as dbt:
                reconciled_prefix = await cls._mutate_create_object_and_reconcile(
                    data=data, branch=branch, db=dbt, namespace_id=namespace_id
                )

            graphql_response = await build_graphql_response(info=info, db=dbt, obj=reconciled_prefix)

        return reconciled_prefix, cls(**graphql_response)

    @classmethod
    async def _mutate_update_object_and_reconcile(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        db: InfrahubDatabase,
        prefix: Node,
        namespace_id: str,
    ) -> Node:
        prefix = await cls.mutate_update_object(db=db, info=info, data=data, branch=branch, obj=prefix)
        return await cls._reconcile_prefix(
            branch=branch, db=db, prefix=prefix, namespace_id=namespace_id, is_delete=False
        )

    @classmethod
    @retry_db_transaction(name="ipprefix_update")
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

        prefix = node or await NodeManager.get_one_by_id_or_default_filter(
            db=db,
            kind=cls._meta.schema.kind,
            id=data.get("id"),
            branch=branch,
            include_owner=True,
            include_source=True,
        )
        namespace = await prefix.ip_namespace.get_peer(db)
        namespace_id = await validate_namespace(db=db, branch=branch, data=data, existing_namespace_id=namespace.id)

        # Prepare a clone to compute locks without triggering pool allocations
        preview_obj = await NodeManager.get_one_by_id_or_default_filter(
            db=db,
            kind=prefix.get_kind(),
            id=prefix.get_id(),
            branch=branch,
        )
        await preview_obj.from_graphql(db=db, data=data, process_pools=False)

        schema_branch = db.schema.get_schema_branch(name=branch.name)
        lock_names = get_lock_names_on_object_mutation(node=preview_obj, schema_branch=schema_branch)

        namespace_lock_names = cls._get_lock_names(namespace_id)
        async with InfrahubMultiLock(lock_registry=lock.registry, locks=namespace_lock_names):
            async with InfrahubMultiLock(lock_registry=lock.registry, locks=lock_names, metrics=False):
                async with db.start_transaction() as dbt:
                    reconciled_prefix = await cls._mutate_update_object_and_reconcile(
                        info=info, data=data, prefix=prefix, db=dbt, namespace_id=namespace_id, branch=branch
                    )
                    result = await cls.mutate_update_to_graphql(db=dbt, info=info, obj=reconciled_prefix)

        return prefix, result

    @classmethod
    async def mutate_upsert(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        node_getter_default_filter: MutationNodeGetterByDefaultFilter,
        database: InfrahubDatabase | None = None,
    ) -> tuple[Node, Self, bool]:
        graphql_context: GraphqlContext = info.context
        db = database or graphql_context.db

        await validate_namespace(db=db, branch=branch, data=data)
        prefix, result, created = await super().mutate_upsert(
            info=info, data=data, branch=branch, node_getter_default_filter=node_getter_default_filter, database=db
        )

        return prefix, result, created

    @classmethod
    async def _reconcile_prefix(
        cls,
        branch: Branch,
        db: InfrahubDatabase,
        prefix: Node,
        namespace_id: str,
        is_delete: bool,
    ) -> Node:
        reconciler = IpamReconciler(db=db, branch=branch)
        ip_network = ipaddress.ip_network(prefix.prefix.value)
        reconciled_prefix = await reconciler.reconcile(
            ip_value=ip_network, node_uuid=prefix.get_id(), namespace=namespace_id, is_delete=is_delete
        )
        return reconciled_prefix

    @classmethod
    @retry_db_transaction(name="ipprefix_delete")
    async def mutate_delete(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
    ) -> DeleteResult:
        graphql_context: GraphqlContext = info.context
        db = graphql_context.db

        prefix = await NodeManager.get_one(
            data.get("id"), graphql_context.db, branch=branch, prefetch_relationships=True
        )
        if not prefix:
            raise NodeNotFoundError(branch, cls._meta.schema.kind, data.get("id"))

        namespace_rels = await prefix.ip_namespace.get_relationships(db=db)
        namespace_id = namespace_rels[0].peer_id

        lock_names = cls._get_lock_names(namespace_id)
        async with InfrahubMultiLock(lock_registry=lock.registry, locks=lock_names):
            async with graphql_context.db.start_transaction() as dbt:
                reconciled_prefix = await cls._reconcile_prefix(
                    branch=branch, db=dbt, prefix=prefix, namespace_id=namespace_id, is_delete=True
                )
        ok = True

        return DeleteResult(node=reconciled_prefix, mutation=cls(ok=ok))
