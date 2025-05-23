from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Field, Float, Int, List, NonNull, ObjectType, String
from infrahub_sdk.utils import extract_fields_first_node

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.ipam.utilization import PrefixUtilizationGetter
from infrahub.core.manager import NodeManager
from infrahub.core.query.ipam import IPPrefixUtilization
from infrahub.core.query.resource_manager import (
    IPAddressPoolGetIdentifiers,
    NumberPoolGetAllocated,
    PrefixPoolGetIdentifiers,
)
from infrahub.exceptions import NodeNotFoundError, SchemaNotFoundError, ValidationError
from infrahub.pools.number import NumberUtilizationGetter

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.protocols import CoreNode
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.initialization import GraphqlContext


class IPPoolUtilizationResource(ObjectType):
    id = Field(String, required=True, description="The ID of the current resource")
    display_label = Field(String, required=True, description="The common name of the resource")
    kind = Field(String, required=True, description="The resource kind")
    weight = Field(Int, required=True, description="The relative weight of this resource.")
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


class PoolAllocatedEdge(ObjectType):
    node = Field(PoolAllocatedNode, required=True)


def _validate_pool_type(pool_id: str, pool: CoreNode | None = None) -> CoreNode:
    if not pool or pool.get_kind() not in [
        InfrahubKind.IPADDRESSPOOL,
        InfrahubKind.IPPREFIXPOOL,
        InfrahubKind.NUMBERPOOL,
    ]:
        raise NodeNotFoundError(node_type="ResourcePool", identifier=pool_id)
    return pool


class PoolAllocated(ObjectType):
    count = Field(Int, required=True, description="The number of allocations within the selected pool.")
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
        pool: CoreNode | None = await NodeManager.get_one(
            id=pool_id, db=graphql_context.db, branch=graphql_context.branch
        )

        fields = await extract_fields_first_node(info=info)

        allocated_kinds: list[str] = []
        pool = _validate_pool_type(pool_id=pool_id, pool=pool)
        match pool.get_kind():
            case InfrahubKind.NUMBERPOOL:
                return await resolve_number_pool_allocation(
                    db=graphql_context.db,
                    graphql_context=graphql_context,
                    pool=pool,
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

            nodes = []
            for result in query.get_results():
                child_node = result.get_node("child")
                child_value_node = result.get_node("av")
                node_id = str(child_node.get("uuid"))

                child_ip_value = child_value_node.get("value")
                kind = child_node.get("kind")
                branch_name = str(result.get("branch"))

                nodes.append(
                    {"node": {"id": node_id, "kind": kind, "branch": branch_name, "display_label": child_ip_value}}
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
                identifier_query = await identifier_query_class.init(
                    db=graphql_context.db, at=graphql_context.at, pool_id=pool_id, allocated=allocated_ids
                )
                await identifier_query.execute(db=graphql_context.db)

                reservations = {}
                for result in identifier_query.get_results():
                    reservation = result.get_rel("reservation")
                    allocated = result.get_node("allocated")
                    reservations[allocated.get("uuid")] = reservation.get("identifier")

                for node in nodes:
                    node["node"]["identifier"] = reservations.get(node["node"]["id"])

            response["edges"] = nodes

        return response


class PoolUtilization(ObjectType):
    count = Field(Int, required=True, description="The number of resources within the selected pool.")
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
        pool: CoreNode | None = await NodeManager.get_one(id=pool_id, db=db, branch=graphql_context.branch)
        pool = _validate_pool_type(pool_id=pool_id, pool=pool)
        if pool.get_kind() == "CoreNumberPool":
            return await resolve_number_pool_utilization(
                db=db, at=graphql_context.at, pool=pool, branch=graphql_context.branch
            )

        resources_map: dict[str, Node] = {}

        try:
            resources_map = await pool.resources.get_peers(db=db, branch_agnostic=True)  # type: ignore[attr-defined,union-attr]
        except SchemaNotFoundError:
            pass

        utilization_getter = PrefixUtilizationGetter(
            db=db, ip_prefixes=list(resources_map.values()), at=graphql_context.at
        )
        fields = await extract_fields_first_node(info=info)
        response: dict[str, Any] = {}
        total_utilization = None
        default_branch_utilization = None
        if "count" in fields:
            response["count"] = len(resources_map)
        if "utilization" in fields:
            response["utilization"] = total_utilization = await utilization_getter.get_use_percentage()
        if "utilization_default_branch" in fields:
            response["utilization_default_branch"] = (
                default_branch_utilization
            ) = await utilization_getter.get_use_percentage(branch_names=[registry.default_branch])
        if "utilization_branches" in fields:
            total_utilization = (
                total_utilization if total_utilization is not None else await utilization_getter.get_use_percentage()
            )
            default_branch_utilization = (
                default_branch_utilization
                if default_branch_utilization is not None
                else await utilization_getter.get_use_percentage(branch_names=[registry.default_branch])
            )
            response["utilization_branches"] = total_utilization - default_branch_utilization
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
                        node_response["display_label"] = await resource_node.render_display_label(db=db)
                    if "weight" in node_fields:
                        node_response["weight"] = await resource_node.get_resource_weight(db=db)  # type: ignore[attr-defined]
                    if "utilization" in node_fields:
                        node_response["utilization"] = resource_total = await utilization_getter.get_use_percentage(
                            ip_prefixes=[resource_node]
                        )
                    if "utilization_default_branch" in node_fields:
                        node_response["utilization_default_branch"] = (
                            default_branch_total
                        ) = await utilization_getter.get_use_percentage(
                            ip_prefixes=[resource_node], branch_names=[registry.default_branch]
                        )
                    if "utilization_branches" in node_fields:
                        resource_total = (
                            resource_total
                            if resource_total is not None
                            else await utilization_getter.get_use_percentage(ip_prefixes=[resource_node])
                        )
                        default_branch_total = (
                            default_branch_total
                            if default_branch_total is not None
                            else await utilization_getter.get_use_percentage(
                                ip_prefixes=[resource_node], branch_names=[registry.default_branch]
                            )
                        )
                        node_response["utilization_branches"] = resource_total - default_branch_total
                    response["edges"].append({"node": node_response})

        return response


async def resolve_number_pool_allocation(
    db: InfrahubDatabase, graphql_context: GraphqlContext, pool: CoreNode, fields: dict, offset: int, limit: int
) -> dict:
    response: dict[str, Any] = {}
    query = await NumberPoolGetAllocated.init(
        db=db, pool=pool, offset=offset, limit=limit, branch=graphql_context.branch, branch_agnostic=True
    )

    if "count" in fields:
        response["count"] = await query.count(db=db)

    if "edges" in fields:
        await query.execute(db=db)
        edges = []
        for entry in query.results:
            node = {
                "node": {
                    "id": entry.get_as_optional_type("id", str),
                    "kind": pool.node.value,  # type: ignore[attr-defined]
                    "branch": entry.get_as_optional_type("branch", str),
                    "display_label": entry.get_as_optional_type("value", int),
                }
            }
            edges.append(node)

        response["edges"] = edges
    return response


async def resolve_number_pool_utilization(
    db: InfrahubDatabase, pool: CoreNode, at: Timestamp | str | None, branch: Branch
) -> dict:
    """
    Returns a mapping containg utilization info of a number pool.
    The utilization is calculated as the percentage of the total number of values in the pool that are not excluded for the corresponding attribute.
    """

    core_number_pool = await registry.manager.get_one_by_id_or_default_filter(db=db, id=pool.id, kind="CoreNumberPool")
    number_pool = NumberUtilizationGetter(db=db, pool=core_number_pool, at=at, branch=branch)
    await number_pool.load_data()

    return {
        "count": 1,
        "utilization": number_pool.utilization,
        "utilization_default_branch": number_pool.utilization_default_branch,
        "utilization_branches": number_pool.utilization_branches,
        "edges": [
            {
                "node": {
                    "id": pool.get_id(),
                    "kind": "CoreNumberPool",
                    "display_label": pool.name.value,  # type: ignore[attr-defined]
                    "weight": 1,
                    "utilization": number_pool.utilization,
                    "utilization_default_branch": number_pool.utilization_default_branch,
                    "utilization_branches": number_pool.utilization_branches,
                }
            }
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
