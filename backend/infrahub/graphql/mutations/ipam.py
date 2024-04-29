import ipaddress
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from graphene import InputObjectType, Mutation
from graphql import GraphQLResolveInfo
from typing_extensions import Self

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.ipam.reconciler import IpamReconciler
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import NodeNotFoundError, ValidationError
from infrahub.graphql.mutations.node_getter.interface import MutationNodeGetterInterface
from infrahub.log import get_logger

from .main import InfrahubMutationMixin, InfrahubMutationOptions

if TYPE_CHECKING:
    from infrahub.graphql import GraphqlContext

log = get_logger()


async def validate_namespace(
    db: InfrahubDatabase, data: InputObjectType, existing_namespace_id: Optional[str] = None
) -> str:
    """Validate or set (if not present) the namespace to pass to the mutation and return its ID."""
    namespace_id: Optional[str] = None
    if "ip_namespace" not in data or not data["ip_namespace"]:
        data["ip_namespace"] = {"id": registry.default_ipnamespace}
        namespace_id = existing_namespace_id or registry.default_ipnamespace
    elif "id" in data["ip_namespace"]:
        namespace = await registry.manager.get_one_by_id_or_default_filter(
            db=db, schema_name=InfrahubKind.IPNAMESPACE, id=data["ip_namespace"]["id"]
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
        **options: Dict[str, Any],
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
        root,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        at: str,
    ):
        if data["id"] == registry.default_ipnamespace:
            raise ValueError("Cannot delete default IPAM namespace")

        return await super().mutate_delete(root=root, info=info, data=data, branch=branch, at=at)


class InfrahubIPAddressMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(  # pylint: disable=arguments-differ
        cls,
        schema: NodeSchema,
        _meta: Optional[Any] = None,
        **options: Dict[str, Any],
    ) -> None:
        # Make sure schema is a valid NodeSchema Node Class
        if not isinstance(schema, NodeSchema):
            raise ValueError(f"You need to pass a valid NodeSchema in '{cls.__name__}.Meta', received '{schema}'")

        if not _meta:
            _meta = InfrahubMutationOptions(cls)
        _meta.schema = schema

        super().__init_subclass_with_meta__(_meta=_meta, **options)

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
        ip_address = ipaddress.ip_interface(data["address"]["value"])
        namespace_id = await validate_namespace(db=db, data=data)

        async with db.start_transaction() as dbt:
            address = await cls.mutate_create_object(data=data, db=dbt, branch=branch, at=at)
            reconciler = IpamReconciler(db=dbt, branch=branch)
            reconciled_address = await reconciler.reconcile(
                ip_value=ip_address, namespace=namespace_id, node_uuid=address.get_id()
            )

        result = await cls.mutate_create_to_graphql(info=info, db=db, obj=reconciled_address)

        return reconciled_address, result

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
    ) -> Tuple[Node, Self]:
        context: GraphqlContext = info.context
        db = database or context.db

        address = node or await NodeManager.get_one_by_id_or_default_filter(
            db=db,
            schema_name=cls._meta.schema.kind,
            id=data.get("id"),
            branch=branch,
            at=at,
            include_owner=True,
            include_source=True,
        )
        namespace = await address.ip_namespace.get_peer(db)
        namespace_id = await validate_namespace(db=db, data=data, existing_namespace_id=namespace.id)
        try:
            async with db.start_transaction() as dbt:
                address = await cls.mutate_update_object(db=dbt, info=info, data=data, branch=branch, obj=address)
                reconciler = IpamReconciler(db=dbt, branch=branch)
                ip_address = ipaddress.ip_interface(address.address.value)
                reconciled_address = await reconciler.reconcile(
                    ip_value=ip_address, node_uuid=address.get_id(), namespace=namespace_id
                )

                result = await cls.mutate_update_to_graphql(db=dbt, info=info, obj=reconciled_address)
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

        return address, result

    @classmethod
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
        context: GraphqlContext = info.context
        db = database or context.db

        await validate_namespace(db=db, data=data)
        prefix, result, created = await super().mutate_upsert(
            root=root, info=info, data=data, branch=branch, at=at, node_getters=node_getters, database=db
        )

        return prefix, result, created

    @classmethod
    async def mutate_delete(
        cls,
        root,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        at: str,
    ):
        return await super().mutate_delete(root=root, info=info, data=data, branch=branch, at=at)


class InfrahubIPPrefixMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(  # pylint: disable=arguments-differ
        cls,
        schema: NodeSchema,
        _meta: Optional[Any] = None,
        **options: Dict[str, Any],
    ) -> None:
        # Make sure schema is a valid NodeSchema Node Class
        if not isinstance(schema, NodeSchema):
            raise ValueError(f"You need to pass a valid NodeSchema in '{cls.__name__}.Meta', received '{schema}'")

        if not _meta:
            _meta = InfrahubMutationOptions(cls)
        _meta.schema = schema

        super().__init_subclass_with_meta__(_meta=_meta, **options)

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
        ip_network = ipaddress.ip_network(data["prefix"]["value"])
        namespace_id = await validate_namespace(db=db, data=data)

        async with db.start_transaction() as dbt:
            prefix = await cls.mutate_create_object(data=data, db=dbt, branch=branch, at=at)
            reconciler = IpamReconciler(db=dbt, branch=branch)
            reconciled_prefix = await reconciler.reconcile(
                ip_value=ip_network, namespace=namespace_id, node_uuid=prefix.get_id()
            )

        result = await cls.mutate_create_to_graphql(info=info, db=db, obj=reconciled_prefix)

        return reconciled_prefix, result

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
    ) -> Tuple[Node, Self]:
        context: GraphqlContext = info.context
        db = database or context.db

        prefix = node or await NodeManager.get_one_by_id_or_default_filter(
            db=db,
            schema_name=cls._meta.schema.kind,
            id=data.get("id"),
            branch=branch,
            at=at,
            include_owner=True,
            include_source=True,
        )
        namespace = await prefix.ip_namespace.get_peer(db)
        namespace_id = await validate_namespace(db=db, data=data, existing_namespace_id=namespace.id)
        try:
            async with db.start_transaction() as dbt:
                prefix = await cls.mutate_update_object(db=dbt, info=info, data=data, branch=branch, obj=prefix)
                reconciler = IpamReconciler(db=dbt, branch=branch)
                ip_network = ipaddress.ip_network(prefix.prefix.value)
                reconciled_prefix = await reconciler.reconcile(
                    ip_value=ip_network, node_uuid=prefix.get_id(), namespace=namespace_id
                )

                result = await cls.mutate_update_to_graphql(db=dbt, info=info, obj=reconciled_prefix)
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

        return prefix, result

    @classmethod
    async def mutate_upsert(
        cls,
        root: dict,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        at: str,
        node_getters: List[MutationNodeGetterInterface],
        database: Optional[InfrahubDatabase] = None,
    ):
        context: GraphqlContext = info.context
        db = database or context.db

        await validate_namespace(db=db, data=data)
        prefix, result, created = await super().mutate_upsert(
            root=root, info=info, data=data, branch=branch, at=at, node_getters=node_getters, database=db
        )

        return prefix, result, created

    @classmethod
    async def mutate_delete(
        cls,
        root,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        at: str,
    ) -> Tuple[Node, Self]:
        context: GraphqlContext = info.context
        db = context.db

        prefix = await NodeManager.get_one(
            data.get("id"), context.db, branch=branch, at=at, prefetch_relationships=True
        )
        if not prefix:
            raise NodeNotFoundError(branch, cls._meta.schema.kind, data.get("id"))

        namespace_rels = await prefix.ip_namespace.get_relationships(db=db)
        namespace_id = namespace_rels[0].peer_id
        try:
            async with context.db.start_transaction() as dbt:
                reconciler = IpamReconciler(db=dbt, branch=branch)
                ip_network = ipaddress.ip_network(prefix.prefix.value)
                reconciled_prefix = await reconciler.reconcile(
                    ip_value=ip_network, node_uuid=prefix.get_id(), namespace=namespace_id, is_delete=True
                )
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

        ok = True

        return reconciled_prefix, cls(ok=ok)
