from infrahub.core.constants import InfrahubKind
from infrahub.git.repository import InfrahubReadOnlyRepository, InfrahubRepository
from infrahub.log import get_logger
from infrahub.message_bus import InfrahubResponse, messages
from infrahub.services import InfrahubServices

log = get_logger()


async def names_only(message: messages.GitDiffNamesOnly, service: InfrahubServices) -> None:
    log.info(
        "Collecting modifications between commits",
        repository=message.repository_name,
        repository_id=message.repository_id,
        repository_kind=message.repository_kind,
        first_commit=message.first_commit,
        second_commit=message.second_commit,
    )

    if message.repository_kind == InfrahubKind.READONLYREPOSITORY:
        repo = await InfrahubReadOnlyRepository.init(
            id=message.repository_id, name=message.repository_name, client=service.client
        )
    else:
        repo = await InfrahubRepository.init(
            id=message.repository_id, name=message.repository_name, client=service.client
        )

    files_changed, files_added, files_removed = await repo.calculate_diff_between_commits(
        first_commit=message.first_commit, second_commit=message.second_commit
    )

    if message.reply_requested:
        response = InfrahubResponse(
            response_class="diffnames_response",
            response_data={"files_added": files_added, "files_changed": files_changed, "files_removed": files_removed},
        )
        await service.reply(message=response, initiator=message)
