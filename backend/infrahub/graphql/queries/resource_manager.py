from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, cast

from graphene import BigInt, Field, Float, Int, List, NonNull, ObjectType, String

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.ipam.utilization import PrefixUtilizationGetter
from infrahub.core.manager import NodeManager
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.query.ipam import IPPrefixUtilization
from infrahub.core.query.resource_manager import (
    IPAddressPoolGetIdentifiers,
    NumberPoolGetAllocated,
    PrefixPoolGetIdentifiers,
)
from infrahub.exceptions import NodeNotFoundError, SchemaNotFoundError, ValidationError
from infrahub.graphql.field_extractor import extract_graphql_fields
from infrahub.graphql.types.enums import PoolRecordProvenance
from infrahub.pools.number import NumberUtilizationGetter, UtilizationFigures
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.number_pool_space import SchemaAttributeDomains, to_pool_ranges
from infrahub.pools.number_ranges import EffectiveSpace

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.protocols import CoreNumberPoolRange
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.initialization import GraphqlContext
    from infrahub.pools.number_ranges import NumberDomain


class IPPoolUtilizationResource(ObjectType):
    id = Field(String, required=True, description="The ID of the current resource")
    display_label = Field(String, required=True, description="The common name of the resource")
    kind = Field(String, required=True, description="The resource kind")
    weight = Field(BigInt, required=True, description="The relative weight of this resource.")
    utilization = Field(Float, required=True, description="The overall utilization of the resource.")
    utilization_branches = Field(
        Float, required=True, description="The utilization of the resource on all non default branches."
    )
    utilization_default_branch = Field(
        Float, required=True, description="The overall utilization of the resource isolated to the default branch."
    )


class IPPrefixUtilizationEdge(ObjectType):
    node = Field(IPPoolUtilizationResource, required=True)


class PoolAllocatedNode(ObjectType):
    id = Field(String, required=True, description="The ID of the allocated node")
    display_label = Field(String, required=True, description="The common name of the resource")
    kind = Field(String, required=True, description="The node kind")
    branch = Field(String, required=True, description="The branch where the node is allocated")
    identifier = Field(String, required=False, description="Identifier used for the allocation")
    provenance = Field(
        PoolRecordProvenance,
        required=False,
        description="Whether the number pool allocated the value the branch holds or a user provided it; null for IP pools",
    )


class PoolAllocatedEdge(ObjectType):
    node = Field(PoolAllocatedNode, required=True)


def _validate_pool_type(pool_id: str, pool: Node | None = None) -> Node:
    if not pool or pool.get_kind() not in [
        InfrahubKind.IPADDRESSPOOL,
        InfrahubKind.IPPREFIXPOOL,
        InfrahubKind.NUMBERPOOL,
    ]:
        raise NodeNotFoundError(node_type="ResourcePool", identifier=pool_id)
    return pool


class PoolAllocated(ObjectType):
    count = Field(BigInt, required=True, description="The number of allocations within the selected pool.")
    edges = Field(List(of_type=NonNull(PoolAllocatedEdge), required=True), required=True)

    @staticmethod
    async def resolve(
        root: dict,  # noqa: ARG004
        info: GraphQLResolveInfo,
        pool_id: str,
        resource_id: str,
        offset: int = 0,
        limit: int = 10,
    ) -> dict:
        graphql_context: GraphqlContext = info.context
        pool = await NodeManager.get_one(id=pool_id, db=graphql_context.db, branch=graphql_context.branch)

        fields = extract_graphql_fields(info=info)

        allocated_kinds: list[str] = []
        pool = _validate_pool_type(pool_id=pool_id, pool=pool)
        match pool.get_kind():
            case InfrahubKind.NUMBERPOOL:
                return await resolve_number_pool_allocation(
                    db=graphql_context.db,
                    graphql_context=graphql_context,
                    domains=SchemaAttributeDomains(schema=graphql_context.db.schema, branch=graphql_context.branch),
                    pool=pool,
                    resource_id=resource_id,
                    fields=fields,
                    offset=offset,
                    limit=limit,
                )
            case InfrahubKind.IPPREFIXPOOL:
                allocated_kinds.append(InfrahubKind.IPPREFIX)
            case InfrahubKind.IPADDRESSPOOL:
                allocated_kinds.append(InfrahubKind.IPADDRESS)

        resources = await pool.resources.get_peers(db=graphql_context.db)  # type: ignore[attr-defined,union-attr]
        if resource_id not in resources:
            raise ValidationError(
                input_value=f"The selected pool_id={pool_id} doesn't contain the requested resource_id={resource_id}"
            )

        resource = resources[resource_id]

        query = await IPPrefixUtilization.init(
            db=graphql_context.db,
            at=graphql_context.at,
            branch=graphql_context.branch,
            ip_prefixes=[resource],
            allocated_kinds=allocated_kinds,
            offset=offset,
            limit=limit,
        )
        response: dict[str, Any] = {}
        if "count" in fields:
            response["count"] = await query.count(db=graphql_context.db)

        if edges := fields.get("edges"):
            await query.execute(db=graphql_context.db)

            node_fields = edges.get("node", {})

            nodes: list[dict[str, dict[str, str | None]]] = []
            for item in query.get_data():
                nodes.append(
                    {
                        "node": {
                            "id": item.child_uuid,
                            "kind": item.child_kind,
                            "branch": graphql_context.branch.name,
                            "display_label": item.ip_value,
                        }
                    }
                )

            if "identifier" in node_fields:
                allocated_ids = [node["node"]["id"] for node in nodes]
                identifier_query_map = {
                    InfrahubKind.IPADDRESSPOOL: IPAddressPoolGetIdentifiers,
                    InfrahubKind.IPPREFIXPOOL: PrefixPoolGetIdentifiers,
                }
                identifier_query_class = identifier_query_map.get(pool.get_kind())
                if not identifier_query_class:
                    raise ValidationError(input_value=f"This query doesn't get support {pool.get_kind()}")
                identifier_query = cast(
                    "IPAddressPoolGetIdentifiers | PrefixPoolGetIdentifiers",
                    await identifier_query_class.init(
                        db=graphql_context.db, at=graphql_context.at, pool_id=pool_id, allocated=allocated_ids
                    ),
                )
                await identifier_query.execute(db=graphql_context.db)

                reservations: dict[str, str] = {}
                for identifier_item in identifier_query.get_data():
                    reservations[identifier_item.allocated_uuid] = identifier_item.identifier

                for node in nodes:
                    node_id = cast("str", node["node"]["id"])
                    node["node"]["identifier"] = reservations.get(node_id)

            response["edges"] = nodes

        return response


class PoolUtilization(ObjectType):
    count = Field(BigInt, required=True, description="The number of resources within the selected pool.")
    utilization = Field(Float, required=True, description="The overall utilization of the pool.")
    utilization_branches = Field(Float, required=True, description="The utilization in all non default branches.")
    utilization_default_branch = Field(
        Float, required=True, description="The overall utilization of the pool isolated to the default branch."
    )
    edges = Field(List(of_type=NonNull(IPPrefixUtilizationEdge), required=True), required=True)

    @staticmethod
    async def resolve(
        root: dict,  # noqa: ARG004
        info: GraphQLResolveInfo,
        pool_id: str,
    ) -> dict:
        graphql_context: GraphqlContext = info.context
        db: InfrahubDatabase = graphql_context.db
        pool = await NodeManager.get_one(id=pool_id, db=db, branch=graphql_context.branch)
        pool = _validate_pool_type(pool_id=pool_id, pool=pool)
        if pool.get_kind() == "CoreNumberPool":
            return await resolve_number_pool_utilization(
                db=db,
                domains=SchemaAttributeDomains(schema=db.schema, branch=graphql_context.branch),
                at=graphql_context.at,
                pool=pool,
                branch=graphql_context.branch,
            )

        resources_map: dict[str, Node] = {}

        with contextlib.suppress(SchemaNotFoundError):
            resources_map = await pool.resources.get_peers(db=db, branch_agnostic=True)  # type: ignore[attr-defined,union-attr]

        default_branch = registry.get_branch_from_registry(branch=registry.default_branch)
        resources = list(resources_map.values())
        branch_getter = PrefixUtilizationGetter(
            db=db, ip_prefixes=resources, branch=graphql_context.branch, at=graphql_context.at
        )
        # Reuse the single-branch query when the request is already on the default branch,
        # otherwise the two getters cache independent result sets.
        default_branch_getter = (
            branch_getter
            if graphql_context.branch.name == default_branch.name
            else PrefixUtilizationGetter(db=db, ip_prefixes=resources, branch=default_branch, at=graphql_context.at)
        )
        fields = extract_graphql_fields(info=info)
        response: dict[str, Any] = {}
        total_utilization = None
        default_branch_utilization = None
        if "count" in fields:
            response["count"] = len(resources_map)
        if "utilization" in fields:
            response["utilization"] = total_utilization = await branch_getter.get_use_percentage()
        if "utilization_default_branch" in fields:
            response["utilization_default_branch"] = (
                default_branch_utilization
            ) = await default_branch_getter.get_use_percentage()
        if "utilization_branches" in fields:
            total_utilization = (
                total_utilization if total_utilization is not None else await branch_getter.get_use_percentage()
            )
            default_branch_utilization = (
                default_branch_utilization
                if default_branch_utilization is not None
                else await default_branch_getter.get_use_percentage()
            )
            # Deletions on the branch can make its view smaller than the default branch's;
            # this field is exposed as a non-negative percentage.
            response["utilization_branches"] = max(0.0, total_utilization - default_branch_utilization)
        if "edges" in fields:
            response["edges"] = []
            if "node" in fields["edges"]:
                node_fields = fields["edges"]["node"]
                for resource_id, resource_node in resources_map.items():
                    resource_total = None
                    default_branch_total = None
                    node_response: dict[str, str | float | int] = {}
                    if "id" in node_fields:
                        node_response["id"] = resource_id
                    if "kind" in node_fields:
                        node_response["kind"] = resource_node.get_kind()
                    if "display_label" in node_fields:
                        node_response["display_label"] = await resource_node.get_display_label(db=db)
                    if "weight" in node_fields:
                        node_response["weight"] = await resource_node.get_resource_weight(db=db)  # type: ignore[attr-defined]
                    if "utilization" in node_fields:
                        node_response["utilization"] = resource_total = await branch_getter.get_use_percentage(
                            ip_prefixes=[resource_node]
                        )
                    if "utilization_default_branch" in node_fields:
                        node_response["utilization_default_branch"] = (
                            default_branch_total
                        ) = await default_branch_getter.get_use_percentage(ip_prefixes=[resource_node])
                    if "utilization_branches" in node_fields:
                        resource_total = (
                            resource_total
                            if resource_total is not None
                            else await branch_getter.get_use_percentage(ip_prefixes=[resource_node])
                        )
                        default_branch_total = (
                            default_branch_total
                            if default_branch_total is not None
                            else await default_branch_getter.get_use_percentage(ip_prefixes=[resource_node])
                        )
                        node_response["utilization_branches"] = max(0.0, resource_total - default_branch_total)
                    response["edges"].append({"node": node_response})

        return response


def _pool_domain(domains: SchemaAttributeDomains, pool: Node) -> NumberDomain:
    return domains.domain_of(
        kind=str(pool.get_attribute("node").value), attribute_name=str(pool.get_attribute("node_attribute").value)
    )


async def resolve_number_pool_allocation(
    db: InfrahubDatabase,
    graphql_context: GraphqlContext,
    domains: SchemaAttributeDomains,
    pool: Node,
    resource_id: str,
    fields: dict,
    offset: int,
    limit: int,
) -> dict:
    """Returns the numbers the pool allocated, from all its ranges when `resource_id` is the pool, or from one range.

    Raises:
        ValidationError: when `resource_id` is neither the pool nor one of its ranges.

    """
    response: dict[str, Any] = {}
    ranges = await NumberPoolRepository(db=db).get_pool_ranges(pool_id=pool.get_id())
    if resource_id != pool.get_id():
        ranges = [pool_range for pool_range in ranges if pool_range.id == resource_id]
        if not ranges:
            raise ValidationError(
                input_value=f"The selected pool_id={pool.get_id()} doesn't contain the requested resource_id={resource_id}"
            )
    space = EffectiveSpace(ranges=ranges, domain=_pool_domain(domains=domains, pool=pool))
    if space.is_empty:
        if "count" in fields:
            response["count"] = 0
        if "edges" in fields:
            response["edges"] = []
        return response

    query = await NumberPoolGetAllocated.init(
        db=db,
        pool=pool,
        ranges=space.as_query_ranges(),
        offset=offset,
        limit=limit,
        branch=graphql_context.branch,
        branch_agnostic=True,
    )

    if "count" in fields:
        response["count"] = await query.count(db=db)

    if "edges" in fields:
        await query.execute(db=db)
        edges = []
        for item in query.get_data():
            node = {
                "node": {
                    "id": item.id,
                    "kind": pool.node.value,  # type: ignore[attr-defined]
                    "branch": item.branch,
                    "display_label": item.value,
                    "identifier": item.identifier,
                    "provenance": item.provenance,
                }
            }
            edges.append(node)

        response["edges"] = edges
    return response


async def _range_edge(db: InfrahubDatabase, range_node: CoreNumberPoolRange, figures: UtilizationFigures) -> dict:
    return {
        "node": {
            "id": range_node.get_id(),
            "kind": InfrahubKind.NUMBERPOOLRANGE,
            "display_label": await range_node.get_display_label(db=db),
            "weight": range_node.allocation_weight.value or 0,
            "utilization": figures.utilization,
            "utilization_default_branch": figures.utilization_default_branch,
            "utilization_branches": figures.utilization_branches,
        }
    }


async def resolve_number_pool_utilization(
    db: InfrahubDatabase, domains: SchemaAttributeDomains, pool: Node, at: Timestamp | str | None, branch: Branch
) -> dict:
    """Returns a mapping containing utilization info of a number pool.

    Every figure is a percentage of the effective space: the pool's ranges clipped to the target
    attribute's min and max, minus its excluded values. Pool totals measure the whole space and each
    range reports its own share of it underneath, so a range about to run out is visible on its own.
    """
    core_number_pool = await registry.manager.get_one_by_id_or_default_filter(db=db, id=pool.id, kind=CoreNumberPool)
    ranges = await NumberPoolRepository(db=db).get_ranges(pool_id=pool.get_id(), at=at)
    # The range nodes serve the edges too, so the space is built from the ones already read.
    space = EffectiveSpace(ranges=to_pool_ranges(ranges=ranges), domain=_pool_domain(domains=domains, pool=pool))
    number_pool = NumberUtilizationGetter(db=db, pool=core_number_pool, space=space, at=at, branch=branch)
    await number_pool.load_data()

    figures = number_pool.figures
    return {
        "count": len(ranges),
        "utilization": figures.utilization,
        "utilization_default_branch": figures.utilization_default_branch,
        "utilization_branches": figures.utilization_branches,
        "edges": [
            await _range_edge(
                db=db, range_node=range_node, figures=number_pool.range_figures(range_id=range_node.get_id())
            )
            for range_node in ranges
        ],
    }


InfrahubResourcePoolAllocated = Field(
    PoolAllocated,
    pool_id=String(required=True),
    resource_id=String(required=True),
    limit=Int(required=False),
    offset=Int(required=False),
    resolver=PoolAllocated.resolve,
    required=True,
)


InfrahubResourcePoolUtilization = Field(
    PoolUtilization, pool_id=String(required=True), resolver=PoolUtilization.resolve, required=True
)
