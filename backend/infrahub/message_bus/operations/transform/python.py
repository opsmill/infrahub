from infrahub.git.repository import get_initialized_repo
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.message_bus.messages.transform_python_data import (
    TransformPythonDataResponse,
    TransformPythonDataResponseData,
)
from infrahub.services import InfrahubServices

log = get_logger()


async def data(message: messages.TransformPythonData, service: InfrahubServices) -> None:
    log.info(
        "Received request to transform Python data",
        repository_name=message.repository_name,
        transform=message.transform_location,
        branch=message.branch,
    )

    repo = await get_initialized_repo(
        repository_id=message.repository_id,
        name=message.repository_name,
        service=service,
        repository_kind=message.repository_kind,
    )

    transformed_data = await repo.execute_python_transform(
        branch_name=message.branch,
        commit=message.commit,
        location=message.transform_location,
        data=message.data,
        client=service.client,
    )

    if message.reply_requested:
        response = TransformPythonDataResponse(
            response_data=TransformPythonDataResponseData(transformed_data=transformed_data)
        )
        await service.reply(message=response, initiator=message)
