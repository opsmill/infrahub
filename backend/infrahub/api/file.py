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
from infrahub.message_bus.events import (
    GitMessageAction,
    InfrahubGitRPC,
    InfrahubRPCResponse,
)

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

    if not commit and repo.commit.value is None:
        raise CommitNotFoundError(identifier=repository_id, commit="", message="No commits found on this repository")

    commit = commit or repo.commit.value

    response: InfrahubRPCResponse = await rpc_client.call(
        message=InfrahubGitRPC(
            action=GitMessageAction.GET_FILE, repository=repo, location=file_path, params={"commit": commit}
        )
    )
    response.raise_for_status()

    return PlainTextResponse(content=response.response["content"])
