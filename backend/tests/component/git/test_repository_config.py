"""Tests for repository configuration file loading and error handling."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from git import Repo as GitRepo  # type: ignore[attr-defined]
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.uuidt import UUIDT

from infrahub.exceptions import RepositoryConfigurationError
from infrahub.git import InfrahubRepository
from tests.helpers.test_client import dummy_async_request

if TYPE_CHECKING:
    from pathlib import Path


class TestGetRepositoryConfig:
    """Tests for the get_repository_config method."""

    @pytest.fixture
    async def repo_without_config(
        self, git_upstream_repo_01: dict[str, str | Path], git_repos_dir: Path
    ) -> InfrahubRepository:
        """Create a repository without a .infrahub.yml config file.

        The test fixture repository doesn't have a config file by default.

        Args:
            git_upstream_repo_01: Upstream repo metadata containing name and path.
            git_repos_dir: Temporary directory for test repositories.

        Returns:
            The initialized Infrahub repository instance without a config file.
        """
        repo = await InfrahubRepository.new(
            id=UUIDT.new(),
            name=git_upstream_repo_01["name"],
            location=str(git_upstream_repo_01["path"]),
            client=InfrahubClient(config=Config(requester=dummy_async_request)),
        )
        return repo

    @pytest.fixture
    async def repo_with_invalid_yaml(
        self, git_upstream_repo_01: dict[str, str | Path], git_repos_dir: Path
    ) -> InfrahubRepository:
        """Create a repository with an invalid YAML config file.

        Args:
            git_upstream_repo_01: Upstream repo metadata containing name and path.
            git_repos_dir: Temporary directory for test repositories.

        Returns:
            The initialized Infrahub repository instance with an invalid YAML config.
        """
        from pathlib import Path as PathlibPath

        # Clone the upstream repo to avoid polluting the shared fixture
        original_path = PathlibPath(git_upstream_repo_01["path"])
        clone_path = git_repos_dir / f"clone_invalid_yaml_{id(self)}"
        cloned_repo = GitRepo.clone_from(str(original_path), str(clone_path))

        config_file = clone_path / ".infrahub.yml"

        # Write invalid YAML content
        invalid_yaml = """
schemas:
  - path: invalid
  this is: [not valid yaml
    missing: closing bracket
"""
        config_file.write_text(invalid_yaml, encoding="utf-8")
        cloned_repo.index.add([".infrahub.yml"])
        cloned_repo.index.commit("Add invalid YAML config file")

        repo = await InfrahubRepository.new(
            id=UUIDT.new(),
            name=git_upstream_repo_01["name"],
            location=str(clone_path),
            client=InfrahubClient(config=Config(requester=dummy_async_request)),
        )
        return repo

    @pytest.fixture
    async def repo_with_invalid_format(
        self, git_upstream_repo_01: dict[str, str | Path], git_repos_dir: Path
    ) -> InfrahubRepository:
        """Create a repository with a YAML config file that has invalid format.

        Args:
            git_upstream_repo_01: Upstream repo metadata containing name and path.
            git_repos_dir: Temporary directory for test repositories.

        Returns:
            The initialized Infrahub repository instance with an invalid format config.
        """
        from pathlib import Path as PathlibPath

        # Clone the upstream repo to avoid polluting the shared fixture
        original_path = PathlibPath(git_upstream_repo_01["path"])
        clone_path = git_repos_dir / f"clone_invalid_format_{id(self)}"
        cloned_repo = GitRepo.clone_from(str(original_path), str(clone_path))

        config_file = clone_path / ".infrahub.yml"

        # Write valid YAML but invalid InfrahubRepositoryConfig format
        invalid_format = """
invalid_key: "this key doesn't exist in the schema"
schemas: "should be a list, not a string"
"""
        config_file.write_text(invalid_format, encoding="utf-8")
        cloned_repo.index.add([".infrahub.yml"])
        cloned_repo.index.commit("Add invalid format config file")

        repo = await InfrahubRepository.new(
            id=UUIDT.new(),
            name=git_upstream_repo_01["name"],
            location=str(clone_path),
            client=InfrahubClient(config=Config(requester=dummy_async_request)),
        )
        return repo

    @pytest.fixture
    async def repo_with_valid_config(
        self, git_upstream_repo_01: dict[str, str | Path], git_repos_dir: Path
    ) -> InfrahubRepository:
        """Create a repository with a valid .infrahub.yml config file.

        Args:
            git_upstream_repo_01: Upstream repo metadata containing name and path.
            git_repos_dir: Temporary directory for test repositories.

        Returns:
            The initialized Infrahub repository instance with a valid config file.
        """
        from pathlib import Path as PathlibPath

        # Clone the upstream repo to avoid polluting the shared fixture
        original_path = PathlibPath(git_upstream_repo_01["path"])
        clone_path = git_repos_dir / f"clone_valid_config_{id(self)}"
        cloned_repo = GitRepo.clone_from(str(original_path), str(clone_path))

        config_file = clone_path / ".infrahub.yml"

        # Write a valid minimal config file
        valid_config = """
# Infrahub Repository Configuration
schemas: []
"""
        config_file.write_text(valid_config, encoding="utf-8")
        cloned_repo.index.add([".infrahub.yml"])
        cloned_repo.index.commit("Add valid .infrahub.yml config file")

        repo = await InfrahubRepository.new(
            id=UUIDT.new(),
            name=git_upstream_repo_01["name"],
            location=str(clone_path),
            client=InfrahubClient(config=Config(requester=dummy_async_request)),
        )
        return repo

    async def test_missing_config_file_raises_error(
        self, repo_without_config: InfrahubRepository, prefect_test_fixture
    ) -> None:
        """Test that a missing config file raises RepositoryConfigurationError."""
        commit = repo_without_config.get_commit_value(branch_name="main")
        repo_without_config.create_commit_worktree(commit)

        with pytest.raises(RepositoryConfigurationError) as exc_info:
            await repo_without_config.get_repository_config(branch_name="main", commit=commit)

        assert repo_without_config.name in str(exc_info.value)
        assert "missing a configuration file" in str(exc_info.value)
        assert ".infrahub.yml" in str(exc_info.value) or ".infrahub.yaml" in str(exc_info.value)
        assert "docs.infrahub.app" in str(exc_info.value)

    async def test_invalid_yaml_raises_error(
        self, repo_with_invalid_yaml: InfrahubRepository, prefect_test_fixture
    ) -> None:
        """Test that an invalid YAML config file raises RepositoryConfigurationError."""
        commit = repo_with_invalid_yaml.get_commit_value(branch_name="main")
        repo_with_invalid_yaml.create_commit_worktree(commit)

        with pytest.raises(RepositoryConfigurationError) as exc_info:
            await repo_with_invalid_yaml.get_repository_config(branch_name="main", commit=commit)

        assert repo_with_invalid_yaml.name in str(exc_info.value)
        assert "could not be parsed as valid YAML" in str(exc_info.value)

    async def test_invalid_format_raises_error(
        self, repo_with_invalid_format: InfrahubRepository, prefect_test_fixture
    ) -> None:
        """Test that a config file with invalid format raises RepositoryConfigurationError."""
        commit = repo_with_invalid_format.get_commit_value(branch_name="main")
        repo_with_invalid_format.create_commit_worktree(commit)

        with pytest.raises(RepositoryConfigurationError) as exc_info:
            await repo_with_invalid_format.get_repository_config(branch_name="main", commit=commit)

        assert repo_with_invalid_format.name in str(exc_info.value)
        assert "format is not valid" in str(exc_info.value)

    async def test_valid_config_file_returns_config(
        self, repo_with_valid_config: InfrahubRepository, prefect_test_fixture
    ) -> None:
        """Test that a valid config file is successfully loaded."""
        commit = repo_with_valid_config.get_commit_value(branch_name="main")
        repo_with_valid_config.create_commit_worktree(commit)

        config = await repo_with_valid_config.get_repository_config(branch_name="main", commit=commit)

        assert config is not None


class TestRepositoryConfigurationErrorException:
    """Tests for the RepositoryConfigurationError exception class."""

    def test_default_message(self) -> None:
        """Test that the default message is correctly set."""
        error = RepositoryConfigurationError(identifier="test-repo")

        assert "Repository configuration file error" in str(error)
        assert error.identifier == "test-repo"

    def test_custom_message(self) -> None:
        """Test that a custom message is correctly set."""
        custom_message = "Custom error message for test-repo"
        error = RepositoryConfigurationError(identifier="test-repo", message=custom_message)

        assert str(error) == custom_message
        assert error.message == custom_message
        assert error.identifier == "test-repo"

    def test_inherits_from_repository_error(self) -> None:
        """Test that RepositoryConfigurationError inherits from RepositoryError."""
        from infrahub.exceptions import RepositoryError

        error = RepositoryConfigurationError(identifier="test-repo")

        assert isinstance(error, RepositoryError)
