from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.branch.models import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME, MetadataOptions, RepositorySyncStatus
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreRepository
from infrahub.core.query.repository import RepositoryBranchAttributesQuery
from infrahub.core.repository_branch_status.reader import RepositoryBranchAttributesReader
from infrahub.core.timestamp import Timestamp
from tests.helpers.db_query_counter import CountingInfrahubDatabase

if TYPE_CHECKING:
    from collections.abc import Generator

    from infrahub.database import InfrahubDatabase
    from tests.component.conftest import RepositoryBranchStatusBranches

QUERY_NAME = RepositoryBranchAttributesQuery.name

SCALE_BRANCH_COUNT = 200
SMALL_BRANCH_COUNT = 5


@dataclass(frozen=True)
class ScaleFixture:
    """A repository and the branches forked after it, so every branch resolves a value."""

    repository_id: str
    """UUID of the repository the branches inherit their commit from."""

    branch_names: tuple[str, ...]
    """Branch names, all forked after the repository was written."""


def _reader(db: InfrahubDatabase) -> RepositoryBranchAttributesReader:
    return RepositoryBranchAttributesReader(
        db=db, default_branch_name=registry.default_branch, global_branch_name=GLOBAL_BRANCH_NAME
    )


async def _create_repository(db: InfrahubDatabase, name: str, commit: str | None = None) -> CoreRepository:
    repository = await Node.init(db=db, schema=CoreRepository)
    await repository.new(db=db, name=name, location=f"git@github.com:opsmill/{name}.git", commit=commit)
    await repository.save(db=db)
    return repository


async def _import_commit(db: InfrahubDatabase, repository_id: str, branch_name: str, commit: str) -> None:
    repository = await NodeManager.get_one(
        db=db, id=repository_id, kind=CoreRepository, branch=branch_name, raise_on_error=True
    )
    repository.commit.value = commit
    await repository.save(db=db)


@pytest.fixture(autouse=True)
def branch_registry_restored(
    repository_branch_status_branches: RepositoryBranchStatusBranches,
) -> Generator[None, None, None]:
    """Undo the branch-cache entries a test adds, so the tests stay independent of each other."""
    original = dict(registry.branch)
    yield
    registry.branch.clear()
    registry.branch.update(original)


@pytest.fixture(scope="module")
async def scale_branches(
    db: InfrahubDatabase,
    repository_branch_status_branches: RepositoryBranchStatusBranches,
) -> ScaleFixture:
    """A repository written before two hundred branches fork from the default branch."""
    repository = await _create_repository(db=db, name="rbap-scale-repository", commit="scale-commit")

    names = tuple(f"rbap-scale-{index:03d}" for index in range(SCALE_BRANCH_COUNT))
    for name in names:
        branch = Branch(name=name, description=f"branch {name}", is_default=False, sync_with_git=True)
        await branch.save(db=db)

    return ScaleFixture(repository_id=repository.id, branch_names=names)


class TestRepositoryBranchAttributesReader:
    async def test_direct_call_with_two_branch_names_and_one_attribute(
        self, db: InfrahubDatabase, repository_branch_status_branches: RepositoryBranchStatusBranches
    ) -> None:
        default_branch_name = repository_branch_status_branches.default_branch.name
        repository = await _create_repository(db=db, name="rbap-direct-call", commit="commit-on-main")
        branch2 = await create_branch(branch_name="rbap-direct-call-branch2", db=db)
        await _import_commit(db=db, repository_id=repository.id, branch_name=branch2.name, commit="commit21")

        result = await _reader(db=db).read(
            repository_ids=[repository.id],
            branch_names=[default_branch_name, branch2.name],
            attribute_names={"commit"},
        )

        on_branch2 = result.get(repository.id, branch2.name, "commit")
        on_main = result.get(repository.id, default_branch_name, "commit")
        assert on_branch2
        assert on_main
        assert on_branch2.value == "commit21"
        assert on_branch2.own_value is True
        assert on_main.value == "commit-on-main"
        # A read-write repository's commit is a LOCAL attribute on a branch-agnostic node, so
        # creation writes it on the global branch and the default branch inherits it.
        assert on_main.own_value is False

    async def test_a_branch_inherits_the_default_branch_value_from_its_fork_point(
        self, db: InfrahubDatabase, repository_branch_status_branches: RepositoryBranchStatusBranches
    ) -> None:
        default_branch_name = repository_branch_status_branches.default_branch.name
        repository = await _create_repository(db=db, name="rbap-inheritance")

        await _import_commit(db=db, repository_id=repository.id, branch_name=default_branch_name, commit="c1")
        first_import = await _reader(db=db).read(
            repository_ids=[repository.id], branch_names=[default_branch_name], attribute_names={"commit"}
        )
        c1_written_at = first_import.get(repository.id, default_branch_name, "commit")
        assert c1_written_at

        b1 = await create_branch(branch_name="rbap-inheritance-b1", db=db)
        await _import_commit(db=db, repository_id=repository.id, branch_name=default_branch_name, commit="c2")
        b2 = await create_branch(branch_name="rbap-inheritance-b2", db=db)

        result = await _reader(db=db).read(
            repository_ids=[repository.id],
            branch_names=[default_branch_name, b1.name, b2.name],
            attribute_names={"commit"},
        )

        on_main = result.get(repository.id, default_branch_name, "commit")
        on_b1 = result.get(repository.id, b1.name, "commit")
        on_b2 = result.get(repository.id, b2.name, "commit")
        assert on_main
        assert on_b1
        assert on_b2
        assert on_main.value == "c2"
        assert on_main.own_value is True
        assert on_b1.value == "c1"
        assert on_b1.own_value is False
        assert on_b1.updated_at == c1_written_at.updated_at
        assert on_b2.value == "c2"
        assert on_b2.own_value is False

    async def test_an_own_import_survives_while_a_rebase_moves_another_branch_forward(
        self, db: InfrahubDatabase, repository_branch_status_branches: RepositoryBranchStatusBranches
    ) -> None:
        default_branch_name = repository_branch_status_branches.default_branch.name
        repository = await _create_repository(db=db, name="rbap-rebase")

        await _import_commit(db=db, repository_id=repository.id, branch_name=default_branch_name, commit="c1")
        b1 = await create_branch(branch_name="rbap-rebase-b1", db=db)
        await _import_commit(db=db, repository_id=repository.id, branch_name=default_branch_name, commit="c2")
        b2 = await create_branch(branch_name="rbap-rebase-b2", db=db)

        await _import_commit(db=db, repository_id=repository.id, branch_name=b1.name, commit="c3")
        await b2.rebase(db=db)

        result = await _reader(db=db).read(
            repository_ids=[repository.id],
            branch_names=[default_branch_name, b1.name, b2.name],
            attribute_names={"commit"},
        )

        on_b1 = result.get(repository.id, b1.name, "commit")
        on_b2 = result.get(repository.id, b2.name, "commit")
        assert on_b1
        assert on_b2
        assert on_b1.value == "c3"
        assert on_b1.own_value is True
        assert on_b2.value == "c2"
        assert on_b2.own_value is False

    async def test_a_repository_that_was_never_imported_resolves_to_no_commit(
        self, db: InfrahubDatabase, repository_branch_status_branches: RepositoryBranchStatusBranches
    ) -> None:
        default_branch_name = repository_branch_status_branches.default_branch.name
        repository = await _create_repository(db=db, name="rbap-never-imported")

        result = await _reader(db=db).read(
            repository_ids=[repository.id],
            branch_names=[default_branch_name],
            attribute_names={"commit", "sync_status"},
        )

        commit = result.get(repository.id, default_branch_name, "commit")
        sync_status = result.get(repository.id, default_branch_name, "sync_status")
        assert commit
        assert sync_status
        assert commit.value is None
        assert sync_status.value == RepositorySyncStatus.UNKNOWN.value

    async def test_a_branch_name_with_no_branch_node_yields_no_row(
        self, db: InfrahubDatabase, repository_branch_status_branches: RepositoryBranchStatusBranches
    ) -> None:
        default_branch_name = repository_branch_status_branches.default_branch.name
        repository = await _create_repository(db=db, name="rbap-unknown-branch", commit="commit-on-main")

        result = await _reader(db=db).read(
            repository_ids=[repository.id],
            branch_names=[default_branch_name, "rbap-no-such-branch"],
            attribute_names={"commit"},
        )

        assert result.get(repository.id, "rbap-no-such-branch", "commit") is None
        assert result.for_branch(repository_id=repository.id, branch_name="rbap-no-such-branch") == {}
        on_main = result.get(repository.id, default_branch_name, "commit")
        assert on_main
        assert on_main.value == "commit-on-main"

    async def test_an_empty_branch_name_list_executes_no_query(
        self, db: InfrahubDatabase, repository_branch_status_branches: RepositoryBranchStatusBranches
    ) -> None:
        repository = await _create_repository(db=db, name="rbap-no-branch-names", commit="commit-on-main")
        counting_db = CountingInfrahubDatabase.from_db(db=db)

        result = await _reader(db=counting_db).read(
            repository_ids=[repository.id], branch_names=[], attribute_names={"commit"}
        )

        assert result.values == {}
        assert counting_db.count_for(QUERY_NAME) == 0
        assert sum(counting_db.query_counts.values()) == 0

    async def test_an_empty_attribute_name_list_executes_no_query(
        self, db: InfrahubDatabase, repository_branch_status_branches: RepositoryBranchStatusBranches
    ) -> None:
        default_branch_name = repository_branch_status_branches.default_branch.name
        repository = await _create_repository(db=db, name="rbap-no-attribute-names", commit="commit-on-main")
        counting_db = CountingInfrahubDatabase.from_db(db=db)

        result = await _reader(db=counting_db).read(
            repository_ids=[repository.id], branch_names=[default_branch_name], attribute_names=set()
        )

        assert result.values == {}
        assert counting_db.count_for(QUERY_NAME) == 0
        assert sum(counting_db.query_counts.values()) == 0

    async def test_two_repositories_are_resolved_in_one_call(
        self, db: InfrahubDatabase, repository_branch_status_branches: RepositoryBranchStatusBranches
    ) -> None:
        default_branch_name = repository_branch_status_branches.default_branch.name
        first = await _create_repository(db=db, name="rbap-pair-first", commit="first-commit")
        second = await _create_repository(db=db, name="rbap-pair-second", commit="second-commit")
        branch = await create_branch(branch_name="rbap-pair-branch", db=db)
        counting_db = CountingInfrahubDatabase.from_db(db=db)

        result = await _reader(db=counting_db).read(
            repository_ids=[first.id, second.id],
            branch_names=[default_branch_name, branch.name],
            attribute_names={"commit"},
        )

        values = {
            (repository_id, branch_name): result.get(repository_id, branch_name, "commit")
            for repository_id in (first.id, second.id)
            for branch_name in (default_branch_name, branch.name)
        }
        assert {key: value.value for key, value in values.items() if value} == {
            (first.id, default_branch_name): "first-commit",
            (first.id, branch.name): "first-commit",
            (second.id, default_branch_name): "second-commit",
            (second.id, branch.name): "second-commit",
        }
        assert counting_db.count_for(QUERY_NAME) == 1

    async def test_the_query_count_does_not_grow_with_the_branch_count(
        self, db: InfrahubDatabase, scale_branches: ScaleFixture
    ) -> None:
        small_db = CountingInfrahubDatabase.from_db(db=db)
        large_db = CountingInfrahubDatabase.from_db(db=db)

        small = await _reader(db=small_db).read(
            repository_ids=[scale_branches.repository_id],
            branch_names=list(scale_branches.branch_names[:SMALL_BRANCH_COUNT]),
            attribute_names={"commit"},
        )
        large = await _reader(db=large_db).read(
            repository_ids=[scale_branches.repository_id],
            branch_names=list(scale_branches.branch_names),
            attribute_names={"commit"},
        )

        assert len(small.values) == SMALL_BRANCH_COUNT
        assert len(large.values) == SCALE_BRANCH_COUNT
        assert sum(small_db.query_counts.values()) == sum(large_db.query_counts.values())
        assert small_db.count_for(QUERY_NAME) == large_db.count_for(QUERY_NAME) == 1
        assert small_db.rows_for(QUERY_NAME) == SMALL_BRANCH_COUNT
        assert large_db.rows_for(QUERY_NAME) == SCALE_BRANCH_COUNT


class TestRepositoryBranchAttributesMatchTheStandardRead:
    async def test_commit_matches_the_standard_read_on_every_branch(
        self, db: InfrahubDatabase, repository_branch_status_branches: RepositoryBranchStatusBranches
    ) -> None:
        """The cross-branch read must agree with the standard node read, legacy branches included."""
        branches = repository_branch_status_branches
        default_branch_name = branches.default_branch.name
        repository = await _create_repository(db=db, name="rbap-differential", commit="created-commit")
        # The import lands on the default branch itself, so only the branches whose window reaches it
        # see it; the others fall back to the creation value on the global branch.
        await _import_commit(
            db=db, repository_id=repository.id, branch_name=default_branch_name, commit="imported-commit"
        )

        branch_names = [
            default_branch_name,
            *branches.five,
            *branches.two_hundred,
            branches.non_syncing,
            *branches.by_status.values(),
            branches.legacy_non_isolated,
        ]
        for name in branch_names:
            if name not in registry.branch:
                registry.branch[name] = await Branch.get_by_name(name=name, db=db, ignore_deleting=False)

        resolved = await _reader(db=db).read(
            repository_ids=[repository.id], branch_names=branch_names, attribute_names={"commit"}
        )

        expected: dict[str, tuple[str | None, str | None]] = {}
        observed: dict[str, tuple[str | None, str | None]] = {}
        for name in branch_names:
            node = await NodeManager.get_one(
                db=db,
                id=repository.id,
                kind=CoreRepository,
                branch=name,
                include_metadata=MetadataOptions.UPDATED_AT,
                raise_on_error=True,
            )
            updated_at = node.commit._get_updated_at()
            expected[name] = (node.commit.value, Timestamp(updated_at).to_string() if updated_at else None)

            value = resolved.get(repository.id, name, "commit")
            observed[name] = (
                (value.value, Timestamp(value.updated_at).to_string() if value.updated_at else None)
                if value
                else (None, None)
            )

        assert observed == expected
        assert expected[default_branch_name][0] == "imported-commit"
        assert expected[branches.legacy_non_isolated] == expected[default_branch_name]
        assert {value for value, _ in expected.values()} == {"imported-commit", "created-commit"}
        assert expected[branches.five[0]][0] == "created-commit"
