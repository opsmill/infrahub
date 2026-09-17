from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub import config
from infrahub.core.constants import GLOBAL_BRANCH_NAME, InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.repository import BranchScope, RepositoryBranchValue, RepositoryBranchValuesQuery
from infrahub.core.timestamp import Timestamp
from tests.helpers.db_query_counter import CountingInfrahubDatabase

if TYPE_CHECKING:
    from collections.abc import Iterator

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

REPOSITORY_NAME = "repo-branch-values"
REPOSITORY_LOCATION = "/tmp/repo-branch-values"
REPOSITORY_DEFAULT_BRANCH = "trunk"

CREATION_COMMIT = "0000000000000000000000000000000000000000"
MAIN_COMMIT = "1111111111111111111111111111111111111111"
BRANCH_COMMIT = "2222222222222222222222222222222222222222"
LATER_MAIN_COMMIT = "3333333333333333333333333333333333333333"

MAIN_REF = "v1.0"
BRANCH_REF = "v2.0"

BEFORE_THE_REPOSITORY_EXISTED = "2020-01-01T00:00:00Z"


@pytest.fixture
def tiny_query_size_limit() -> Iterator[None]:
    """Page unbounded reads after two rows, so a read that lost its own bound issues extra queries."""
    original = config.SETTINGS.database.query_size_limit
    config.SETTINGS.database.query_size_limit = 2
    yield
    config.SETTINGS.database.query_size_limit = original


@pytest.fixture
async def repository(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None, data_schema: None
) -> Node:
    repo = await Node.init(db=db, schema=InfrahubKind.REPOSITORY, branch=default_branch)
    await repo.new(
        db=db,
        name=REPOSITORY_NAME,
        location=REPOSITORY_LOCATION,
        default_branch=REPOSITORY_DEFAULT_BRANCH,
        commit=CREATION_COMMIT,
    )
    await repo.save(db=db)

    # commit is LOCAL on a branch-agnostic node, so its creation edge lands on the global branch.
    # The import that follows a repository's creation is what puts an edge on the default branch.
    repo.commit.value = MAIN_COMMIT
    await repo.save(db=db)

    return repo


@pytest.fixture
async def untracked_repository(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None, data_schema: None
) -> Node:
    repo = await Node.init(db=db, schema=InfrahubKind.REPOSITORY, branch=default_branch)
    await repo.new(db=db, name=REPOSITORY_NAME, location=REPOSITORY_LOCATION, default_branch=REPOSITORY_DEFAULT_BRANCH)
    await repo.save(db=db)
    return repo


@pytest.fixture
async def read_only_repository(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None, data_schema: None
) -> Node:
    repo = await Node.init(db=db, schema=InfrahubKind.READONLYREPOSITORY, branch=default_branch)
    await repo.new(db=db, name=REPOSITORY_NAME, location=REPOSITORY_LOCATION, ref=MAIN_REF, commit=MAIN_COMMIT)
    await repo.save(db=db)
    return repo


async def _resolve(
    db: InfrahubDatabase,
    repository_id: str,
    branches: list[Branch],
    attribute_names: set[str],
) -> dict[tuple[str, str], RepositoryBranchValue]:
    at = Timestamp()
    query = await RepositoryBranchValuesQuery.init(
        db=db,
        branch=branches[0],
        at=at,
        repository_id=repository_id,
        branch_scopes=[BranchScope.from_branch(branch=branch, at=at) for branch in branches],
        attribute_names=attribute_names,
    )
    await query.execute(db=db)
    return {(row.branch_name, row.attribute_name): row for row in query.get_data()}


async def _set_commit(db: InfrahubDatabase, repository: Node, branch: Branch, commit: str) -> None:
    repo_on_branch = await NodeManager.get_one(db=db, id=repository.id, branch=branch, raise_on_error=True)
    repo_on_branch.commit.value = commit
    await repo_on_branch.save(db=db)


async def test_branch_reports_the_commit_it_imported_itself(
    db: InfrahubDatabase, default_branch: Branch, repository: Node
) -> None:
    branch = await create_branch(branch_name="branch2", db=db)
    await _set_commit(db=db, repository=repository, branch=branch, commit=BRANCH_COMMIT)

    values = await _resolve(
        db=db, repository_id=repository.id, branches=[default_branch, branch], attribute_names={"commit"}
    )

    assert values == {
        (default_branch.name, "commit"): RepositoryBranchValue(
            branch_name=default_branch.name,
            attribute_name="commit",
            value=MAIN_COMMIT,
            source_branch=default_branch.name,
        ),
        ("branch2", "commit"): RepositoryBranchValue(
            branch_name="branch2", attribute_name="commit", value=BRANCH_COMMIT, source_branch="branch2"
        ),
    }


async def test_branch_that_never_imported_inherits_the_fork_point_value(
    db: InfrahubDatabase, default_branch: Branch, repository: Node
) -> None:
    branch = await create_branch(branch_name="branch2", db=db)

    values = await _resolve(
        db=db, repository_id=repository.id, branches=[default_branch, branch], attribute_names={"commit"}
    )

    assert values["branch2", "commit"] == RepositoryBranchValue(
        branch_name="branch2", attribute_name="commit", value=MAIN_COMMIT, source_branch=default_branch.name
    )


async def test_inherited_value_stays_at_the_fork_point_after_a_later_default_branch_import(
    db: InfrahubDatabase, default_branch: Branch, repository: Node
) -> None:
    branch = await create_branch(branch_name="branch2", db=db)
    await _set_commit(db=db, repository=repository, branch=default_branch, commit=LATER_MAIN_COMMIT)

    values = await _resolve(
        db=db, repository_id=repository.id, branches=[default_branch, branch], attribute_names={"commit"}
    )

    assert values == {
        (default_branch.name, "commit"): RepositoryBranchValue(
            branch_name=default_branch.name,
            attribute_name="commit",
            value=LATER_MAIN_COMMIT,
            source_branch=default_branch.name,
        ),
        ("branch2", "commit"): RepositoryBranchValue(
            branch_name="branch2", attribute_name="commit", value=MAIN_COMMIT, source_branch=default_branch.name
        ),
    }


async def test_inherited_value_follows_the_default_branch_after_a_rebase(
    db: InfrahubDatabase, default_branch: Branch, repository: Node
) -> None:
    branch = await create_branch(branch_name="branch2", db=db)
    await _set_commit(db=db, repository=repository, branch=default_branch, commit=LATER_MAIN_COMMIT)

    await branch.rebase(db=db)

    values = await _resolve(
        db=db, repository_id=repository.id, branches=[default_branch, branch], attribute_names={"commit"}
    )

    assert values["branch2", "commit"] == RepositoryBranchValue(
        branch_name="branch2", attribute_name="commit", value=LATER_MAIN_COMMIT, source_branch=default_branch.name
    )


async def test_read_only_repository_reports_each_branch_own_ref(
    db: InfrahubDatabase, default_branch: Branch, read_only_repository: Node
) -> None:
    branch = await create_branch(branch_name="branch2", db=db)
    repo_on_branch = await NodeManager.get_one(db=db, id=read_only_repository.id, branch=branch, raise_on_error=True)
    repo_on_branch.ref.value = BRANCH_REF
    repo_on_branch.commit.value = BRANCH_COMMIT
    await repo_on_branch.save(db=db)

    values = await _resolve(
        db=db,
        repository_id=read_only_repository.id,
        branches=[default_branch, branch],
        attribute_names={"commit", "ref"},
    )

    assert values == {
        (default_branch.name, "commit"): RepositoryBranchValue(
            branch_name=default_branch.name,
            attribute_name="commit",
            value=MAIN_COMMIT,
            source_branch=default_branch.name,
        ),
        (default_branch.name, "ref"): RepositoryBranchValue(
            branch_name=default_branch.name, attribute_name="ref", value=MAIN_REF, source_branch=default_branch.name
        ),
        ("branch2", "commit"): RepositoryBranchValue(
            branch_name="branch2", attribute_name="commit", value=BRANCH_COMMIT, source_branch="branch2"
        ),
        ("branch2", "ref"): RepositoryBranchValue(
            branch_name="branch2", attribute_name="ref", value=BRANCH_REF, source_branch="branch2"
        ),
    }


@pytest.mark.parametrize("branch_count", [5, 20])
async def test_one_execution_whatever_the_branch_count(
    db: InfrahubDatabase, default_branch: Branch, repository: Node, branch_count: int, tiny_query_size_limit: None
) -> None:
    """The read must cost one round trip however many branches it covers.

    `query_size_limit` is lowered under both cases so that a read which lost its own bound would
    page, and be caught here rather than passing because the default page is larger than the fixture.
    """
    branches = [default_branch]
    for index in range(branch_count - 1):
        branches.append(await create_branch(branch_name=f"branch{index}", db=db))

    counting_db = CountingInfrahubDatabase.from_db(db=db)
    values = await _resolve(db=counting_db, repository_id=repository.id, branches=branches, attribute_names={"commit"})

    assert counting_db.count_for(RepositoryBranchValuesQuery.name) == 1
    assert counting_db.rows_for(RepositoryBranchValuesQuery.name) == branch_count
    assert {value.value for value in values.values()} == {MAIN_COMMIT}


async def test_branch_that_resolves_nothing_reports_no_source_branch(
    db: InfrahubDatabase, default_branch: Branch, read_only_repository: Node
) -> None:
    """A branch forked before a read-only repository existed resolves no edge, and is still a row.

    The read-only kind overrides `ref` and `commit` to AWARE, so their creation edges land on the
    default branch and the fork point hides them. A read-write `commit` is LOCAL, whose creation edge
    goes to the global branch and is therefore visible from a branch that forked before the node.
    """
    branch = await create_branch(branch_name="branch2", db=db, at=BEFORE_THE_REPOSITORY_EXISTED)

    values = await _resolve(
        db=db,
        repository_id=read_only_repository.id,
        branches=[default_branch, branch],
        attribute_names={"commit", "ref"},
    )

    assert values["branch2", "commit"] == RepositoryBranchValue(
        branch_name="branch2", attribute_name="commit", value=None, source_branch=None
    )
    assert values["branch2", "ref"] == RepositoryBranchValue(
        branch_name="branch2", attribute_name="ref", value=None, source_branch=None
    )


async def test_attribute_with_no_value_reports_none_rather_than_the_stored_marker(
    db: InfrahubDatabase, default_branch: Branch, untracked_repository: Node
) -> None:
    """An unset optional attribute is stored as a marker string, which must not reach a caller.

    Its edge sits on the global branch: a LOCAL attribute of a branch-agnostic node is created there,
    and nothing has updated this one since.
    """
    values = await _resolve(
        db=db, repository_id=untracked_repository.id, branches=[default_branch], attribute_names={"commit"}
    )

    assert values[default_branch.name, "commit"] == RepositoryBranchValue(
        branch_name=default_branch.name, attribute_name="commit", value=None, source_branch=GLOBAL_BRANCH_NAME
    )


async def test_duplicate_branch_scopes_are_refused(
    db: InfrahubDatabase, default_branch: Branch, repository: Node
) -> None:
    at = Timestamp()
    scope = BranchScope.from_branch(branch=default_branch, at=at)

    with pytest.raises(ValueError, match=rf"^branch_scopes names {default_branch.name} more than once$"):
        await RepositoryBranchValuesQuery.init(
            db=db,
            branch=default_branch,
            at=at,
            repository_id=repository.id,
            branch_scopes=[scope, scope],
            attribute_names={"commit"},
        )


async def test_paging_arguments_are_refused(db: InfrahubDatabase, default_branch: Branch, repository: Node) -> None:
    at = Timestamp()

    with pytest.raises(ValueError, match=r"^limit, offset not supported: the read returns every matching row$"):
        await RepositoryBranchValuesQuery.init(
            db=db,
            branch=default_branch,
            at=at,
            limit=10,
            offset=5,
            repository_id=repository.id,
            branch_scopes=[BranchScope.from_branch(branch=default_branch, at=at)],
            attribute_names={"commit"},
        )
