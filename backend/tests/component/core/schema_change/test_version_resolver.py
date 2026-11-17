from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.schema_change.enums import SchemaChangeStatus
from infrahub.core.schema_change.repository import SchemaChangeRepository
from infrahub.core.schema_change.version_resolver import SchemaChangeVersion, SchemaChangeVersionResolver
from infrahub.core.timestamp import Timestamp
from tests.helpers.schema_change import BranchHistorySeed, SeededSchemaChangeHistory, seed_schema_change_history

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

APPLIED = SchemaChangeStatus.APPLIED

MAIN_WITH_VERSIONS = "main-with-versions"
MAIN_BRANCHED_AT_VERSION_2 = "main-branched-at-version-2"
BRANCH_WITHOUT_CHANGE = "branch-without-change"
BRANCH_WITHOUT_CHANGE_TWIN = "branch-without-change-twin"
BRANCH_WITH_APPLIED_CHANGE = "branch-with-applied-change"
MAIN_APPLIED_BEFORE_BRANCH = "main-applied-before-branch"
BRANCH_CREATED_AFTER_LOAD = "branch-created-after-load"
BRANCH_CREATED_AT_LOAD = "branch-created-at-load"
MAIN_APPLIED_AFTER_BRANCH = "main-applied-after-branch"
BRANCH_CREATED_BEFORE_LOAD = "branch-created-before-load"
MAIN_WITH_UNFINISHED_CHANGES = "main-with-unfinished-changes"
BRANCH_WITH_UNFINISHED_CHANGES = "branch-with-unfinished-changes"


@dataclass
class ResolverCases:
    branches: dict[str, Branch] = field(default_factory=dict)
    history: SeededSchemaChangeHistory = field(default_factory=SeededSchemaChangeHistory)

    def add_history(self, history: SeededSchemaChangeHistory) -> None:
        self.history.schema_changes.extend(history.schema_changes)

    def applied(self, branch: str, version: int) -> str:
        """Return the ID of the applied schema change of a branch with that version."""
        (schema_change,) = [change for change in self.history.applied_on_branch(branch) if change.version == version]
        return schema_change.id


async def _create_branch(
    db: InfrahubDatabase, cases: ResolverCases, name: str, branched_from: str | None = None
) -> None:
    branch = Branch(
        name=name,
        status=BranchStatus.OPEN,
        hierarchy_level=2,
        is_default=False,
        branched_from=branched_from or Timestamp().to_string(),
    )
    await branch.save(db=db)
    cases.branches[name] = branch


async def _seed(db: InfrahubDatabase, cases: ResolverCases, *seeds: BranchHistorySeed) -> SeededSchemaChangeHistory:
    history = await seed_schema_change_history(db=db, branches=seeds)
    cases.add_history(history)
    return history


def _resolver(db: InfrahubDatabase, default_branch_name: str) -> SchemaChangeVersionResolver:
    return SchemaChangeVersionResolver(
        repository=SchemaChangeRepository(db=db), default_branch_name=default_branch_name
    )


@pytest.fixture(scope="class")
async def resolver_cases(db: InfrahubDatabase, default_branch_scope_class: Branch) -> ResolverCases:
    """Seed each case under a main branch of its own, which the resolver of the case receives as its default branch."""
    cases = ResolverCases(branches={default_branch_scope_class.name: default_branch_scope_class})

    await _create_branch(db=db, cases=cases, name=MAIN_WITH_VERSIONS)
    await _seed(db, cases, BranchHistorySeed(branch=MAIN_WITH_VERSIONS, changes=[APPLIED, APPLIED, APPLIED]))

    await _create_branch(db=db, cases=cases, name=MAIN_BRANCHED_AT_VERSION_2)
    await _seed(db, cases, BranchHistorySeed(branch=MAIN_BRANCHED_AT_VERSION_2, changes=[APPLIED, APPLIED]))
    for name in (BRANCH_WITHOUT_CHANGE, BRANCH_WITHOUT_CHANGE_TWIN, BRANCH_WITH_APPLIED_CHANGE):
        await _create_branch(db=db, cases=cases, name=name)
    await _seed(
        db,
        cases,
        BranchHistorySeed(
            branch=MAIN_BRANCHED_AT_VERSION_2,
            changes=[APPLIED],
            first_version=3,
            first_parent_id=cases.applied(MAIN_BRANCHED_AT_VERSION_2, 2),
        ),
        BranchHistorySeed(
            branch=BRANCH_WITH_APPLIED_CHANGE,
            changes=[APPLIED],
            first_version=3,
            first_parent_id=cases.applied(MAIN_BRANCHED_AT_VERSION_2, 2),
        ),
    )

    await _create_branch(db=db, cases=cases, name=MAIN_APPLIED_BEFORE_BRANCH)
    main_load = await _seed(db, cases, BranchHistorySeed(branch=MAIN_APPLIED_BEFORE_BRANCH, changes=[APPLIED]))
    await _create_branch(db=db, cases=cases, name=BRANCH_CREATED_AFTER_LOAD)
    await _create_branch(
        db=db, cases=cases, name=BRANCH_CREATED_AT_LOAD, branched_from=main_load.schema_changes[0].at.to_string()
    )

    await _create_branch(db=db, cases=cases, name=MAIN_APPLIED_AFTER_BRANCH)
    await _create_branch(db=db, cases=cases, name=BRANCH_CREATED_BEFORE_LOAD)
    await _seed(db, cases, BranchHistorySeed(branch=MAIN_APPLIED_AFTER_BRANCH, changes=[APPLIED]))

    unfinished = [SchemaChangeStatus.FAILED, SchemaChangeStatus.RUNNING]
    await _create_branch(db=db, cases=cases, name=MAIN_WITH_UNFINISHED_CHANGES)
    await _seed(db, cases, BranchHistorySeed(branch=MAIN_WITH_UNFINISHED_CHANGES, changes=[APPLIED, *unfinished]))
    await _create_branch(db=db, cases=cases, name=BRANCH_WITH_UNFINISHED_CHANGES)
    await _seed(db, cases, BranchHistorySeed(branch=BRANCH_WITH_UNFINISHED_CHANGES, changes=unfinished))

    return cases


class TestSchemaChangeVersionResolver:
    async def test_main_without_schema_change_gives_version_1_without_parent(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, resolver_cases: ResolverCases
    ) -> None:
        resolver = _resolver(db=db, default_branch_name=default_branch_scope_class.name)

        version = await resolver.resolve_next(branch=resolver_cases.branches[default_branch_scope_class.name])

        assert version == SchemaChangeVersion(version=1, parent_id=None)

    async def test_main_gives_its_highest_version_plus_1_with_that_schema_change_as_parent(
        self, db: InfrahubDatabase, resolver_cases: ResolverCases
    ) -> None:
        resolver = _resolver(db=db, default_branch_name=MAIN_WITH_VERSIONS)

        version = await resolver.resolve_next(branch=resolver_cases.branches[MAIN_WITH_VERSIONS])

        assert version == SchemaChangeVersion(version=4, parent_id=resolver_cases.applied(MAIN_WITH_VERSIONS, 3))

    async def test_branch_numbers_after_main_at_its_creation_then_after_its_own_versions(
        self, db: InfrahubDatabase, resolver_cases: ResolverCases
    ) -> None:
        resolver = _resolver(db=db, default_branch_name=MAIN_BRANCHED_AT_VERSION_2)

        without_change = await resolver.resolve_next(branch=resolver_cases.branches[BRANCH_WITHOUT_CHANGE])
        with_applied_change = await resolver.resolve_next(branch=resolver_cases.branches[BRANCH_WITH_APPLIED_CHANGE])

        assert without_change == SchemaChangeVersion(
            version=3, parent_id=resolver_cases.applied(MAIN_BRANCHED_AT_VERSION_2, 2)
        )
        assert with_applied_change == SchemaChangeVersion(
            version=4, parent_id=resolver_cases.applied(BRANCH_WITH_APPLIED_CHANGE, 3)
        )

    async def test_two_branches_created_from_the_same_version_of_main_give_the_same_version(
        self, db: InfrahubDatabase, resolver_cases: ResolverCases
    ) -> None:
        resolver = _resolver(db=db, default_branch_name=MAIN_BRANCHED_AT_VERSION_2)
        expected = SchemaChangeVersion(version=3, parent_id=resolver_cases.applied(MAIN_BRANCHED_AT_VERSION_2, 2))

        assert await resolver.resolve_next(branch=resolver_cases.branches[BRANCH_WITHOUT_CHANGE]) == expected
        assert await resolver.resolve_next(branch=resolver_cases.branches[BRANCH_WITHOUT_CHANGE_TWIN]) == expected

    async def test_branch_counts_a_schema_change_of_main_applied_at_or_before_its_creation(
        self, db: InfrahubDatabase, resolver_cases: ResolverCases
    ) -> None:
        resolver = _resolver(db=db, default_branch_name=MAIN_APPLIED_BEFORE_BRANCH)
        expected = SchemaChangeVersion(version=2, parent_id=resolver_cases.applied(MAIN_APPLIED_BEFORE_BRANCH, 1))

        assert await resolver.resolve_next(branch=resolver_cases.branches[BRANCH_CREATED_AFTER_LOAD]) == expected
        assert await resolver.resolve_next(branch=resolver_cases.branches[BRANCH_CREATED_AT_LOAD]) == expected

    async def test_branch_does_not_count_a_schema_change_of_main_applied_after_its_creation(
        self, db: InfrahubDatabase, resolver_cases: ResolverCases
    ) -> None:
        resolver = _resolver(db=db, default_branch_name=MAIN_APPLIED_AFTER_BRANCH)

        version = await resolver.resolve_next(branch=resolver_cases.branches[BRANCH_CREATED_BEFORE_LOAD])

        assert [change.version for change in resolver_cases.history.applied_on_branch(MAIN_APPLIED_AFTER_BRANCH)] == [1]
        assert version == SchemaChangeVersion(version=1, parent_id=None)

    async def test_running_and_failed_schema_changes_do_not_change_the_version(
        self, db: InfrahubDatabase, resolver_cases: ResolverCases
    ) -> None:
        resolver = _resolver(db=db, default_branch_name=MAIN_WITH_UNFINISHED_CHANGES)
        expected = SchemaChangeVersion(version=2, parent_id=resolver_cases.applied(MAIN_WITH_UNFINISHED_CHANGES, 1))

        assert await resolver.resolve_next(branch=resolver_cases.branches[MAIN_WITH_UNFINISHED_CHANGES]) == expected
        assert await resolver.resolve_next(branch=resolver_cases.branches[BRANCH_WITH_UNFINISHED_CHANGES]) == expected
