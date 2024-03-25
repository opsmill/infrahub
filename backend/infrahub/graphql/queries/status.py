from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Boolean, Field, Int, ObjectType
from infrahub_sdk.utils import extract_fields_first_node

from infrahub.services import InfrahubServices, services

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.branch import Branch
    from infrahub.graphql import GraphqlContext


class StatusWorkerCount(ObjectType):
    api_servers = Int(required=True)
    git_agents = Int(required=True)


class StatusSchemaHash(ObjectType):
    synced = Field(Boolean, required=True)


class StatusSchemaHashOverview(ObjectType):
    all = Field(
        Boolean,
        required=True,
        description="Indicates if all workers and agents are using the same schema hash for this branch",
    )
    api_workers = Field(
        Boolean,
        required=True,
        description="Indicates if all api workers are using the same schema hash for this branch",
    )
    git_agents = Field(
        Boolean, required=True, description="Indicates if all git agents are using the same schema hash for this branch"
    )


class StatusOverview(ObjectType):
    online = Field(StatusWorkerCount, required=True)
    schema_hash = Field(StatusSchemaHashOverview, required=True)


class Status(ObjectType):
    overview = Field(StatusOverview, required=True)


async def resolve_overview(overview: dict, service: InfrahubServices, branch: Branch) -> dict:
    response: dict[str, Any] = {}

    if schema_hash := overview.get("schema_hash"):
        response["schema_hash"] = {}
        if "all" in schema_hash:
            response["schema_hash"]["all"] = await service.component.schema_hash_synced(branch=branch.name)
        if "api_workers" in schema_hash:
            response["schema_hash"]["api_workers"] = await service.component.schema_hash_synced(
                branch=branch.name, component="api_server"
            )
        if "git_agents" in schema_hash:
            response["schema_hash"]["git_agents"] = await service.component.schema_hash_synced(
                branch=branch.name, component="git_agent"
            )

    if online := overview.get("online"):
        response["online"] = await resolve_online_count(
            api_servers="api_servers" in online,
            git_agents="git_agents" in online,
            service=service,
        )

    return response


async def resolve_online_count(api_servers: bool, git_agents: bool, service: InfrahubServices) -> dict:
    response = {}

    if api_servers:
        response["api_servers"] = await service.component.count_component(component="api_server")

    if git_agents:
        response["git_agents"] = await service.component.count_component(component="git_agent")

    return response


async def resolve_status(
    root: dict,  # pylint: disable=unused-argument
    info: GraphQLResolveInfo,  # pylint: disable=unused-argument
) -> dict:
    context: GraphqlContext = info.context
    service = context.service or services.service
    fields = await extract_fields_first_node(info)
    response = {}

    if overview := fields.get("overview"):
        response["overview"] = await resolve_overview(
            overview=overview,
            service=service,
            branch=context.branch,
        )

    return response


InfrahubStatus = Field(Status, resolver=resolve_status)
