from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Boolean, Field, List, ObjectType, String
from infrahub_sdk.utils import extract_fields_first_node

from infrahub.services import services

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext


class StatusSummary(ObjectType):
    schema_hash_synced = Field(
        Boolean, required=True, description="Indicates if the schema hash is in sync on all active workers"
    )


class StatusWorker(ObjectType):
    id = Field(String, required=True)
    active = Field(Boolean, required=True)
    schema_hash = Field(String, required=False)


class StatusWorkerEdge(ObjectType):
    node = Field(StatusWorker, required=True)


class StatusWorkerEdges(ObjectType):
    edges = Field(List(of_type=StatusWorkerEdge, required=True), required=True)


class Status(ObjectType):
    summary = Field(StatusSummary, required=True)
    workers = Field(StatusWorkerEdges, required=True)


async def resolve_status(
    root: dict,  # pylint: disable=unused-argument
    info: GraphQLResolveInfo,
) -> dict:
    context: GraphqlContext = info.context
    service = context.service or services.service
    fields = await extract_fields_first_node(info)
    response: dict[str, Any] = {}
    workers = await service.component.list_workers(branch=context.branch.id or context.branch.name, schema_hash=True)

    if summary := fields.get("summary"):
        response["summary"] = {}
        if "schema_hash_synced" in summary:
            hashes = {worker.schema_hash for worker in workers if worker.active}
            response["summary"]["schema_hash_synced"] = len(hashes) == 1

    if "workers" in fields:
        response["workers"] = {}
        response["workers"]["edges"] = [{"node": worker.to_dict()} for worker in workers]

    return response


InfrahubStatus = Field(Status, resolver=resolve_status)
