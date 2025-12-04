import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.git.utils import get_repositories_commit_per_branch


@pytest.fixture
async def repository_01(db: InfrahubDatabase, register_core_models_schema, default_branch: Branch):
    repo = await Node.init(db=db, schema=InfrahubKind.REPOSITORY, branch=default_branch)
    await repo.new(db=db, name="repo01", default_branch=default_branch.name, commit="commit01", location="location01")
    await repo.save(db=db)
    return repo


@pytest.fixture
async def repository_02(db: InfrahubDatabase, register_core_models_schema, default_branch: Branch):
    repo = await Node.init(db=db, schema=InfrahubKind.READONLYREPOSITORY, branch=default_branch)
    await repo.new(db=db, name="repo02", ref=default_branch.name, commit="commit02", location="location02")
    await repo.save(db=db)
    return repo


async def test_get_repositories_commit_per_branch_main(
    db: InfrahubDatabase, register_core_models_schema, repository_01: Node, repository_02: Node
) -> None:
    repositories = await get_repositories_commit_per_branch(db=db)
    assert list(repositories.keys()) == ["repo01", "repo02"]

    assert repositories["repo01"].repository.id == repository_01.id
    assert repositories["repo01"].model_dump(exclude=["repository"]) == {
        "repository_id": repository_01.id,
        "repository_name": "repo01",
        "branches": {"main": "commit01", "-global-": "commit01"},
        "branch_info": {"main": {"internal_status": "inactive"}, "-global-": {"internal_status": "inactive"}},
    }
    assert repositories["repo02"].repository.id == repository_02.id
    assert repositories["repo02"].model_dump(exclude=["repository"]) == {
        "repository_id": repository_02.id,
        "repository_name": "repo02",
        "branches": {"main": "commit02", "-global-": None},
        "branch_info": {"main": {"internal_status": "inactive"}, "-global-": {"internal_status": "inactive"}},
    }


async def test_get_repositories_commit_per_branch_branches(
    db: InfrahubDatabase, register_core_models_schema, repository_01: Node, repository_02: Node
) -> None:
    branch2 = await create_branch(db=db, branch_name="branch2")
    repo01_branch = await NodeManager.get_one(db=db, id=repository_01.id, branch=branch2)
    repo01_branch.commit.value = "commit21"
    await repo01_branch.save(db=db)

    branch3 = await create_branch(db=db, branch_name="branch3")
    repo02_branch = await NodeManager.get_one(db=db, id=repository_02.id, branch=branch3)
    repo02_branch.commit.value = "commit32"
    await repo02_branch.save(db=db)

    repositories = await get_repositories_commit_per_branch(db=db)
    assert list(repositories.keys()) == ["repo01", "repo02"]

    assert repositories["repo01"].repository.id == repository_01.id
    assert repositories["repo01"].model_dump(exclude=["repository"]) == {
        "repository_id": repository_01.id,
        "repository_name": "repo01",
        "branches": {
            "-global-": "commit01",
            "branch2": "commit21",
            "branch3": "commit01",
            "main": "commit01",
        },
        "branch_info": {
            "-global-": {"internal_status": "inactive"},
            "branch2": {"internal_status": "inactive"},
            "branch3": {"internal_status": "inactive"},
            "main": {"internal_status": "inactive"},
        },
    }
    assert repositories["repo02"].repository.id == repository_02.id
    assert repositories["repo02"].model_dump(exclude=["repository"]) == {
        "repository_id": repository_02.id,
        "repository_name": "repo02",
        "branches": {
            "-global-": None,
            "branch2": "commit02",
            "branch3": "commit32",
            "main": "commit02",
        },
        "branch_info": {
            "-global-": {"internal_status": "inactive"},
            "branch2": {"internal_status": "inactive"},
            "branch3": {"internal_status": "inactive"},
            "main": {"internal_status": "inactive"},
        },
    }
