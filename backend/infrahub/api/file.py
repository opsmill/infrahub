from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request
from starlette.responses import PlainTextResponse

from infrahub.api.dependencies import BranchParams, get_branch_params, get_current_user, get_db
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreGenericRepository
from infrahub.database import InfrahubDatabase  # noqa: TC001
from infrahub.exceptions import CommitNotFoundError, PropagatedFromWorkerError
from infrahub.message_bus.messages import GitFileGet, GitFileGetResponse

if TYPE_CHECKING:
    from infrahub.services import InfrahubServices


router = APIRouter(prefix="/file")


@router.get("/{repository_id:str}/{file_path:path}", response_class=PlainTextResponse)
async def get_file(
    request: Request,
    repository_id: str,
    file_path: str,
    branch_params: BranchParams = Depends(get_branch_params),
    db: InfrahubDatabase = Depends(get_db),
    commit: str | None = None,
    _: str = Depends(get_current_user),
) -> PlainTextResponse:
    """Retrieve a file from a git repository.

    Raises:
        CommitNotFoundError: When no commit is provided and the repository has no commits.
        PropagatedFromWorkerError: When the worker returns an error response while reading the file.

    """
    service: InfrahubServices = request.app.state.service

    repo = await NodeManager.get_one_by_id_or_default_filter(
        db=db,
        id=repository_id,
        kind=CoreGenericRepository,
        branch=branch_params.branch,
        at=branch_params.at,
    )

    # `commit` is defined on CoreRepository/CoreReadOnlyRepository but not on
    # CoreGenericRepository; arguably it belongs on the generic since every concrete
    # repository kind carries one. Until that's lifted, the runtime kind here is always
    # one of the subclasses, so the access is safe.
    commit = commit or repo.commit.value  # type: ignore[attr-defined]

    if not commit:
        raise CommitNotFoundError(identifier=repository_id, commit="", message="No commits found on this repository")

    message = GitFileGet(
        repository_id=repo.id,
        repository_name=str(repo.name.value),
        repository_kind=repo.get_kind(),
        commit=str(commit),
        file=file_path,
    )

    response = await service.message_bus.rpc(message=message, response_class=GitFileGetResponse)
    if response.data.http_code is not None:
        assert response.data.error_message is not None
        raise PropagatedFromWorkerError(message=response.data.error_message, http_code=response.data.http_code)

    return PlainTextResponse(content=response.data.content)
