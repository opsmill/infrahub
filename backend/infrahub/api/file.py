from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from fastapi import APIRouter, Depends, Request
from starlette.responses import PlainTextResponse

from infrahub.api.dependencies import (
    BranchParams,
    get_branch_params,
    get_current_user,
    get_db,
)
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.database import InfrahubDatabase  # noqa: TCH001
from infrahub.exceptions import CommitNotFoundError
from infrahub.message_bus import messages

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
    commit: Optional[str] = None,
    _: str = Depends(get_current_user),
) -> PlainTextResponse:
    """Retrieve a file from a git repository."""
    service: InfrahubServices = request.app.state.service

    repo = await NodeManager.get_one_by_id_or_default_filter(
        db=db,
        id=repository_id,
        schema_name=InfrahubKind.GENERICREPOSITORY,
        branch=branch_params.branch,
        at=branch_params.at,
    )

    commit = commit or repo.commit.value  # type: ignore[attr-defined]

    if not commit:
        raise CommitNotFoundError(identifier=repository_id, commit="", message="No commits found on this repository")

    message = messages.GitFileGet(
        repository_id=repo.id,
        repository_name=repo.name.value,  # type: ignore[attr-defined]
        repository_kind=repo.get_kind(),
        commit=commit,
        file=file_path,
    )

    response: messages.GitFileGetResponse = await service.message_bus.rpc(message=message)  # type: ignore[assignment]
    return PlainTextResponse(content=response.response_data.content)
