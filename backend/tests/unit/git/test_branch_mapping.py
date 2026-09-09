from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.git.branch_mapping import get_mapped_remote_branch


@dataclass
class MappingCase:
    name: str
    branch_name: str
    repository_default_branch: str
    infrahub_default_branch: str
    expected: str


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            MappingCase(
                name="default_branch_reads_the_repository_trunk",
                branch_name="main",
                repository_default_branch="trunk",
                infrahub_default_branch="main",
                expected="trunk",
            ),
            id="default_branch_reads_the_repository_trunk",
        ),
        pytest.param(
            MappingCase(
                name="default_branch_matching_the_repository_trunk_reads_itself",
                branch_name="main",
                repository_default_branch="main",
                infrahub_default_branch="main",
                expected="main",
            ),
            id="default_branch_matching_the_repository_trunk_reads_itself",
        ),
        pytest.param(
            MappingCase(
                name="other_branch_reads_the_same_name",
                branch_name="feature",
                repository_default_branch="trunk",
                infrahub_default_branch="main",
                expected="feature",
            ),
            id="other_branch_reads_the_same_name",
        ),
        pytest.param(
            MappingCase(
                name="other_branch_named_like_the_repository_trunk_reads_itself",
                branch_name="trunk",
                repository_default_branch="trunk",
                infrahub_default_branch="main",
                expected="trunk",
            ),
            id="other_branch_named_like_the_repository_trunk_reads_itself",
        ),
    ],
)
def test_get_mapped_remote_branch(case: MappingCase) -> None:
    assert (
        get_mapped_remote_branch(
            branch_name=case.branch_name,
            repository_default_branch=case.repository_default_branch,
            infrahub_default_branch=case.infrahub_default_branch,
        )
        == case.expected
    )
