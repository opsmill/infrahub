from collections.abc import Generator

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import (
    GLOBAL_BRANCH_NAME,
    InfrahubKind,
    RepositoryInternalStatus,
    RepositoryOperationalStatus,
)
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.repository import RepositoryBranchAttributesQuery
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.git.constants import REPOSITORY_BRANCH_READ_CHUNK_SIZE
from infrahub.git.utils import get_repositories_commit_per_branch
from tests.helpers.db_query_counter import CountingInfrahubDatabase

ATTRIBUTES_QUERY_NAME = RepositoryBranchAttributesQuery.name
REPOSITORY_NODES_QUERY_NAME = "node_get_list"

BRANCH_COUNT = REPOSITORY_BRANCH_READ_CHUNK_SIZE * 2 + 1
"""Branch names the read resolves, the default branch included.

Two full chunks and a partial one, so a batching error at the final chunk boundary cannot pass.
"""

EXPECTED_ATTRIBUTES_QUERY_COUNT = 3
"""Chunks BRANCH_COUNT branch names split into, at any chunk size: ceil((2C + 1) / C) is 3.

Pinned as a literal rather than recomputed from the chunk size, so a chunking regression fails here
instead of being tracked by an expectation derived from the implementation's own formula.
"""


@pytest.fixture(autouse=True)
def branch_registry_restored() -> Generator[None, None, None]:
    """Undo the branch-cache entries a test adds, so the tests stay independent of each other."""
    original = dict(registry.branch)
    yield
    registry.branch.clear()
    registry.branch.update(original)


@pytest.fixture
async def repository_01(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch, default_branch: Branch
) -> Node:
    repo = await Node.init(db=db, schema=InfrahubKind.REPOSITORY, branch=default_branch)
    await repo.new(db=db, name="repo01", default_branch=default_branch.name, commit="commit01", location="location01")
    await repo.save(db=db)
    return repo


@pytest.fixture
async def repository_02(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch, default_branch: Branch
) -> Node:
    repo = await Node.init(db=db, schema=InfrahubKind.READONLYREPOSITORY, branch=default_branch)
    await repo.new(db=db, name="repo02", ref=default_branch.name, commit="commit02", location="location02")
    await repo.save(db=db)
    return repo


async def test_get_repositories_commit_per_branch_main(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch, repository_01: Node, repository_02: Node
) -> None:
    repositories = await get_repositories_commit_per_branch(db=db)
    assert list(repositories.keys()) == ["repo01", "repo02"]

    assert repositories["repo01"].repository.id == repository_01.id
    assert repositories["repo01"].model_dump(exclude=["repository"]) == {
        "repository_id": repository_01.id,
        "repository_name": "repo01",
        "branches": {"main": "commit01"},
        "branch_info": {"main": {"internal_status": "inactive"}},
    }
    assert repositories["repo02"].repository.id == repository_02.id
    assert repositories["repo02"].model_dump(exclude=["repository"]) == {
        "repository_id": repository_02.id,
        "repository_name": "repo02",
        "branches": {"main": "commit02"},
        "branch_info": {"main": {"internal_status": "inactive"}},
    }


async def test_get_repositories_commit_per_branch_non_main_default_branch(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch, default_branch: Branch
) -> None:
    repo = await Node.init(db=db, schema=InfrahubKind.REPOSITORY, branch=default_branch)
    await repo.new(db=db, name="repo01", default_branch="staging", commit="commit01", location="location01")
    await repo.save(db=db)

    repositories = await get_repositories_commit_per_branch(db=db)

    assert repositories["repo01"].repository.default_branch.value == "staging"


async def test_get_repositories_commit_per_branch_branches(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch, repository_01: Node, repository_02: Node
) -> None:
    """`commit` and `internal_status` are resolved per branch, not taken off the default branch."""
    branch2 = await create_branch(db=db, branch_name="branch2")
    repo01_branch = await NodeManager.get_one(db=db, id=repository_01.id, branch=branch2)
    repo01_branch.commit.value = "commit21"
    repo01_branch.internal_status.value = RepositoryInternalStatus.STAGING.value
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
            "branch2": "commit21",
            "branch3": "commit01",
            "main": "commit01",
        },
        "branch_info": {
            "branch2": {"internal_status": "staging"},
            "branch3": {"internal_status": "inactive"},
            "main": {"internal_status": "inactive"},
        },
    }
    assert repositories["repo02"].repository.id == repository_02.id
    assert repositories["repo02"].model_dump(exclude=["repository"]) == {
        "repository_id": repository_02.id,
        "repository_name": "repo02",
        "branches": {
            "branch2": "commit02",
            "branch3": "commit32",
            "main": "commit02",
        },
        "branch_info": {
            "branch2": {"internal_status": "inactive"},
            "branch3": {"internal_status": "inactive"},
            "main": {"internal_status": "inactive"},
        },
    }


async def test_get_repositories_commit_per_branch_repository_created_on_a_branch(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch, default_branch: Branch
) -> None:
    """A repository created on a user branch, and staged there, is still read off the default branch.

    The repository kinds are branch-agnostic, so the node lands on the global branch whatever branch
    it was created from and the single default-branch query for the nodes finds it. Were that not
    so, the repository would drop out of the result with no error at all.
    """
    branch = await create_branch(db=db, branch_name="branch-that-adds-a-repository")
    repo = await Node.init(db=db, schema=InfrahubKind.REPOSITORY, branch=branch)
    await repo.new(
        db=db,
        name="repo-on-branch",
        default_branch=default_branch.name,
        commit="commit-on-branch",
        location="location-on-branch",
    )
    await repo.save(db=db)

    repo_on_branch = await NodeManager.get_one(db=db, id=repo.id, branch=branch)
    repo_on_branch.internal_status.value = RepositoryInternalStatus.STAGING.value
    await repo_on_branch.save(db=db)

    repositories = await get_repositories_commit_per_branch(db=db)

    assert set(repositories) == {"repo-on-branch"}
    assert repositories["repo-on-branch"].model_dump(exclude=["repository"]) == {
        "repository_id": repo.id,
        "repository_name": "repo-on-branch",
        "branches": {
            "branch-that-adds-a-repository": "commit-on-branch",
            "main": "commit-on-branch",
        },
        "branch_info": {
            "branch-that-adds-a-repository": {"internal_status": "staging"},
            "main": {"internal_status": "inactive"},
        },
    }


async def test_get_repositories_commit_per_branch_without_a_commit_on_a_branch(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch, repository_01: Node
) -> None:
    """A branch that holds no commit is reported with no commit rather than dropped from the result."""
    branch = await create_branch(db=db, branch_name="branch-without-commit")
    repo_on_branch = await NodeManager.get_one(db=db, id=repository_01.id, branch=branch)
    repo_on_branch.commit.value = None
    await repo_on_branch.save(db=db)

    repositories = await get_repositories_commit_per_branch(db=db)

    assert repositories["repo01"].model_dump(exclude=["repository"]) == {
        "repository_id": repository_01.id,
        "repository_name": "repo01",
        "branches": {
            "branch-without-commit": None,
            "main": "commit01",
        },
        "branch_info": {
            "branch-without-commit": {"internal_status": "inactive"},
            "main": {"internal_status": "inactive"},
        },
    }


async def test_get_repositories_commit_per_branch_reads_the_branch_agnostic_node_fields(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch, repository_01: Node, repository_02: Node
) -> None:
    """The node read carries every branch-agnostic field a caller needs, `operational_status` included.

    An unrequested field reads back its schema default rather than raising, so a field a caller uses
    but the read does not ask for looks like a legitimate value.
    """
    repository_01.operational_status.value = RepositoryOperationalStatus.ONLINE.value
    await repository_01.save(db=db)

    repositories = await get_repositories_commit_per_branch(db=db)

    assert repositories["repo01"].repository.default_branch.value == "main"
    assert repositories["repo01"].repository.location.value == "location01"
    assert repositories["repo01"].repository.operational_status.value == RepositoryOperationalStatus.ONLINE.value
    assert repositories["repo02"].repository.location.value == "location02"
    assert repositories["repo02"].repository.operational_status.value == RepositoryOperationalStatus.UNKNOWN.value


async def test_get_repositories_commit_per_branch_reads_the_branches_in_chunks(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch, repository_01: Node, repository_02: Node
) -> None:
    """The per-branch reads are batched into chunks, the last of them partial, not one per branch."""
    for index in range(BRANCH_COUNT - 1):
        branch = Branch(
            name=f"chunked-branch-{index:03d}",
            description=f"Branch chunked-branch-{index:03d}",
            hierarchy_level=2,
            is_default=False,
            sync_with_git=True,
        )
        await branch.save(db=db)
        registry.branch[branch.name] = branch

    branch_names = [name for name in registry.branch if name != GLOBAL_BRANCH_NAME]
    assert len(branch_names) == BRANCH_COUNT

    counting_db = CountingInfrahubDatabase.from_db(db=db)
    repositories = await get_repositories_commit_per_branch(db=counting_db)

    assert set(repositories) == {"repo01", "repo02"}
    assert repositories["repo01"].branches == dict.fromkeys(branch_names, "commit01")
    assert repositories["repo02"].branches == dict.fromkeys(branch_names, "commit02")
    assert counting_db.count_for(ATTRIBUTES_QUERY_NAME) == EXPECTED_ATTRIBUTES_QUERY_COUNT
    assert counting_db.count_for(REPOSITORY_NODES_QUERY_NAME) == 1
