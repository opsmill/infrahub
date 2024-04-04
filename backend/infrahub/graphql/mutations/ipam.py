from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from graphene import InputObjectType, Mutation
from graphql import GraphQLResolveInfo
from typing_extensions import Self

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
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

        address, result = await super().mutate_create(root=root, info=info, data=data, branch=branch, at=at)

        if result.ok:
            prefix_data = await get_ip_prefix_for_ip_address(db=context.db, branch=branch, at=at, ip_address=address)
            if prefix_data:
                prefix_node = await NodeManager.get_one_by_id_or_default_filter(
                    db=context.db, id=prefix_data.id, schema_name=InfrahubKind.IPPREFIX, branch=context.branch, at=at
                )
                if not prefix_node:
                    raise ValueError(f"Unable to find the {InfrahubKind.IPPREFIX} {prefix_data.id}")

                await address.ip_prefix.update(db=context.db, data=prefix_node)
                await address.save(db=context.db)

                # FIXME: ValueError('Relationship has not been initialized')
                # prefix_node_addresses = await prefix_node.ip_addresses.get_peers(db=context.db)
                # prefix_node_addresses[address.id] = address
                await prefix_node.ip_addresses.update(db=context.db, data=address)
                await prefix_node.save(db=context.db)

        return address, result

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

        prefix, result = await super().mutate_create(root=root, info=info, data=data, branch=branch, at=at)

        if result.ok:
            # Find if a parent prefix exists in the database and add relationship if one does
            container_data = await get_container(db=context.db, branch=branch, at=at, ip_prefix=prefix)
            if container_data:
                container_node = await NodeManager.get_one_by_id_or_default_filter(
                    db=context.db, id=container_data.id, schema_name=InfrahubKind.IPPREFIX, branch=context.branch, at=at
                )
                if not container_node:
                    raise ValueError(f"Unable to find the {InfrahubKind.IPPREFIX} {container_data.id}")

                await prefix.parent.update(db=context.db, data=container_node)

            # Find if some children prefixes exist and add relationships if some do
            subnet_datas = await get_subnets(db=context.db, branch=branch, at=at, ip_prefix=prefix)
            subnet_nodes = []
            for subnet_data in subnet_datas:
                node = await NodeManager.get_one_by_id_or_default_filter(
                    db=context.db, id=subnet_data.id, schema_name=InfrahubKind.IPPREFIX, branch=context.branch, at=at
                )
                if not node:
                    raise ValueError(f"Unable to find the {InfrahubKind.IPPREFIX} {subnet_data.id}")

                await node.parent.delete(db=context.db)
                await node.parent.update(db=context.db, data=prefix)
                await node.save(db=context.db)
                subnet_nodes.append(node)

            await prefix.children.update(db=context.db, data=subnet_nodes)

            # Find if some IP addresses fit into the prefix and add relationships if some do
            address_datas = await get_ip_addresses(db=context.db, branch=branch, at=at, ip_prefix=prefix)
            address_nodes = []
            for address_data in address_datas:
                node = await NodeManager.get_one_by_id_or_default_filter(
                    db=context.db, id=address_data.id, schema_name=InfrahubKind.IPPREFIX, branch=context.branch, at=at
                )
                if not node:
                    raise ValueError(f"Unable to find the {InfrahubKind.IPADDRESS} {address_data.id}")

                # Set container prefix on each address
                current_prefix = await node.ip_prefix.get_peer(db=context.db)
                if not current_prefix or current_prefix.prefix.prefixlen < prefix.prefix.prefixlen:
                    await node.ip_prefix.delete(db=context.db)
                    await node.ip_prefix.update(db=context.db, data=prefix)
                    await node.save(db=context.db)

                    if current_prefix and node.id in await current_prefix.ip_addresses.get_peers(db=context.db):
                        await current_prefix.ip_addresses.remove(db=context.db, update_db=True, peer_id=node.id)
                address_nodes.append(node)

            # Set prefix' addresses
            await prefix.ip_addresses.update(db=context.db, data=address_nodes)
            await prefix.save(db=context.db)

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

        prefix = await NodeManager.get_one(db=context.db, id=data.get("id"), branch=branch, at=at)
        if not prefix:
            raise NodeNotFoundError(branch, cls._meta.schema.kind, data.get("id"))

        # Attach children to the current parent of the node before deleting the node
        node_parent = await prefix.parent.get_peer(db=context.db)
        if node_parent:
            node_children = await prefix.children.get_peers(db=context.db)
            for child in node_children.values():
                await node_parent.children.update(db=context.db, data=child)
            await node_parent.children.save(db=context.db)

        # Proceed to node deletion
        prefix, result = await super().mutate_delete(root=root, info=info, data=data, branch=branch, at=at)

        return prefix, result
