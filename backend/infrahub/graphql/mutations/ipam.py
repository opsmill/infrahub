import ipaddress
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from graphene import InputObjectType, Mutation
from graphql import GraphQLResolveInfo
from typing_extensions import Self

from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.ipam import get_container, get_ip_addresses, get_ip_prefix_for_ip_address, get_subnets
from infrahub.core.schema import NodeSchema
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import NodeNotFoundError
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
        ip_address = ipaddress.ip_interface(data["address"]["value"])

        ip_network = await get_ip_prefix_for_ip_address(db=context.db, branch=branch, at=at, ip_address=ip_address)
        if ip_network:
            data["ip_prefix"] = {"id": ip_network.id}

        return await super().mutate_create(root=root, info=info, data=data, branch=branch, at=at)

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
        # context: GraphqlContext = info.context

        prefix, result = await super().mutate_update(root=root, info=info, data=data, branch=branch, at=at)

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
        # context: GraphqlContext = info.context

        prefix, result, created = await super().mutate_upsert(
            root=root, info=info, data=data, branch=branch, at=at, node_getters=node_getters
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
        ip_network = ipaddress.ip_network(data["prefix"]["value"])

        # Set supernet if found
        super_network = await get_container(db=context.db, branch=branch, at=at, ip_prefix=ip_network)
        if super_network:
            data["parent"] = {"id": super_network.id}

        # Set subnets if found
        sub_networks = await get_subnets(db=context.db, branch=branch, at=at, ip_prefix=ip_network)
        if sub_networks:
            data["children"] = [s.id for s in sub_networks]

        async with context.db.start_transaction() as dbt:
            prefix, result = await super().mutate_create(
                root=root, info=info, data=data, branch=branch, at=at, database=dbt
            )

            # Fix ip_prefix for addresses if needed
            for ip_address in await get_ip_addresses(db=dbt, branch=branch, at=at, ip_prefix=ip_network):
                node = await NodeManager.get_one(ip_address.id, dbt, branch=branch, at=at)
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
        # context: GraphqlContext = info.context

        prefix, result = await super().mutate_update(root=root, info=info, data=data, branch=branch, at=at)

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
        # context: GraphqlContext = info.context

        prefix, result, created = await super().mutate_upsert(
            root=root, info=info, data=data, branch=branch, at=at, node_getters=node_getters
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
