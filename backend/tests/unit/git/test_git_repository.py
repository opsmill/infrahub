from pathlib import Path

from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.uuidt import UUIDT

from infrahub import config
from infrahub.core.registry import registry
from infrahub.git import InfrahubRepository
from tests.helpers.file_repo import MultipleStagesFileRepo
from tests.helpers.test_client import dummy_async_request


async def test_has_conflicting_changes_no_false_positive(
    tmp_path: Path,
) -> None:
    """has_conflicting_changes() should not report false positives when
    file content contains conflict marker characters like '======='."""
    old_default_branch = getattr(registry, "_default_branch", None)
    old_repos_dir = config.SETTINGS.git.repositories_directory

    try:
        registry._default_branch = "main"

        repos_dir = tmp_path / "repositories"
        repos_dir.mkdir()
        config.SETTINGS.git.repositories_directory = str(repos_dir)

        sources_dir = tmp_path / "source"
        sources_dir.mkdir()

        test_repo = MultipleStagesFileRepo(name="false-positive-conflicts", sources_directory=sources_dir)
        repository = await InfrahubRepository.new(
            id=UUIDT.new(),
            name=test_repo.name,
            location=test_repo.path,
            default_branch_name="main",
            client=InfrahubClient(config=Config(requester=dummy_async_request)),
        )

        # The branch adds a file containing ======= but has no actual conflicts with main
        assert not repository.has_conflicting_changes(target_branch="main", source_branch="change1")
    finally:
        config.SETTINGS.git.repositories_directory = old_repos_dir
        if old_default_branch is not None:
            registry._default_branch = old_default_branch
