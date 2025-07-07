from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphql.type.definition import GraphQLNonNull
from netaddr import IPSet
from opentelemetry import trace

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.ipam.constants import PrefixMemberType
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.graphql.parser import extract_selection
from infrahub.graphql.permissions import get_permissions

from ..models import OrderModel

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo
    from pydantic import IPvAnyAddress, IPvAnyNetwork

    from infrahub.core.branch.models import Branch
    from infrahub.core.schema import NodeSchema
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.initialization import GraphqlContext
    from infrahub.graphql.models import OrderModel


def ip_range_display_label(node: Node) -> str:
    """Return a human friendly summary of an IP range"""
    size = int(node.last_address.obj) - int(node.address.obj) + 1

    if size == 1:
        return "1 IP address available"
    if size <= 2**16:
        return f"{size} IP addresses available"
    return "Many IP addresses available"


async def build_ip_range_node(
    db: InfrahubDatabase,
    branch: Branch,
    schema: NodeSchema,
    address: IPvAnyAddress,
    last_address: IPvAnyAddress,
    ip_namespace: Node,
    ip_prefix: Node,
) -> Node:
    n = await Node.init(schema=schema, db=db, branch=branch)
    await n.new(
        db=db,
        address=str(address),
        last_address=str(last_address),
        description=f"Available IP range {address} - {last_address}",
        ip_namespace=ip_namespace,
        ip_prefix=ip_prefix,
    )
    return n


def include_first_and_last_ips(ip_prefix: Node) -> bool:
    if ip_prefix.prefix.version == 6 or ip_prefix.is_pool.value:
        return True

    return ip_prefix.member_type.value == PrefixMemberType.ADDRESS.value and ip_prefix.prefix.prefixlen == 31


async def resolve_available_address_nodes(db: InfrahubDatabase, branch: Branch, prefix: Node) -> list[Node]:
    """Annotate a list of IP addresses node with available ranges within a prefix."""
    ip_prefix: IPvAnyNetwork = prefix.prefix.obj
    ip_namespace = await prefix.ip_namespace.get_peer(db=db)
    ip_range_schema = registry.get_node_schema(name=InfrahubKind.IPRANGEAVAILABLE, branch=branch)

    first_address: IPvAnyAddress = (
        ip_prefix.network_address if include_first_and_last_ips(ip_prefix=prefix) else ip_prefix.network_address + 1
    )
    last_address: IPvAnyAddress = (
        ip_prefix.broadcast_address if include_first_and_last_ips(ip_prefix=prefix) else ip_prefix.broadcast_address - 1
    )
    existing_addresses: list[Node] = sorted(
        [await r.get_peer(db=db) for r in await prefix.ip_addresses.get_relationships(db=db)],
        key=lambda a: a.address.obj,
    )

    if not existing_addresses:
        return [
            await build_ip_range_node(
                db=db,
                branch=branch,
                schema=ip_range_schema,
                address=first_address,
                last_address=last_address,
                ip_namespace=ip_namespace,
                ip_prefix=prefix,
            )
        ]

    with_available_ranges: list[Node] = []
    previous_address: IPvAnyAddress | None = None

    # Look for a gap at the beginning of the prefix
    if existing_addresses[0].address.obj.ip > first_address:
        with_available_ranges.append(
            await build_ip_range_node(
                db=db,
                branch=branch,
                schema=ip_range_schema,
                address=first_address,
                last_address=existing_addresses[0].address.obj.ip - 1,
                ip_namespace=ip_namespace,
                ip_prefix=prefix,
            )
        )

    # Look for gaps between existing addresses
    for existing in existing_addresses:
        current = existing.address.obj.ip
        if previous_address:
            if int(current) - int(previous_address) > 1:
                with_available_ranges.append(
                    await build_ip_range_node(
                        db=db,
                        branch=branch,
                        schema=ip_range_schema,
                        address=previous_address + 1,
                        last_address=current - 1,
                        ip_namespace=ip_namespace,
                        ip_prefix=prefix,
                    )
                )

        with_available_ranges.append(existing)
        previous_address = existing.address.obj.ip

    # Look for a gap at the end of the prefix
    if previous_address and previous_address < last_address:
        with_available_ranges.append(
            await build_ip_range_node(
                db=db,
                branch=branch,
                schema=ip_range_schema,
                address=previous_address + 1,
                last_address=last_address,
                ip_namespace=ip_namespace,
                ip_prefix=prefix,
            )
        )

    return with_available_ranges


async def resolve_available_prefix_nodes(db: InfrahubDatabase, branch: Branch, prefix: Node) -> list[Node]:
    """Annotate a list of IP prefixes node with available prefixes within a parent one."""
    # Fetch all the child prefixes of the current prefix to be sure not to return any of them as available ones
    children_prefixes: list[Node] = sorted(
        [await r.get_peer(db=db) for r in await prefix.children.get_relationships(db=db)],
        key=lambda a: a.prefix.obj,
    )

    # Infer which prefixes are actually available
    available_prefixes = IPSet([prefix.prefix.value]) ^ IPSet([c.prefix.value for c in children_prefixes])
    available_nodes: list[Node] = []

    # Turn them into nodes (without saving them in the database)
    for available_prefix in available_prefixes.iter_cidrs():
        node = await Node.init(schema=prefix.get_schema(), db=db, branch=branch)
        await node.new(
            db=db,
            prefix=str(available_prefix),
            ip_namespace=await prefix.ip_namespace.get_peer(db=db),
            parent=prefix,
            is_available=True,
        )
        available_nodes.append(node)

    # Return existing nodes with available prefixes properly sorted
    return sorted(children_prefixes + available_nodes, key=lambda n: n.prefix.obj)


@trace.get_tracer(__name__).start_as_current_span("ipam_paginated_list_resolver")
async def ipam_paginated_list_resolver(
    root: dict,  # noqa: ARG001
    info: GraphQLResolveInfo,
    offset: int | None = None,
    limit: int | None = None,
    order: OrderModel | None = None,
    partial_match: bool = False,
    **kwargs: dict[str, Any],
) -> dict[str, Any]:
    schema: NodeSchema = (
        info.return_type.of_type.graphene_type._meta.schema
        if isinstance(info.return_type, GraphQLNonNull)
        else info.return_type.graphene_type._meta.schema
    )

    fields = await extract_selection(info.field_nodes[0], schema=schema)
    resolve_available = kwargs.pop("include_available", False)

    graphql_context: GraphqlContext = info.context
    async with graphql_context.db.start_session(read_only=True) as db:
        response: dict[str, Any] = {"edges": []}
        filters = {
            key: value for key, value in kwargs.items() if ("__" in key and value is not None) or key in ("ids", "hfid")
        }

        edges = fields.get("edges", {})
        node_fields = edges.get("node", {})

        permission_set: dict[str, Any] | None = None
        permissions = (
            await get_permissions(schema=schema, graphql_context=graphql_context)
            if graphql_context.permissions
            else None
        )
        if fields.get("permissions"):
            response["permissions"] = permissions

        if permissions:
            for edge in permissions["edges"]:
                if edge["node"]["kind"] == schema.kind:
                    permission_set = edge["node"]

        parent_prefix_id = ""
        if schema.is_ip_address and "ip_prefix__ids" in filters:
            parent_prefix_id = next(iter(filters["ip_prefix__ids"]))
        if schema.is_ip_prefix and "parent__ids" in filters:
            parent_prefix_id = next(iter(filters["parent__ids"]))

        parent_prefix: Node | None = None
        if parent_prefix_id:
            parent_prefix = await NodeManager.get_one(
                db=db, id=parent_prefix_id, at=graphql_context.at, branch=graphql_context.branch
            )

        objs = []
        if edges or "hfid" in filters:
            objs = await NodeManager.query(
                db=db,
                schema=schema,
                filters=filters or None,
                fields=node_fields,
                at=graphql_context.at,
                branch=graphql_context.branch,
                limit=limit,
                offset=offset,
                account=graphql_context.account_session,
                include_source=True,
                include_owner=True,
                partial_match=partial_match,
                order=order,
            )

        if "count" in fields:
            if filters.get("hfid"):
                response["count"] = len(objs)
            else:
                response["count"] = await NodeManager.count(
                    db=db,
                    schema=schema,
                    filters=filters,
                    at=graphql_context.at,
                    branch=graphql_context.branch,
                    partial_match=partial_match,
                )

        result = []
        if resolve_available and parent_prefix:
            result = (
                await resolve_available_address_nodes(db=db, branch=graphql_context.branch, prefix=parent_prefix)
                if schema.is_ip_address
                else await resolve_available_prefix_nodes(db=db, branch=graphql_context.branch, prefix=parent_prefix)
            )
        else:
            result = objs

        if result:
            objects = []
            for obj in result:
                obj_data = await obj.to_graphql(
                    db=db,
                    fields=node_fields,
                    related_node_ids=graphql_context.related_node_ids,
                    permissions=permission_set,
                )

                # Override display label for available IP ranges
                if obj.get_schema().kind == InfrahubKind.IPRANGEAVAILABLE and "display_label" in obj_data:
                    obj_data["display_label"] = ip_range_display_label(node=obj)

                objects.append({"node": obj_data})

            response["edges"] = objects

        return response
