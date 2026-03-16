"""Component tests for GraphQL fragment inlining during repository import.

Tests verify that `import_all_graphql_query()` resolves fragment spreads correctly
and passes the rendered query strings to `create_graphql_query()`. The SDK's database
calls are stubbed so no live server is required.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from git import Repo as GitRepo
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.exceptions import FragmentFileNotFoundError, FragmentNotFoundError
from infrahub_sdk.schema.repository import InfrahubRepositoryFragmentConfig, InfrahubRepositoryGraphQLConfig
from infrahub_sdk.uuidt import UUIDT

from infrahub.git import InfrahubRepository
from infrahub.git.integrator import InfrahubRepositoryIntegrator
from tests.constants import FIXTURE_REPOS_DIR
from tests.helpers.test_client import dummy_async_request

FRAGMENT_INLINING_FIXTURE = FIXTURE_REPOS_DIR / "fragment-inlining"


def _create_upstream_repo(tmp_path: Path) -> Path:
    """Create a git repo with the fragment_inlining fixture files."""
    repo_path = tmp_path / "fragment_repo"
    shutil.copytree(FRAGMENT_INLINING_FIXTURE, repo_path)
    git_repo = GitRepo.init(str(repo_path), initial_branch="main")
    git_repo.config_writer().set_value("user", "name", "test").release()
    git_repo.config_writer().set_value("user", "email", "test@test.com").release()
    git_repo.git.add(A=True)
    git_repo.index.commit("Initial commit with fragment files")
    return repo_path


def _stub_sdk_client(repo: InfrahubRepository) -> None:
    """Replace the repo's SDK client with a full AsyncMock.

    Every method on the client is a mock, so no live server is required.
    filters() returning [] means all queries are treated as new (only_local path),
    but the create/update/delete reconciliation logic is not exercised here —
    these tests focus solely on fragment rendering.
    """
    mock_client = AsyncMock()
    mock_client.filters = AsyncMock(return_value=[])
    repo.client = mock_client


async def _import_queries(
    repo: InfrahubRepository, branch_name: str = "main", commit: str | None = None
) -> dict[str, str]:
    """Run import_all_graphql_query and return the rendered strings keyed by query name.

    Patches create_graphql_query on the class to capture what was rendered without
    hitting the database. sdk.filters is already stubbed via the mock client on the repo.
    """
    if commit is None:
        commit = repo.get_commit_value(branch_name=branch_name)
    config_file = await repo.get_repository_config(branch_name=branch_name, commit=commit)

    rendered: dict[str, str] = {}

    async def _capture(branch_name: str, name: str, query_string: str) -> None:
        rendered[name] = query_string

    with patch.object(InfrahubRepositoryIntegrator, "create_graphql_query", side_effect=_capture):
        await repo.import_all_graphql_query(branch_name=branch_name, commit=commit, config_file=config_file)

    return rendered


@pytest.fixture
async def fragment_repo(
    git_sources_dir: Path, git_repos_dir: Path, tmp_path: Path, prefect_test_fixture: None
) -> InfrahubRepository:
    """InfrahubRepository cloned from a local upstream with fragment files.

    The SDK client is replaced with a mock so that sdk.filters() returns an
    empty list (simulating a fresh graph with no existing queries).
    """
    upstream_path = _create_upstream_repo(tmp_path)
    repo = await InfrahubRepository.new(
        id=UUIDT.new(),
        name="fragment_repo",
        location=str(upstream_path),
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )
    _stub_sdk_client(repo)
    return repo


async def test_two_fragment_files_stored_query_contains_both_definitions(
    fragment_repo: InfrahubRepository,
) -> None:
    """A query using fragments from two separate files must have both fragment definitions inlined."""
    queries = await _import_queries(fragment_repo)

    assert "fragment interfaceFragment" in queries["query_two_files"]
    assert "fragment deviceFragment" in queries["query_two_files"]


async def test_no_spreads_query_stored_unchanged(
    fragment_repo: InfrahubRepository,
) -> None:
    """A query with no fragment spreads must be stored without modification."""
    queries = await _import_queries(fragment_repo)

    assert "fragment " not in queries["query_no_fragments"]
    assert "QueryNoFragments" in queries["query_no_fragments"]


async def test_transitive_dependency_included(
    fragment_repo: InfrahubRepository,
) -> None:
    """query_transitive only spreads ...deviceFragment; interfaceFragment must also appear because the inliner walks fragment bodies recursively."""
    queries = await _import_queries(fragment_repo)

    assert "fragment deviceFragment" in queries["query_transitive"]
    assert "fragment interfaceFragment" in queries["query_transitive"]


async def test_surplus_fragment_excluded(
    fragment_repo: InfrahubRepository,
) -> None:
    """Fragments not reachable from a query's spread chain must not appear in its stored string."""
    queries = await _import_queries(fragment_repo)

    assert "fragment " not in queries["query_no_fragments"]
    assert "fragment portFragment" not in queries["query_transitive"]
    assert "fragment chassisFragment" not in queries["query_transitive"]


async def test_unresolved_fragment_raises(
    fragment_repo: InfrahubRepository,
) -> None:
    """A query that spreads an undeclared fragment must raise FragmentNotFoundError during import."""
    commit = fragment_repo.get_commit_value(branch_name="main")
    config_file = await fragment_repo.get_repository_config(branch_name="main", commit=commit)
    config_file.queries.append(
        InfrahubRepositoryGraphQLConfig(
            name="query_missing_fragment", file_path=Path("queries/query_missing_fragment.gql")
        )
    )

    with pytest.raises(FragmentNotFoundError):
        await fragment_repo.import_all_graphql_query(branch_name="main", commit=commit, config_file=config_file)


async def test_missing_fragment_file_raises_with_path(
    fragment_repo: InfrahubRepository,
) -> None:
    """A declared fragment file that doesn't exist on disk must raise FragmentFileNotFoundError with the missing path."""
    commit = fragment_repo.get_commit_value(branch_name="main")
    config_file = await fragment_repo.get_repository_config(branch_name="main", commit=commit)
    config_file.graphql_fragments = [
        InfrahubRepositoryFragmentConfig(name="missing_file", file_path=Path("fragments/does_not_exist.gql"))
    ]

    with pytest.raises(FragmentFileNotFoundError) as exc_info:
        await fragment_repo.import_all_graphql_query(branch_name="main", commit=commit, config_file=config_file)

    assert "does_not_exist.gql" in exc_info.value.file_path


async def test_resync_after_fragment_update_reflects_new_definition(
    git_sources_dir: Path, git_repos_dir: Path, tmp_path: Path, prefect_test_fixture: None
) -> None:
    """After a fragment file is updated in the upstream repo and re-synced, stored queries
    reflect the new field selection from the updated fragment.
    """
    upstream_path = _create_upstream_repo(tmp_path)
    repo = await InfrahubRepository.new(
        id=UUIDT.new(),
        name="resync_repo",
        location=str(upstream_path),
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )
    _stub_sdk_client(repo)

    queries_v1 = await _import_queries(repo)
    assert "fragment interfaceFragment" in queries_v1["query_transitive"]
    assert "newFieldAddedInV2" not in queries_v1["query_transitive"]

    # Update the fragment file in the upstream repo
    upstream_git = GitRepo(str(upstream_path))
    (upstream_path / "fragments" / "interfaces.gql").write_text(
        """fragment interfaceFragment on InterfaceL3 {
  id
  name { value }
  newFieldAddedInV2 { value }
}

fragment portFragment on InterfaceL2 {
  id
  enabled { value }
}
""",
        encoding="utf-8",
    )
    upstream_git.index.add(["fragments/interfaces.gql"])
    upstream_git.index.commit("Update interfaceFragment to add newFieldAddedInV2")

    await repo.fetch()
    commit2 = repo.get_commit_value(branch_name="main", remote=True)
    repo.create_commit_worktree(commit2)

    queries_v2 = await _import_queries(repo, commit=commit2)
    assert "newFieldAddedInV2" in queries_v2["query_transitive"]


async def test_fragment_isolation_between_repositories(
    git_sources_dir: Path, git_repos_dir: Path, tmp_path: Path, prefect_test_fixture: None
) -> None:
    """Two repos declaring the same fragment name with different field selections
    must each store their query using only their own fragment definition.
    """

    def _make_upstream(root: Path, variant: str) -> Path:
        repo_path = root / f"repo_{variant}"
        repo_path.mkdir()
        git_repo = GitRepo.init(str(repo_path), initial_branch="main")
        git_repo.config_writer().set_value("user", "name", "test").release()
        git_repo.config_writer().set_value("user", "email", "test@test.com").release()

        (repo_path / ".infrahub.yml").write_text(
            """---
graphql_fragments:
  - name: frags
    file_path: frags.gql
queries:
  - name: my_query
    file_path: my_query.gql
""",
            encoding="utf-8",
        )
        (repo_path / "frags.gql").write_text(
            f"fragment deviceFragment on InfraDevice {{ id\n  variant_{variant} {{ value }}\n}}\n",
            encoding="utf-8",
        )
        (repo_path / "my_query.gql").write_text(
            "query Q { InfraDevice { edges { node { ...deviceFragment } } } }", encoding="utf-8"
        )
        git_repo.index.add([".infrahub.yml", "frags.gql", "my_query.gql"])
        git_repo.index.commit("Initial commit")
        return repo_path

    upstream_a = _make_upstream(tmp_path, "a")
    upstream_b = _make_upstream(tmp_path, "b")

    repo_a = await InfrahubRepository.new(
        id=UUIDT.new(),
        name="repo_a",
        location=str(upstream_a),
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )
    repo_b = await InfrahubRepository.new(
        id=UUIDT.new(),
        name="repo_b",
        location=str(upstream_b),
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )
    for repo in (repo_a, repo_b):
        _stub_sdk_client(repo)

    queries_a = await _import_queries(repo_a)
    queries_b = await _import_queries(repo_b)

    assert "variant_a" in queries_a["my_query"]
    assert "variant_b" not in queries_a["my_query"]
    assert "variant_b" in queries_b["my_query"]
    assert "variant_a" not in queries_b["my_query"]
