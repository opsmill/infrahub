from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.database import InfrahubDatabase

from .models import RepositoryBranchInfo, RepositoryData

if TYPE_CHECKING:
    from infrahub.core.protocols import CoreGenericRepository


async def get_repositories_commit_per_branch(
    db: InfrahubDatabase,
) -> dict[str, RepositoryData]:
    """Get a list of all repositories and their commit on each branches.

    This method is similar to 'get_list_repositories' method in the Python SDK.

    NOTE: At some point, we should refactor this function to use a single Database query instead of one per branch
    """

    repositories: dict[str, RepositoryData] = {}

    for branch in list(registry.branch.values()):
        repos: list[CoreGenericRepository] = await NodeManager.query(
            db=db,
            branch=branch,
            fields={"id": None, "name": None, "commit": None, "internal_status": None},
            schema=InfrahubKind.GENERICREPOSITORY,
        )

        for repository in repos:
            repo_name = repository.name.value
            if repo_name not in repositories:
                repositories[repo_name] = RepositoryData(
                    repository_id=repository.get_id(),
                    repository_name=repo_name,
                    branches={},
                )

            repositories[repo_name].branches[branch.name] = repository.commit.value  # type: ignore[attr-defined]
            repositories[repo_name].branch_info[branch.name] = RepositoryBranchInfo(
                internal_status=repository.internal_status.value
            )

    return repositories
