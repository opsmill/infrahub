from infrahub.core.constants import InfrahubKind
from infrahub.git.repository import InfrahubReadOnlyRepository, InfrahubRepository
from infrahub.log import get_logger
from infrahub.message_bus import InfrahubResponse, messages
from infrahub.services import InfrahubServices

log = get_logger()


async def data(message: messages.TransformPythonData, service: InfrahubServices) -> None:
    log.info(
        "Received request to transform Python data",
        repository_name=message.repository_name,
        transform=message.transform_location,
        branch=message.branch,
    )

    if message.repository_kind == InfrahubKind.READONLYREPOSITORY:
        repo = await InfrahubReadOnlyRepository.init(id=message.repository_id, name=message.repository_name)
    else:
        repo = await InfrahubRepository.init(id=message.repository_id, name=message.repository_name)

    transformed_data = await repo.execute_python_transform(
        branch_name=message.branch,
        commit=message.commit,
        location=message.transform_location,
        data=message.data,
        client=service.client,
    )

    if message.reply_requested:
        response = InfrahubResponse(
            response_class="transform_response", response_data={"transformed_data": transformed_data}
        )
        await service.reply(message=response, initiator=message)
