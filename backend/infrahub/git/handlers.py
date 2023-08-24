from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import infrahub.config as config
from infrahub import lock
from infrahub.exceptions import (
    CheckError,
    Error,
    FileNotFound,
    RepositoryError,
    TransformError,
)
from infrahub.git.repository import InfrahubRepository
from infrahub.log import set_log_data
from infrahub.message_bus.events import (
    ArtifactMessageAction,
    CheckMessageAction,
    GitMessageAction,
    InfrahubArtifactRPC,
    InfrahubCheckRPC,
    InfrahubGitRPC,
    InfrahubRPC,
    InfrahubRPCResponse,
    InfrahubTransformRPC,
    MessageType,
    RPCStatusCode,
    TransformMessageAction,
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


async def handle_check_message_action_python(message: InfrahubCheckRPC, client: InfrahubClient) -> InfrahubRPCResponse:
    repo = await InfrahubRepository.init(id=message.repository_id, name=message.repository_name, client=client)

    try:
        check = await repo.execute_python_check(
            branch_name=message.branch_name,
            commit=message.commit,
            location=message.check_location,
            class_name=message.check_name,
            client=client,
        )

        return InfrahubRPCResponse(
            status=RPCStatusCode.OK,
            response={"passed": check.passed, "logs": check.logs, "errors": check.errors},
        )

    except (CheckError, FileNotFound) as exc:
        return InfrahubRPCResponse(status=RPCStatusCode.INTERNAL_ERROR, errors=[exc.message])


async def handle_git_message_action_branch_add(message: InfrahubGitRPC, client: InfrahubClient) -> InfrahubRPCResponse:
    repo = await InfrahubRepository.init(id=message.repository_id, name=message.repository_name, client=client)
    async with lock.registry.get(name=message.repository_name, namespace="repository"):
        try:
            await repo.create_branch_in_git(branch_name=message.params["branch_name"])
        except RepositoryError as exc:
            return InfrahubRPCResponse(status=RPCStatusCode.INTERNAL_ERROR, errors=[exc.message])
        set_log_data(key="branch_name", value=message.params["branch_name"])

        return InfrahubRPCResponse(status=RPCStatusCode.OK)


async def handle_git_message_action_diff(message: InfrahubGitRPC, client: InfrahubClient) -> InfrahubRPCResponse:
    repo = await InfrahubRepository.init(id=message.repository_id, name=message.repository_name, client=client)
    files_changed, files_added, files_removed = await repo.calculate_diff_between_commits(
        first_commit=message.params["first_commit"], second_commit=message.params["second_commit"]
    )
    return InfrahubRPCResponse(
        status=RPCStatusCode.OK,
        response={"files_changed": files_changed, "files_added": files_added, "files_removed": files_removed},
    )


async def handle_git_message_action_get_file(message: InfrahubGitRPC, client: InfrahubClient) -> InfrahubRPCResponse:
    repo = await InfrahubRepository.init(id=message.repository_id, name=message.repository_name, client=client)
    content = await repo.get_file(commit=message.params["commit"], location=message.location)

    return InfrahubRPCResponse(
        status=RPCStatusCode.OK,
        response={"content": content},
    )


async def handle_git_message_action_merge(message: InfrahubGitRPC, client: InfrahubClient) -> InfrahubRPCResponse:
    repo = await InfrahubRepository.init(id=message.repository_id, name=message.repository_name, client=client)
    async with lock.registry.get(name=message.repository_name, namespace="repository"):
        await repo.merge(source_branch=message.params["branch_name"], dest_branch=config.SETTINGS.main.default_branch)
        return InfrahubRPCResponse(status=RPCStatusCode.OK)


async def handle_git_message_action_repo_add(message: InfrahubGitRPC, client: InfrahubClient) -> InfrahubRPCResponse:
    async with lock.registry.get(name=message.repository_name, namespace="repository"):
        try:
            repo = await InfrahubRepository.new(
                id=message.repository_id, name=message.repository_name, location=message.location, client=client
            )
            await repo.import_objects_from_files(branch_name=repo.default_branch_name)
            await repo.sync()

        except RepositoryError as exc:
            return InfrahubRPCResponse(status=RPCStatusCode.BAD_REQUEST, errors=[exc.message])

        return InfrahubRPCResponse(status=RPCStatusCode.CREATED)


async def handle_transform_message_action_jinja2(
    message: InfrahubTransformRPC, client: InfrahubClient
) -> InfrahubRPCResponse:
    repo = await InfrahubRepository.init(id=message.repository_id, name=message.repository_name, client=client)

    try:
        rendered_template = await repo.render_jinja2_template(
            commit=message.commit, location=message.transform_location, data={"data": message.data} or {}
        )
        return InfrahubRPCResponse(status=RPCStatusCode.OK, response={"rendered_template": rendered_template})

    except (TransformError, FileNotFound) as exc:
        return InfrahubRPCResponse(status=RPCStatusCode.INTERNAL_ERROR, errors=[exc.message])


async def handle_transform_message_action_python(
    message: InfrahubTransformRPC, client: InfrahubClient
) -> InfrahubRPCResponse:
    repo = await InfrahubRepository.init(id=message.repository_id, name=message.repository_name, client=client)

    try:
        data = None
        if message.data:
            data = message.data

        transformed_data = await repo.execute_python_transform(
            branch_name=message.branch_name,
            commit=message.commit,
            location=message.transform_location,
            data=data,
            client=client,
        )
        return InfrahubRPCResponse(status=RPCStatusCode.OK, response={"transformed_data": transformed_data})

    except (TransformError, FileNotFound) as exc:
        return InfrahubRPCResponse(status=RPCStatusCode.INTERNAL_ERROR, errors=[exc.message])


async def handle_artifact_message_action_generate(
    message: InfrahubTransformRPC, client: InfrahubClient
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
        GitMessageAction.REPO_ADD: handle_git_message_action_repo_add,
        GitMessageAction.BRANCH_ADD: handle_git_message_action_branch_add,
        GitMessageAction.DIFF: handle_git_message_action_diff,
        GitMessageAction.MERGE: handle_git_message_action_merge,
        GitMessageAction.GET_FILE: handle_git_message_action_get_file,
        GitMessageAction.REBASE: handle_not_implemented,
        GitMessageAction.PUSH: handle_not_implemented,
        GitMessageAction.PULL: handle_not_implemented,
    }
    handler = handler_map.get(message.action) or handle_bad_request
    return await handler(message=message, client=client)


async def handle_git_transform_message(message: InfrahubTransformRPC, client: InfrahubClient) -> InfrahubRPCResponse:
    LOGGER.debug(
        f"Will process Transform RPC message : {message.action}, {message.repository_name} : {message.transform_location}"
    )

    handler_map = {
        TransformMessageAction.JINJA2: handle_transform_message_action_jinja2,
        TransformMessageAction.PYTHON: handle_transform_message_action_python,
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


async def handle_git_check_message(message: InfrahubCheckRPC, client: InfrahubClient) -> InfrahubRPCResponse:
    LOGGER.debug(
        f"Will process Check RPC message : {message.action}, {message.repository_name} : {message.check_location} {message.check_name}"
    )
    handler_map = {
        CheckMessageAction.PYTHON: handle_check_message_action_python,
    }
    handler = handler_map.get(message.action) or handle_bad_request
    return await handler(message=message, client=client)


async def handle_message(message: InfrahubRPC, client: InfrahubClient) -> InfrahubRPCResponse:
    message_type_map = {
        MessageType.CHECK: handle_git_check_message,
        MessageType.GIT: handle_git_rpc_message,
        MessageType.TRANSFORMATION: handle_git_transform_message,
        MessageType.ARTIFACT: handle_artifact_message,
    }
    handler = message_type_map.get(message.type) or handle_not_found
    return await handler(message=message, client=client)
