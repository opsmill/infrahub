from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import infrahub.config as config
from infrahub import lock
from infrahub.exceptions import Error
from infrahub.git.repository import InfrahubRepository
from infrahub.message_bus.events import (
    ArtifactMessageAction,
    GitMessageAction,
    InfrahubArtifactRPC,
    InfrahubGitRPC,
    InfrahubRPC,
    InfrahubRPCResponse,
    MessageType,
    RPCStatusCode,
)
from infrahub_client import InfrahubNode

if TYPE_CHECKING:
    from infrahub_client import InfrahubClient

LOGGER = logging.getLogger("infrahub.git")


async def handle_bad_request(  # pylint: disable=unused-argument
    message: InfrahubRPC, client: InfrahubClient
) -> InfrahubRPCResponse:
    return InfrahubRPCResponse(status=RPCStatusCode.BAD_REQUEST)


async def handle_not_found(  # pylint: disable=unused-argument
    message: InfrahubRPC, client: InfrahubClient
) -> InfrahubRPCResponse:
    return InfrahubRPCResponse(status=RPCStatusCode.NOT_FOUND)


async def handle_not_implemented(  # pylint: disable=unused-argument
    message: InfrahubRPC, client: InfrahubClient
) -> InfrahubRPCResponse:
    return InfrahubRPCResponse(status=RPCStatusCode.NOT_IMPLEMENTED)


async def handle_git_message_action_merge(message: InfrahubGitRPC, client: InfrahubClient) -> InfrahubRPCResponse:
    repo = await InfrahubRepository.init(id=message.repository_id, name=message.repository_name, client=client)
    async with lock.registry.get(name=message.repository_name, namespace="repository"):
        await repo.merge(source_branch=message.params["branch_name"], dest_branch=config.SETTINGS.main.default_branch)
        return InfrahubRPCResponse(status=RPCStatusCode.OK)


async def handle_artifact_message_action_generate(
    message: InfrahubArtifactRPC, client: InfrahubClient
) -> InfrahubRPCResponse:
    repo = await InfrahubRepository.init(id=message.repository_id, name=message.repository_name, client=client)

    artifact_schema = await client.schema.get(kind=message.artifact.get("__typename"))
    artifact = InfrahubNode(client=client, schema=artifact_schema, data=message.artifact, branch=message.branch_name)
    try:
        transformation_schema = await client.schema.get(kind=message.transformation.get("__typename"))
        transformation = InfrahubNode(
            client=client, schema=transformation_schema, data=message.transformation, branch=message.branch_name
        )

        definition_schema = await client.schema.get(kind=message.definition.get("__typename"))
        definition = InfrahubNode(
            client=client, schema=definition_schema, data=message.definition, branch=message.branch_name
        )

        query_schema = await client.schema.get(kind=message.query.get("__typename"))
        query = InfrahubNode(client=client, schema=query_schema, data=message.query, branch=message.branch_name)

        target_schema = await client.schema.get(kind=message.target.get("__typename"))
        target = InfrahubNode(client=client, schema=target_schema, data=message.target, branch=message.branch_name)

        result = await repo.artifact_generate(
            branch_name=message.branch_name,
            commit=message.commit,
            artifact=artifact,
            target=target,
            transformation=transformation,
            query=query,
            definition=definition,
        )
        return InfrahubRPCResponse(status=RPCStatusCode.OK, response=result.dict())

    except Error as exc:
        # pylint: disable=no-member
        artifact.status.value = "Error"
        await artifact.save()
        return InfrahubRPCResponse(status=RPCStatusCode.INTERNAL_ERROR, errors=[exc.message])


async def handle_git_rpc_message(  # pylint: disable=too-many-return-statements
    message: InfrahubGitRPC, client: InfrahubClient
) -> InfrahubRPCResponse:
    LOGGER.debug(f"Will process Git RPC message : {message.action}, {message.repository_name} : {message.params}")

    handler_map = {
        GitMessageAction.MERGE: handle_git_message_action_merge,
    }
    handler = handler_map.get(message.action) or handle_bad_request
    return await handler(message=message, client=client)


async def handle_artifact_message(message: InfrahubArtifactRPC, client: InfrahubClient) -> InfrahubRPCResponse:
    LOGGER.debug(
        f"Will process Artifact RPC message : {message.action}, {message.repository_name} : {message.definition['display_label']} {message.target['display_label']}"
    )

    handler_map = {
        ArtifactMessageAction.GENERATE: handle_artifact_message_action_generate,
    }
    handler = handler_map.get(message.action) or handle_bad_request
    return await handler(message=message, client=client)


async def handle_message(message: InfrahubRPC, client: InfrahubClient) -> InfrahubRPCResponse:
    message_type_map = {
        MessageType.GIT: handle_git_rpc_message,
        MessageType.ARTIFACT: handle_artifact_message,
    }
    handler = message_type_map.get(message.type) or handle_not_found
    return await handler(message=message, client=client)
