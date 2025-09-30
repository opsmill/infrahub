import ipaddress
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
from infrahub.core.node.create import get_profile_ids
from infrahub.core.schema import NodeSchema
from infrahub.database import InfrahubDatabase, retry_db_transaction
from infrahub.exceptions import NodeNotFoundError, ValidationError
from infrahub.lock import InfrahubMultiLock, build_object_lock_name
from infrahub.log import get_logger

from ...lock_getter import get_lock_names_on_object_mutation
from .main import DeleteResult, InfrahubMutationMixin, InfrahubMutationOptions
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
            db=db, branch=branch, kind=InfrahubKind.IPNAMESPACE, hfid=data["ip_namespace"]["hfid"]
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
        ip_address: ipaddress.IPv4Interface | ipaddress.IPv6Interface,
        namespace_id: str,
    ) -> Node:
        address = await cls.mutate_create_object(data=data, db=db, branch=branch)
        reconciler = IpamReconciler(db=db, branch=branch)

        if lock_name := cls._get_lock_name(namespace_id, branch):
            async with InfrahubMultiLock(lock_registry=lock.registry, locks=[lock_name]):
                reconciled_address = await reconciler.reconcile(
                    ip_value=ip_address, namespace=namespace_id, node_uuid=address.get_id()
                )
        else:
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

        async with db.start_transaction() as dbt:
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
        fields_to_validate: list[str],
        fields: list[str],
        previous_profile_ids: set[str],
        lock_names: list[str],
    ) -> Node:
        address = await cls.mutate_update_object(
            db=db,
            info=info,
            data=data,
            branch=branch,
            obj=address,
            fields_to_validate=fields_to_validate,
            fields=fields,
            previous_profile_ids=previous_profile_ids,
            lock_names=lock_names,
            manage_lock=False,
            apply_data=False,
        )
        reconciler = IpamReconciler(db=db, branch=branch)
        ip_address = ipaddress.ip_interface(address.address.value)
        if lock_name := cls._get_lock_name(namespace_id, branch):
            async with InfrahubMultiLock(lock_registry=lock.registry, locks=[lock_name]):
                reconciled_address = await reconciler.reconcile(
                    ip_value=ip_address, node_uuid=address.get_id(), namespace=namespace_id
                )
        else:
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

        before_mutate_profile_ids = await get_profile_ids(db=db, obj=address)
        await address.from_graphql(db=db, data=data)
        fields_to_validate = list(data)
        fields = list(data.keys())

        for field_to_remove in ("id", "hfid"):
            if field_to_remove in fields:
                fields.remove(field_to_remove)

        schema_branch = db.schema.get_schema_branch(name=branch.name)
        lock_names = get_lock_names_on_object_mutation(node=address, branch=branch, schema_branch=schema_branch)

        async with InfrahubMultiLock(lock_registry=lock.registry, locks=lock_names):
            async with db.start_transaction() as dbt:
                reconciled_address = await cls._mutate_update_object_and_reconcile(
                    info=info,
                    data=data,
                    branch=branch,
                    db=dbt,
                    address=address,
                    namespace_id=namespace_id,
                    fields_to_validate=fields_to_validate,
                    fields=fields,
                    previous_profile_ids=before_mutate_profile_ids,
                    lock_names=lock_names,
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
    def _get_lock_name(namespace_id: str) -> str | None:
        # IPPrefix has some cardinality-one relationships involved (parent/child/ip_address),
        # so we need to lock on any branch to avoid creating multiple peers for these relationships
        # during concurrent ipam reconciliations.
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
        database: InfrahubDatabase | None = None,
    ) -> tuple[Node, Self]:
        graphql_context: GraphqlContext = info.context
        db = database or graphql_context.db
        namespace_id = await validate_namespace(db=db, branch=branch, data=data)

        async with db.start_transaction() as dbt:
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
        fields_to_validate: list[str],
        fields: list[str],
        previous_profile_ids: set[str],
        lock_names: list[str],
    ) -> Node:
        prefix = await cls.mutate_update_object(
            db=db,
            info=info,
            data=data,
            branch=branch,
            obj=prefix,
            fields_to_validate=fields_to_validate,
            fields=fields,
            previous_profile_ids=previous_profile_ids,
            lock_names=lock_names,
            manage_lock=False,
            apply_data=False,
        )
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

        before_mutate_profile_ids = await get_profile_ids(db=db, obj=prefix)
        await prefix.from_graphql(db=db, data=data)
        fields_to_validate = list(data)
        fields = list(data.keys())

        for field_to_remove in ("id", "hfid"):
            if field_to_remove in fields:
                fields.remove(field_to_remove)

        schema_branch = db.schema.get_schema_branch(name=branch.name)
        lock_names = get_lock_names_on_object_mutation(node=prefix, branch=branch, schema_branch=schema_branch)

        async with InfrahubMultiLock(lock_registry=lock.registry, locks=lock_names):
            async with db.start_transaction() as dbt:
                reconciled_prefix = await cls._mutate_update_object_and_reconcile(
                    info=info,
                    data=data,
                    branch=branch,
                    db=dbt,
                    prefix=prefix,
                    namespace_id=namespace_id,
                    fields_to_validate=fields_to_validate,
                    fields=fields,
                    previous_profile_ids=before_mutate_profile_ids,
                    lock_names=lock_names,
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
        if lock_name := cls._get_lock_name(namespace_id):
            async with InfrahubMultiLock(lock_registry=lock.registry, locks=[lock_name]):
                reconciled_prefix = await reconciler.reconcile(
                    ip_value=ip_network, node_uuid=prefix.get_id(), namespace=namespace_id, is_delete=is_delete
                )
        else:
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

        async with graphql_context.db.start_transaction() as dbt:
            reconciled_prefix = await cls._reconcile_prefix(
                branch=branch, db=dbt, prefix=prefix, namespace_id=namespace_id, is_delete=True
            )
        ok = True

        return DeleteResult(node=reconciled_prefix, mutation=cls(ok=ok))
