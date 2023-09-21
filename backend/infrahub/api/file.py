from typing import TYPE_CHECKING, Optional

from fastapi import APIRouter, Depends, Request
from neo4j import AsyncSession
from starlette.responses import PlainTextResponse

from infrahub.api.dependencies import (
    BranchParams,
    get_branch_params,
    get_current_user,
    get_session,
)
from infrahub.core.manager import NodeManager
from infrahub.exceptions import CommitNotFoundError
from infrahub.message_bus import messages
from infrahub.message_bus.responses import ContentResponse

if TYPE_CHECKING:
    from infrahub.message_bus.rpc import InfrahubRpcClient


router = APIRouter(prefix="/file")


@router.get("/{repository_id:str}/{file_path:path}", response_class=PlainTextResponse)
async def get_file(
    request: Request,
    repository_id: str,
    file_path: str,
    branch_params: BranchParams = Depends(get_branch_params),
    session: AsyncSession = Depends(get_session),
    commit: Optional[str] = None,
    _: str = Depends(get_current_user),
) -> PlainTextResponse:
    """Retrieve a file from a git repository."""
    rpc_client: InfrahubRpcClient = request.app.state.rpc_client

    repo = await NodeManager.get_one_by_id_or_default_filter(
        session=session,
        id=repository_id,
        schema_name="CoreRepository",
        branch=branch_params.branch,
        at=branch_params.at,
    )

    commit = commit or repo.commit.value  # type: ignore[attr-defined]

    if not commit:
        raise CommitNotFoundError(identifier=repository_id, commit="", message="No commits found on this repository")

    message = messages.GitFileGet(
        repository_id=repo.id,
        repository_name=repo.name.value,  # type: ignore[attr-defined]
        commit=commit,
        file=file_path,
    )

    response = await rpc_client.rpc(message=message)
    content = response.parse(response_class=ContentResponse)
    return PlainTextResponse(content=content.content)
