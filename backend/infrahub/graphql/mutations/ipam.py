import ipaddress
from ipaddress import IPv4Interface
from typing import TYPE_CHECKING, Any, Optional

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
from infrahub.graphql.mutations.node_getter.interface import MutationNodeGetterInterface
from infrahub.lock import InfrahubMultiLock, build_object_lock_name
from infrahub.log import get_logger

from .main import InfrahubMutationMixin, InfrahubMutationOptions

if TYPE_CHECKING:
    from infrahub.graphql.initialization import GraphqlContext

log = get_logger()


async def validate_namespace(
    db: InfrahubDatabase,
    branch: Branch | str | None,
    data: InputObjectType,
    existing_namespace_id: Optional[str] = None,
) -> str:
    """Validate or set (if not present) the namespace to pass to the mutation and return its ID."""
    namespace_id: Optional[str] = None
    if "ip_namespace" not in data or not data["ip_namespace"]:
        namespace_id = existing_namespace_id or registry.default_ipnamespace
        data["ip_namespace"] = {"id": namespace_id}
    elif "id" in data["ip_namespace"]:
        namespace = await registry.manager.get_one(
            db=db, branch=branch, kind=InfrahubKind.IPNAMESPACE, id=data["ip_namespace"]["id"]
        )
        namespace_id = namespace.id
    else:
        raise ValidationError(
            "A valid ip_namespace must be provided or ip_namespace should be left empty in order to use the default value."
        )
    return namespace_id


class InfrahubIPNamespaceMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(  # pylint: disable=arguments-differ
        cls,
        schema: NodeSchema,
        _meta: Optional[Any] = None,
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
    ):
        if data["id"] == registry.default_ipnamespace:
            raise ValueError("Cannot delete default IPAM namespace")

        return await super().mutate_delete(info=info, data=data, branch=branch)


class InfrahubIPAddressMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(  # pylint: disable=arguments-differ
        cls,
        schema: NodeSchema,
        _meta: Optional[Any] = None,
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
    def _get_lock_name(namespace_id: str, branch: Branch) -> str | None:
        if not branch.is_default:
            # Do not lock on other branches as reconciliation will be performed at least when merging in main branch.
            return None
        return build_object_lock_name(InfrahubKind.IPADDRESS + "_" + namespace_id)

    @classmethod
    async def _mutate_create_object_and_reconcile(
        cls,
        data: InputObjectType,
        branch: Branch,
        db: InfrahubDatabase,
        ip_address: IPv4Interface | ipaddress.IPv6Interface,
        namespace_id: str,
    ) -> Node:
        address = await cls.mutate_create_object(data=data, db=db, branch=branch)
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
        database: Optional[InfrahubDatabase] = None,
    ) -> tuple[Node, Self]:
        context: GraphqlContext = info.context
        db = database or context.db
        ip_address = ipaddress.ip_interface(data["address"]["value"])
        namespace_id = await validate_namespace(db=db, branch=branch, data=data)

        async with db.start_transaction() as dbt:
            if lock_name := cls._get_lock_name(namespace_id, branch):
                async with InfrahubMultiLock(lock_registry=lock.registry, locks=[lock_name]):
                    reconciled_address = await cls._mutate_create_object_and_reconcile(
                        data=data, branch=branch, db=dbt, ip_address=ip_address, namespace_id=namespace_id
                    )
            else:
                reconciled_address = await cls._mutate_create_object_and_reconcile(
                    data=data, branch=branch, db=dbt, ip_address=ip_address, namespace_id=namespace_id
                )
            result = await cls.mutate_create_to_graphql(info=info, db=dbt, obj=reconciled_address)

        return reconciled_address, result

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
        database: Optional[InfrahubDatabase] = None,
        node: Optional[Node] = None,
    ) -> tuple[Node, Self]:
        context: GraphqlContext = info.context
        db = database or context.db

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
        try:
            async with db.start_transaction() as dbt:
                if lock_name := cls._get_lock_name(namespace_id, branch):
                    async with InfrahubMultiLock(lock_registry=lock.registry, locks=[lock_name]):
                        reconciled_address = await cls._mutate_update_object_and_reconcile(
                            info=info, data=data, branch=branch, address=address, namespace_id=namespace_id, db=dbt
                        )
                else:
                    reconciled_address = await cls._mutate_update_object_and_reconcile(
                        info=info, data=data, branch=branch, address=address, namespace_id=namespace_id, db=dbt
                    )

                result = await cls.mutate_update_to_graphql(db=dbt, info=info, obj=reconciled_address)
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

        return address, result

    @classmethod
    async def mutate_upsert(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        node_getters: list[MutationNodeGetterInterface],
        database: Optional[InfrahubDatabase] = None,
    ) -> tuple[Node, Self, bool]:
        context: GraphqlContext = info.context
        db = database or context.db

        await validate_namespace(db=db, branch=branch, data=data)
        prefix, result, created = await super().mutate_upsert(
            info=info, data=data, branch=branch, node_getters=node_getters, database=db
        )

        return prefix, result, created

    @classmethod
    async def mutate_delete(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
    ):
        return await super().mutate_delete(info=info, data=data, branch=branch)


class InfrahubIPPrefixMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(  # pylint: disable=arguments-differ
        cls,
        schema: NodeSchema,
        _meta: Optional[Any] = None,
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
    def _get_lock_name(namespace_id: str, branch: Branch) -> str | None:
        if not branch.is_default:
            # Do not lock on other branches as reconciliation will be performed at least when merging in main branch.
            return None
        return build_object_lock_name(InfrahubKind.IPPREFIX + "_" + namespace_id)

    @classmethod
    async def _mutate_create_object_and_reconcile(
        cls,
        data: InputObjectType,
        branch: Branch,
        db: InfrahubDatabase,
        namespace_id: str,
    ) -> Node:
        prefix = await cls.mutate_create_object(data=data, db=db, branch=branch)
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
        database: Optional[InfrahubDatabase] = None,
    ) -> tuple[Node, Self]:
        context: GraphqlContext = info.context
        db = database or context.db
        namespace_id = await validate_namespace(db=db, branch=branch, data=data)

        async with db.start_transaction() as dbt:
            if lock_name := cls._get_lock_name(namespace_id, branch):
                async with InfrahubMultiLock(lock_registry=lock.registry, locks=[lock_name]):
                    reconciled_prefix = await cls._mutate_create_object_and_reconcile(
                        data=data, branch=branch, db=dbt, namespace_id=namespace_id
                    )
            else:
                reconciled_prefix = await cls._mutate_create_object_and_reconcile(
                    data=data, branch=branch, db=dbt, namespace_id=namespace_id
                )

            result = await cls.mutate_create_to_graphql(info=info, db=dbt, obj=reconciled_prefix)

        return reconciled_prefix, result

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
        database: Optional[InfrahubDatabase] = None,
        node: Optional[Node] = None,
    ) -> tuple[Node, Self]:
        context: GraphqlContext = info.context
        db = database or context.db

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
        try:
            async with db.start_transaction() as dbt:
                if lock_name := cls._get_lock_name(namespace_id, branch):
                    async with InfrahubMultiLock(lock_registry=lock.registry, locks=[lock_name]):
                        reconciled_prefix = await cls._mutate_update_object_and_reconcile(
                            info=info, data=data, prefix=prefix, db=dbt, namespace_id=namespace_id, branch=branch
                        )
                else:
                    reconciled_prefix = await cls._mutate_update_object_and_reconcile(
                        info=info, data=data, prefix=prefix, db=dbt, namespace_id=namespace_id, branch=branch
                    )
                result = await cls.mutate_update_to_graphql(db=dbt, info=info, obj=reconciled_prefix)
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

        return prefix, result

    @classmethod
    async def mutate_upsert(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        node_getters: list[MutationNodeGetterInterface],
        database: Optional[InfrahubDatabase] = None,
    ):
        context: GraphqlContext = info.context
        db = database or context.db

        await validate_namespace(db=db, branch=branch, data=data)
        prefix, result, created = await super().mutate_upsert(
            info=info, data=data, branch=branch, node_getters=node_getters, database=db
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
    ) -> tuple[Node, Self]:
        context: GraphqlContext = info.context
        db = context.db

        prefix = await NodeManager.get_one(data.get("id"), context.db, branch=branch, prefetch_relationships=True)
        if not prefix:
            raise NodeNotFoundError(branch, cls._meta.schema.kind, data.get("id"))

        namespace_rels = await prefix.ip_namespace.get_relationships(db=db)
        namespace_id = namespace_rels[0].peer_id
        try:
            async with context.db.start_transaction() as dbt:
                if lock_name := cls._get_lock_name(namespace_id, branch):
                    async with InfrahubMultiLock(lock_registry=lock.registry, locks=[lock_name]):
                        reconciled_prefix = await cls._reconcile_prefix(
                            branch=branch, db=dbt, prefix=prefix, namespace_id=namespace_id, is_delete=True
                        )
                else:
                    reconciled_prefix = await cls._reconcile_prefix(
                        branch=branch, db=dbt, prefix=prefix, namespace_id=namespace_id, is_delete=True
                    )

        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

        ok = True

        return reconciled_prefix, cls(ok=ok)
