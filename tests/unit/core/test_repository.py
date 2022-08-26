import os
import tarfile

import pytest

import infrahub.config as config
from infrahub.core import registry
from infrahub.core.repository import Repository, initialize_repositories_directory


@pytest.fixture
def edge_repo_main_only(tmp_path):

    repositories_dir = tmp_path / "repositories"
    repositories_dir.mkdir()
    config.SETTINGS.main.repositories_directory = str(repositories_dir)

    root_dir = os.getcwd()
    fixtures_dir = f"{root_dir}/tests/fixtures"
    fixture_file_path = f"{fixtures_dir}/repo-main-branch-only.tar.gz"

    fixture_file = tarfile.open(fixture_file_path)
    fixture_file.extractall(str(repositories_dir))

    return repositories_dir / "infrahub-demo-edge"


def test_initialize_repositories_directory_missing(tmp_path):

    repositories_dir = tmp_path / "repositories"
    config.SETTINGS.main.repositories_directory = str(repositories_dir)

    created = initialize_repositories_directory()

    assert created is True
    assert len(list(tmp_path.iterdir())) == 1


def test_initialize_repositories_directory_present(tmp_path):

    repositories_dir = tmp_path / "repositories"
    repositories_dir.mkdir()

    config.SETTINGS.main.repositories_directory = str(repositories_dir)

    created = initialize_repositories_directory()

    assert created is False
    assert len(list(tmp_path.iterdir())) == 1


def test_ensure_exists_locally_when_present(register_core_models_schema, edge_repo_main_only):

    repo_schema = registry.get_schema("Repository")
    obj = Repository(repo_schema).new(name="infrahub-demo-edge", location="notvalid")

    assert obj.ensure_exists_locally() is False
    assert obj.commit.value == "dd60ae4804c0d0e71c8de0640bb84b095fc3ee61"


def test_add_branch(register_core_models_schema, edge_repo_main_only):

    repo_schema = registry.get_schema("Repository")
    obj = Repository(repo_schema).new(name="infrahub-demo-edge", location="notvalid")
    obj.add_branch("newbranch", push_origin=False)

    assert os.path.isdir(str(edge_repo_main_only / "newbranch"))
