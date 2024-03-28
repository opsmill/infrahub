from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Boolean, Field, List, ObjectType, String
from infrahub_sdk.utils import extract_fields_first_node

from infrahub.services import InfrahubServices, services

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.graphql import GraphqlContext


class StatusWorker(ObjectType):
    id = Field(String, required=True)
    active = Field(Boolean, required=True)
    schema_hash = Field(String, required=False)


class StatusWorkerEdge(ObjectType):
    node = Field(StatusWorker, required=True)


class StatusWorkerEdges(ObjectType):
    edges = Field(List(of_type=StatusWorkerEdge), required=True)


class Status(ObjectType):
    workers = Field(StatusWorkerEdges, required=True)


async def resolve_workers(workers: dict, service: InfrahubServices, branch: Branch) -> dict:
    response: dict[str, Any] = {}
    if edges := workers.get("edges"):
        response["edges"] = []
        if node := edges.get("node"):
            response["edges"] = await resolve_worker_node(node=node, service=service, branch=branch)

    return response


async def resolve_worker_node(node: dict, service: InfrahubServices, branch: Branch) -> list[dict]:
    response: list[dict] = []

    schema_hash = "schema_hash" in node
    workers = await service.component.list_workers(branch=branch.name, schema_hash=schema_hash)
    for worker in workers:
        response.append({"node": worker.to_dict()})

    return response


async def resolve_status(
    root: dict,  # pylint: disable=unused-argument
    info: GraphQLResolveInfo,
) -> dict:
    context: GraphqlContext = info.context
    service = context.service or services.service
    fields = await extract_fields_first_node(info)
    response = {}

    if workers := fields.get("workers"):
        response["workers"] = await resolve_workers(
            workers=workers,
            service=service,
            branch=context.branch,
        )

    return response


InfrahubStatus = Field(Status, resolver=resolve_status)
