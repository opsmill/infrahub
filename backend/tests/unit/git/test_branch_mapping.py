from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.git.branch_mapping import get_mapped_remote_branch, remote_branch_is_imported


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


@dataclass
class ImportedCase:
    name: str
    remote_branch_name: str
    branch_is_synced_with_git: bool
    import_sync_branch_names: list[str]
    expected: bool


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            ImportedCase(
                name="no_filters_import_every_branch",
                remote_branch_name="feature",
                branch_is_synced_with_git=False,
                import_sync_branch_names=[],
                expected=True,
            ),
            id="no_filters_import_every_branch",
        ),
        pytest.param(
            ImportedCase(
                name="filters_skip_an_unsynced_branch_they_do_not_match",
                remote_branch_name="feature",
                branch_is_synced_with_git=False,
                import_sync_branch_names=["release-.*"],
                expected=False,
            ),
            id="filters_skip_an_unsynced_branch_they_do_not_match",
        ),
        pytest.param(
            ImportedCase(
                name="filters_keep_a_synced_branch_they_do_not_match",
                remote_branch_name="feature",
                branch_is_synced_with_git=True,
                import_sync_branch_names=["release-.*"],
                expected=True,
            ),
            id="filters_keep_a_synced_branch_they_do_not_match",
        ),
        pytest.param(
            ImportedCase(
                name="a_matching_filter_keeps_an_unsynced_branch",
                remote_branch_name="release-1",
                branch_is_synced_with_git=False,
                import_sync_branch_names=["release-.*"],
                expected=True,
            ),
            id="a_matching_filter_keeps_an_unsynced_branch",
        ),
        pytest.param(
            ImportedCase(
                name="a_literal_filter_keeps_an_unsynced_branch",
                remote_branch_name="feature",
                branch_is_synced_with_git=False,
                import_sync_branch_names=["feature"],
                expected=True,
            ),
            id="a_literal_filter_keeps_an_unsynced_branch",
        ),
        pytest.param(
            ImportedCase(
                name="filters_never_skip_the_repository_trunk",
                remote_branch_name="trunk",
                branch_is_synced_with_git=False,
                import_sync_branch_names=["release-.*"],
                expected=True,
            ),
            id="filters_never_skip_the_repository_trunk",
        ),
        pytest.param(
            ImportedCase(
                name="filters_never_skip_the_infrahub_default_branch",
                remote_branch_name="main",
                branch_is_synced_with_git=False,
                import_sync_branch_names=["release-.*"],
                expected=True,
            ),
            id="filters_never_skip_the_infrahub_default_branch",
        ),
    ],
)
def test_remote_branch_is_imported(case: ImportedCase) -> None:
    assert (
        remote_branch_is_imported(
            remote_branch_name=case.remote_branch_name,
            branch_is_synced_with_git=case.branch_is_synced_with_git,
            repository_default_branch="trunk",
            infrahub_default_branch="main",
            import_sync_branch_names=case.import_sync_branch_names,
        )
        is case.expected
    )
