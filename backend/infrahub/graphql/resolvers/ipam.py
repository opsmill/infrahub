from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING, Any

from graphql.type.definition import GraphQLNonNull
from netaddr import IPSet
from opentelemetry import trace

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.ipam.constants import PrefixMemberType
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import BuiltinIPNamespace, BuiltinIPPrefix
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.exceptions import ValidationError
from infrahub.graphql.parser import extract_selection
from infrahub.graphql.permissions import get_permissions

from ..models import OrderModel

if TYPE_CHECKING:
    from collections.abc import Sequence

    from graphql import GraphQLResolveInfo
    from pydantic import IPvAnyAddress, IPvAnyInterface, IPvAnyNetwork

    from infrahub.core.branch.models import Branch
    from infrahub.core.schema import NodeSchema
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.initialization import GraphqlContext
    from infrahub.graphql.models import OrderModel


def _ip_range_display_label(node: Node) -> str:
    """Return a human friendly summary of an IP range"""
    size = int(node.last_address.obj) - int(node.address.obj) + 1

    if size == 1:
        return "1 IP address available"
    if size <= 2**16:
        return f"{size} IP addresses available"
    return f"More than {2**16} IP addresses available"


def _ip_with_prefix_length(ip_address: IPvAnyAddress, ip_prefix: IPvAnyNetwork) -> IPvAnyInterface:
    """Convert an `IPAddress` object into an `IPInterface` one given a `IPNetwork`."""
    return ipaddress.ip_interface(f"{ip_address}/{ip_prefix.prefixlen}")


async def _build_ip_range_node(
    db: InfrahubDatabase,
    branch: Branch,
    schema: NodeSchema,
    address: IPvAnyAddress,
    last_address: IPvAnyAddress,
    ip_namespace: BuiltinIPNamespace,
    ip_prefix: BuiltinIPPrefix,
) -> Node:
    address_with_len = str(_ip_with_prefix_length(ip_address=address, ip_prefix=ip_prefix.prefix.obj))
    last_address_with_len = str(_ip_with_prefix_length(ip_address=last_address, ip_prefix=ip_prefix.prefix.obj))

    n = await Node.init(schema=schema, db=db, branch=branch)
    await n.new(
        db=db,
        address=address_with_len,
        last_address=last_address_with_len,
        description=f"Available IP range {address_with_len} - {last_address_with_len}",
        ip_namespace=ip_namespace,
        ip_prefix=ip_prefix,
    )
    return n


def _include_first_and_last_ips(ip_prefix: BuiltinIPPrefix) -> bool:
    if ip_prefix.prefix.version == 6 or ip_prefix.is_pool.value:
        return True

    return ip_prefix.member_type.value == PrefixMemberType.ADDRESS.value and ip_prefix.prefix.prefixlen == 31


async def _resolve_available_address_nodes(
    db: InfrahubDatabase,
    branch: Branch,
    prefix: BuiltinIPPrefix,
    existing_nodes: Sequence[Node],
    first_node_context: Node | None = None,
    last_node_context: Node | None = None,
) -> list[Node]:
    """Annotate a list of IP addresses node with available ranges within a prefix."""
    ip_prefix: IPvAnyNetwork = prefix.prefix.obj
    ip_namespace = await prefix.ip_namespace.get_peer(db=db, peer_type=BuiltinIPNamespace, raise_on_error=True)
    ip_range_schema = registry.get_node_schema(name=InfrahubKind.IPRANGEAVAILABLE, branch=branch)

    # Make sure nodes are ordered by addresses
    sorted_nodes = sorted(existing_nodes, key=lambda n: n.address.obj)
    prefix_first_address = (
        ip_prefix.network_address if _include_first_and_last_ips(ip_prefix=prefix) else ip_prefix.network_address + 1
    )
    prefix_last_address = (
        ip_prefix.broadcast_address
        if _include_first_and_last_ips(ip_prefix=prefix)
        else ip_prefix.broadcast_address - 1
    )

    if not sorted_nodes:
        return [
            await _build_ip_range_node(
                db=db,
                branch=branch,
                schema=ip_range_schema,
                address=prefix_first_address,
                last_address=prefix_last_address,
                ip_namespace=ip_namespace,
                ip_prefix=prefix,
            )
        ]

    first_address: IPvAnyAddress = prefix_first_address
    last_address: IPvAnyAddress = prefix_last_address

    # Use but exclude context addresses to avoid having them in the result
    if first_node_context:
        first_address = first_node_context.address.obj.ip + 1
    if last_node_context:
        last_address = last_node_context.address.obj.ip - 1

    with_available_ranges: list[Node] = []
    previous_address: IPvAnyAddress | None = None

    # Look for a gap at the beginning of the prefix
    if sorted_nodes[0].address.obj.ip > first_address:
        with_available_ranges.append(
            await _build_ip_range_node(
                db=db,
                branch=branch,
                schema=ip_range_schema,
                address=first_address,
                last_address=sorted_nodes[0].address.obj.ip - 1,
                ip_namespace=ip_namespace,
                ip_prefix=prefix,
            )
        )

    # Look for gaps between existing addresses
    for existing in sorted_nodes:
        current = existing.address.obj.ip
        if previous_address:
            if int(current) - int(previous_address) > 1:
                with_available_ranges.append(
                    await _build_ip_range_node(
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
            await _build_ip_range_node(
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


async def _resolve_available_prefix_nodes(
    db: InfrahubDatabase,
    branch: Branch,
    prefix: BuiltinIPPrefix,
    existing_nodes: Sequence[Node],
    first_node_context: Node | None = None,
    last_node_context: Node | None = None,
) -> list[Node]:
    """Annotate a list of IP prefixes node with available prefixes within a parent one."""
    ip_prefix_schema = registry.get_node_schema(name=InfrahubKind.IPPREFIXAVAILABLE, branch=branch)

    existing_prefixes = IPSet([n.prefix.value for n in existing_nodes])
    if first_node_context:
        existing_prefixes.add(first_node_context.prefix.value)
    if last_node_context:
        existing_prefixes.add(last_node_context.prefix.value)

    # Infer which prefixes are actually available
    available_prefixes = IPSet([prefix.prefix.value]) ^ existing_prefixes
    available_nodes: list[Node] = []

    # Turn them into nodes (without saving them in the database)
    for available_prefix in available_prefixes.iter_cidrs():
        p = ipaddress.ip_network(str(available_prefix))
        if (first_node_context and p < first_node_context.prefix.obj) or (
            last_node_context and p > last_node_context.prefix.obj
        ):
            continue

        node = await Node.init(schema=ip_prefix_schema, db=db, branch=branch)
        await node.new(
            db=db, prefix=str(available_prefix), ip_namespace=await prefix.ip_namespace.get_peer(db=db), parent=prefix
        )
        available_nodes.append(node)

    # Properly sort existing nodes with available prefixes
    with_available_prefixes = sorted(existing_nodes + available_nodes, key=lambda n: n.prefix.obj)

    if len(with_available_prefixes) > 1 or with_available_prefixes[0].prefix.obj != prefix.prefix.obj:
        return with_available_prefixes

    # If the only available prefix is the same as the container prefix, this means the container prefix is empty and we should therefore at least
    # offer two smaller prefixes allocatable within it
    available_nodes.clear()

    for subnet in prefix.prefix.obj.subnets():
        node = await Node.init(schema=ip_prefix_schema, db=db, branch=branch)
        await node.new(db=db, prefix=str(subnet), ip_namespace=await prefix.ip_namespace.get_peer(db=db), parent=prefix)
        available_nodes.append(node)

    return available_nodes


def _filter_kinds(nodes: list[Node], kinds: list[str], limit: int | None) -> list[Node]:
    filtered: list[Node] = []
    available_node_kinds = [InfrahubKind.IPPREFIXAVAILABLE, InfrahubKind.IPRANGEAVAILABLE]
    kinds_with_available = kinds + available_node_kinds

    limit_with_available = limit
    for node in nodes:
        if node.get_schema().kind not in kinds_with_available:
            continue
        # Adapt the limit of nodes to return by always including available ones
        if limit and node.get_schema().kind in available_node_kinds:
            limit_with_available += 1
        filtered.append(node)

    return filtered[:limit_with_available] if limit else filtered


async def _annotate_result(
    db: InfrahubDatabase,
    branch: Branch,
    resolve_available: bool,
    schema: NodeSchema | GenericSchema,
    parent_prefix: BuiltinIPPrefix | None,
    result: list[Node],
    first_node_context: Node | None = None,
    last_node_context: Node | None = None,
    kinds_to_filter: list[str] | None = None,
    limit: int | None = None,
) -> list[Node]:
    nodes: list[Node] = result

    if resolve_available and parent_prefix:
        if schema.is_ip_address:
            nodes = await _resolve_available_address_nodes(
                db=db,
                branch=branch,
                prefix=parent_prefix,
                existing_nodes=result,
                first_node_context=first_node_context,
                last_node_context=last_node_context,
            )
        else:
            nodes = await _resolve_available_prefix_nodes(
                db=db,
                branch=branch,
                prefix=parent_prefix,
                existing_nodes=result,
                first_node_context=first_node_context,
                last_node_context=last_node_context,
            )

    return _filter_kinds(nodes=nodes, kinds=kinds_to_filter, limit=limit) if kinds_to_filter else nodes


@trace.get_tracer(__name__).start_as_current_span("ipam_paginated_list_resolver")
async def ipam_paginated_list_resolver(  # noqa: PLR0915
    root: dict,  # noqa: ARG001
    info: GraphQLResolveInfo,
    offset: int | None = None,
    limit: int | None = None,
    order: OrderModel | None = None,
    partial_match: bool = False,
    **kwargs: dict[str, Any],
) -> dict[str, Any]:
    schema: NodeSchema | GenericSchema = (
        info.return_type.of_type.graphene_type._meta.schema
        if isinstance(info.return_type, GraphQLNonNull)
        else info.return_type.graphene_type._meta.schema
    )

    if not isinstance(schema, GenericSchema) or schema.kind not in [InfrahubKind.IPADDRESS, InfrahubKind.IPPREFIX]:
        raise ValidationError(f"{schema.kind} is not {InfrahubKind.IPADDRESS} or {InfrahubKind.IPPREFIX}")

    fields = await extract_selection(info=info, schema=schema)
    resolve_available = bool(kwargs.pop("include_available", False))
    kinds_to_filter: list[str] = kwargs.pop("kinds", [])  # type: ignore[assignment]

    for kind in kinds_to_filter:
        if kind not in schema.used_by:
            raise ValidationError(f"{kind} is not a node inheriting from {schema.kind}")

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

        parent_prefix: BuiltinIPPrefix | None = None
        if parent_prefix_id:
            parent_prefix = await NodeManager.get_one(
                db=db, kind=BuiltinIPPrefix, id=parent_prefix_id, at=graphql_context.at, branch=graphql_context.branch
            )

        first_node_context: Node | None = None
        fetch_first_node_context = False
        if offset is not None and offset > 0:
            offset -= 1
            fetch_first_node_context = True

        last_node_context: Node | None = None
        fetch_last_node_context = False
        if limit is not None and limit > 0:
            limit += 1
            fetch_last_node_context = True

        # Since we are going to narrow down the number of nodes in the end, we will query for a larger set (that can potentially include all kinds of
        # implementations) in the first place to make sure that we will fill in the page to its maximum
        query_limit = limit
        if kinds_to_filter and limit:
            query_limit *= len(schema.used_by)

        objs = []
        if edges or "hfid" in filters:
            objs = await NodeManager.query(
                db=db,
                schema=schema,
                filters=filters or None,
                fields=node_fields,
                at=graphql_context.at,
                branch=graphql_context.branch,
                limit=query_limit,
                offset=offset,
                account=graphql_context.account_session,
                include_source=True,
                include_owner=True,
                partial_match=partial_match,
                order=order,
            )

            if fetch_first_node_context and len(objs) > 2:
                first_node_context = objs[0]
                objs = objs[1:]
            if fetch_last_node_context and len(objs) >= limit >= 2:
                last_node_context = objs[-1]
                objs = objs[:-1]

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

        result = await _annotate_result(
            db=db,
            branch=graphql_context.branch,
            resolve_available=resolve_available,
            schema=schema,
            parent_prefix=parent_prefix,
            result=objs,
            first_node_context=first_node_context,
            last_node_context=last_node_context,
            kinds_to_filter=kinds_to_filter,
            limit=limit,
        )

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
                    obj_data["display_label"] = _ip_range_display_label(node=obj)

                objects.append({"node": obj_data})

            response["edges"] = objects

        return response
