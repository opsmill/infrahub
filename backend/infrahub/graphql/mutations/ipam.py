import ipaddress
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from graphene import InputObjectType, Mutation
from graphql import GraphQLResolveInfo
from typing_extensions import Self

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.ipam import get_container, get_ip_addresses, get_ip_prefix_for_ip_address, get_subnets
from infrahub.core.schema import NodeSchema
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import NodeNotFoundError, ValidationError
from infrahub.graphql.mutations.node_getter.interface import MutationNodeGetterInterface
from infrahub.log import get_logger

from .main import InfrahubMutationMixin, InfrahubMutationOptions

if TYPE_CHECKING:
    from infrahub.graphql import GraphqlContext

log = get_logger()


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
    def forbid_managed_attributes(cls, data: InputObjectType) -> None:
        if "ip_prefix" in data:
            raise ValueError("Cannot set 'ip_prefix', attribute is managed automatically.")

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
        cls.forbid_managed_attributes(data)

        context: GraphqlContext = info.context
        db = database or context.db
        ip_address = ipaddress.ip_interface(data["address"]["value"])

        namespace_id: Optional[str] = None
        if "ip_namespace" not in data:
            data["ip_namespace"] = {"id": registry.default_ipnamespace}
            namespace_id = registry.default_ipnamespace
        elif "ip_namespace" in data and "id" in data["ip_namespace"]:
            namespace = await registry.manager.get_one_by_id_or_default_filter(
                db=db, schema_name=InfrahubKind.IPNAMESPACE, id=data["ip_namespace"]["id"]
            )
            namespace_id = namespace.id
        else:
            raise ValidationError(
                "A Valid ip_namespace must be provided or ip_namespace should be left empty in order to use the default value."
            )

        ip_network = await get_ip_prefix_for_ip_address(
            db=db, branch=branch, at=at, ip_address=ip_address, namespace=namespace_id
        )
        if ip_network:
            data["ip_prefix"] = {"id": ip_network.id}

        return await super().mutate_create(root=root, info=info, data=data, branch=branch, at=at, database=db)

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
        cls.forbid_managed_attributes(data)

        prefix, result = await super().mutate_update(
            root=root, info=info, data=data, branch=branch, at=at, database=database, node=node
        )

        if result.ok:
            # TODO
            # Find if a parent relationship already exists, create it if not, update it if incorrect
            pass

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
        cls.forbid_managed_attributes(data)

        prefix, result, created = await super().mutate_upsert(
            root=root, info=info, data=data, branch=branch, at=at, node_getters=node_getters, database=database
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
    def forbid_managed_attributes(cls, data: InputObjectType) -> None:
        managed_attributes = ["parent", "children", "ip_addresses"]

        for attr in managed_attributes:
            if attr in data:
                raise ValueError(f"Cannot set '{attr}', attribute is managed automatically.")

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
        cls.forbid_managed_attributes(data)

        context: GraphqlContext = info.context
        db = database or context.db
        ip_network = ipaddress.ip_network(data["prefix"]["value"])

        namespace_id: Optional[str] = None
        if "ip_namespace" not in data:
            data["ip_namespace"] = {"id": registry.default_ipnamespace}
            namespace_id = registry.default_ipnamespace
        elif "ip_namespace" in data and "id" in data["ip_namespace"]:
            namespace = await registry.manager.get_one_by_id_or_default_filter(
                db=db, schema_name=InfrahubKind.IPNAMESPACE, id=data["ip_namespace"]["id"]
            )
            namespace_id = namespace.id
        else:
            raise ValidationError(
                "A Valid ip_namespace must be provided or ip_namespace should be left empty in order to use the default value."
            )

        # Set supernet if found
        super_network = await get_container(db=db, branch=branch, at=at, ip_prefix=ip_network, namespace=namespace_id)
        if super_network:
            data["parent"] = {"id": super_network.id}

        # Set subnets if found
        sub_networks = await get_subnets(db=db, branch=branch, at=at, ip_prefix=ip_network, namespace=namespace_id)
        if sub_networks:
            data["children"] = [s.id for s in sub_networks]

        async with db.start_transaction() as dbt:
            prefix, result = await super().mutate_create(
                root=root, info=info, data=data, branch=branch, at=at, database=dbt
            )

            # Fix ip_prefix for addresses if needed
            addresses = await get_ip_addresses(
                db=dbt, branch=branch, at=at, ip_prefix=ip_network, namespace=namespace_id
            )
            for ip_address in addresses:
                node = await NodeManager.get_one(ip_address.id, dbt, branch=branch, at=at)
                node_prefix = await node.ip_prefix.get_peer(dbt)
                if not node_prefix or ip_network.prefixlen > ipaddress.ip_network(node_prefix.prefix.value).prefixlen:
                    # Change address' prefix only if none set or new one is more specific
                    await node.ip_prefix.update(prefix, dbt)
                    await node.ip_prefix.save(db=dbt)

        return prefix, result

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
        cls.forbid_managed_attributes(data)

        prefix, result = await super().mutate_update(
            root=root, info=info, data=data, branch=branch, at=at, database=database, node=node
        )

        if result.ok:
            # TODO
            # Find if a parent relationship already exists, create it if not, update it if incorrect
            # Find if children relationshps already exist, create them if not, update them if incorrect
            # Find if some IP addresses relationships already exist, create them if not, update them if incorrect
            pass

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
        cls.forbid_managed_attributes(data)

        prefix, result, created = await super().mutate_upsert(
            root=root, info=info, data=data, branch=branch, at=at, node_getters=node_getters, database=database
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
        context: GraphqlContext = info.context

        prefix = await NodeManager.get_one(
            data.get("id"), context.db, branch=branch, at=at, prefetch_relationships=True
        )
        if not prefix:
            raise NodeNotFoundError(branch, cls._meta.schema.kind, data.get("id"))

        # FIXME: ValueError: Relationship has not been initialized
        # Attach children to the current parent of the node before deleting the node
        # parent = await prefix.parent.get_peer(db=context.db)
        # if parent:
        #     children = await prefix.children.get_peers(db=context.db)
        #     await parent.children.update(db=context.db, data=children)
        #     await parent.children.save(db=context.db)

        # Proceed to node deletion
        prefix, result = await super().mutate_delete(root=root, info=info, data=data, branch=branch, at=at)

        return prefix, result
