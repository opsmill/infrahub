from __future__ import annotations

import logging

import infrahub.config as config
from infrahub.exceptions import (
    CheckError,
    FileNotFound,
    RepositoryError,
    TransformError,
)
from infrahub.git.repository import InfrahubRepository
from infrahub.lock import registry as lock_registry
from infrahub.message_bus.events import (
    CheckMessageAction,
    GitMessageAction,
    InfrahubCheckRPC,
    InfrahubGitRPC,
    InfrahubRPC,
    InfrahubRPCResponse,
    InfrahubTransformRPC,
    MessageType,
    RPCStatusCode,
    TransformMessageAction,
)
from infrahub_client import InfrahubClient

LOGGER = logging.getLogger("infrahub.git")


async def handle_bad_request(  # pylint: disable=unused-argument
    message: InfrahubGitRPC, client: InfrahubClient
) -> InfrahubRPCResponse:
    return InfrahubRPCResponse(status=RPCStatusCode.BAD_REQUEST.value)


async def handle_not_found(  # pylint: disable=unused-argument
    message: InfrahubGitRPC, client: InfrahubClient
) -> InfrahubRPCResponse:
    return InfrahubRPCResponse(status=RPCStatusCode.NOT_FOUND.value)


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
            status=RPCStatusCode.OK.value,
            response={"passed": check.passed, "logs": check.logs, "errors": check.errors},
        )

    except (CheckError, FileNotFound) as exc:
        return InfrahubRPCResponse(status=RPCStatusCode.INTERNAL_ERROR.value, errors=[exc.message])


async def handle_transform_message_action_jinja2(
    message: InfrahubTransformRPC, client: InfrahubClient
) -> InfrahubRPCResponse:
    repo = await InfrahubRepository.init(id=message.repository_id, name=message.repository_name, client=client)

    try:
        rendered_template = await repo.render_jinja2_template(
            commit=message.commit, location=message.transform_location, data={"data": message.data} or {}
        )
        return InfrahubRPCResponse(status=RPCStatusCode.OK.value, response={"rendered_template": rendered_template})

    except (TransformError, FileNotFound) as exc:
        return InfrahubRPCResponse(status=RPCStatusCode.INTERNAL_ERROR.value, errors=[exc.message])


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
        return InfrahubRPCResponse(status=RPCStatusCode.OK.value, response={"transformed_data": transformed_data})

    except (TransformError, FileNotFound) as exc:
        return InfrahubRPCResponse(status=RPCStatusCode.INTERNAL_ERROR.value, errors=[exc.message])


async def handle_git_rpc_message(  # pylint: disable=too-many-return-statements
    message: InfrahubGitRPC, client: InfrahubClient
) -> InfrahubRPCResponse:
    LOGGER.debug(f"Will process Git RPC message : {message.action}, {message.repository_name} : {message.params}")

    if message.action == GitMessageAction.REPO_ADD.value:
        async with lock_registry.get(message.repository_name):
            try:
                repo = await InfrahubRepository.new(
                    id=message.repository_id, name=message.repository_name, location=message.location, client=client
                )
                await repo.import_objects_from_files(branch_name=repo.default_branch_name)
                await repo.sync()

            except RepositoryError as exc:
                return InfrahubRPCResponse(status=RPCStatusCode.BAD_REQUEST, errors=[exc.message])

            return InfrahubRPCResponse(status=RPCStatusCode.CREATED.value)

    repo = await InfrahubRepository.init(id=message.repository_id, name=message.repository_name, client=client)

    if message.action == GitMessageAction.BRANCH_ADD.value:
        async with lock_registry.get(message.repository_name):
            try:
                await repo.create_branch_in_git(branch_name=message.params["branch_name"])
            except RepositoryError as exc:
                return InfrahubRPCResponse(status=RPCStatusCode.INTERNAL_ERROR, errors=[exc.message])

            return InfrahubRPCResponse(status=RPCStatusCode.OK.value)

    elif message.action == GitMessageAction.DIFF.value:
        # Calculate the diff between 2 timestamps / branches
        files_changed, files_added, files_removed = await repo.calculate_diff_between_commits(
            first_commit=message.params["first_commit"], second_commit=message.params["second_commit"]
        )
        return InfrahubRPCResponse(
            status=RPCStatusCode.OK.value,
            response={"files_changed": files_changed, "files_added": files_added, "files_removed": files_removed},
        )

    elif message.action == GitMessageAction.MERGE.value:
        async with lock_registry.get(message.repository_name):
            await repo.merge(
                source_branch=message.params["branch_name"], dest_branch=config.SETTINGS.main.default_branch
            )
            return InfrahubRPCResponse(status=RPCStatusCode.OK.value)

    elif message.action == GitMessageAction.REBASE.value:
        # async with lock_registry.get(message.repository_name):
        return InfrahubRPCResponse(status=RPCStatusCode.NOT_IMPLEMENTED.value)

    elif message.action == GitMessageAction.PUSH.value:
        # async with lock_registry.get(message.repository_name):
        return InfrahubRPCResponse(status=RPCStatusCode.NOT_IMPLEMENTED.value)

    elif message.action == GitMessageAction.PULL.value:
        # async with lock_registry.get(message.repository_name):
        return InfrahubRPCResponse(status=RPCStatusCode.NOT_IMPLEMENTED.value)

    return InfrahubRPCResponse(status=RPCStatusCode.BAD_REQUEST.value)


async def handle_git_transform_message(message: InfrahubTransformRPC, client: InfrahubClient) -> InfrahubRPCResponse:
    LOGGER.debug(
        f"Will process Transform RPC message : {message.action}, {message.repository_name} : {message.transform_location}"
    )

    handler_map = {
        TransformMessageAction.JINJA2.value: handle_transform_message_action_jinja2,
        TransformMessageAction.PYTHON.value: handle_transform_message_action_python,
    }
    handler = handler_map.get(message.action) or handle_bad_request
    return await handler(message=message, client=client)


async def handle_git_check_message(message: InfrahubCheckRPC, client: InfrahubClient) -> InfrahubRPCResponse:
    LOGGER.debug(
        f"Will process Check RPC message : {message.action}, {message.repository_name} : {message.check_location} {message.check_name}"
    )
    handler_map = {
        CheckMessageAction.PYTHON.value: handle_check_message_action_python,
    }
    handler = handler_map.get(message.action) or handle_bad_request
    return await handler(message=message, client=client)


async def handle_message(message: InfrahubRPC, client: InfrahubClient) -> InfrahubRPCResponse:
    message_type_map = {
        MessageType.CHECK: handle_git_check_message,
        MessageType.TRANSFORMATION: handle_git_transform_message,
    }
    handler = message_type_map.get(message.type) or handle_not_found
    return await handler(message=message, client=client)
