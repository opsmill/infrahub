from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request

from infrahub.api.dependencies import get_branch_dep, get_current_user, get_db
from infrahub.core import registry
from infrahub.core.diff.artifacts.calculator import ArtifactDiffCalculator
from infrahub.core.diff.branch_differ import BranchDiffer
from infrahub.core.diff.model.diff import (
    BranchDiffArtifact,
    BranchDiffFile,
    BranchDiffRepository,
)

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices


router = APIRouter(prefix="/diff")


@router.get("/files")
async def get_diff_files(
    request: Request,
    db: InfrahubDatabase = Depends(get_db),
    branch: Branch = Depends(get_branch_dep),
    time_from: str | None = None,
    time_to: str | None = None,
    branch_only: bool = True,
    _: AccountSession = Depends(get_current_user),
) -> dict[str, dict[str, BranchDiffRepository]]:
    response: dict[str, dict[str, BranchDiffRepository]] = defaultdict(dict)
    service: InfrahubServices = request.app.state.service

    # Query the Diff for all files and repository from the database
    diff = await BranchDiffer.init(
        db=db,
        branch=branch,
        diff_from=time_from,
        diff_to=time_to,
        branch_only=branch_only,
        service=service,
    )
    diff_files = await diff.get_files()

    for branch_name, items in diff_files.items():
        for item in items:
            repository_id = item.repository.get_id()
            display_label = await item.repository.render_display_label(db=db)
            if repository_id not in response[branch_name]:
                response[branch_name][repository_id] = BranchDiffRepository(
                    id=repository_id,
                    display_name=display_label or f"Repository ({repository_id})",
                    commit_from=item.commit_from,
                    commit_to=item.commit_to,
                    branch=branch_name,
                )

            response[branch_name][repository_id].files.append(BranchDiffFile(**item.to_graphql()))

    return response


@router.get("/artifacts")
async def get_diff_artifacts(
    db: InfrahubDatabase = Depends(get_db),
    branch: Branch = Depends(get_branch_dep),
    _: str = Depends(get_current_user),
) -> dict[str, BranchDiffArtifact]:
    artifact_diff_calculator = ArtifactDiffCalculator(db=db)
    target_branch = await registry.get_branch(db=db, branch=registry.default_branch)
    artifact_diffs = await artifact_diff_calculator.calculate(source_branch=branch, target_branch=target_branch)
    response = {art_diff.id: art_diff for art_diff in artifact_diffs}
    return response
