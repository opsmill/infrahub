
import os
import tarfile

import asyncio
import pytest
import pytest_asyncio

import infrahub.config as config


@pytest.fixture
def git_sources_dir(tmpdir):

    source_dir = os.path.join(str(tmpdir), "sources")

    os.mkdir(source_dir)

    return source_dir

@pytest.fixture
def git_repos_dir(tmpdir):

    repos_dir = os.path.join(str(tmpdir), "repositories")

    os.mkdir(repos_dir)

    config.SETTINGS.main.repositories_directory = repos_dir

    return repos_dir

@pytest.fixture
def git_upstream_repo_01(git_sources_dir):

    fixtures_dir = os.path.join(os.getcwd(), "tests/fixtures")
    fixture_repo = os.path.join(fixtures_dir, "infrahub-test-fixture-01-0b341c0.tar.gz" )

    # Extract the fixture package in the source directory
    file = tarfile.open(fixture_repo)
    file.extractall(git_sources_dir)
    file.close()

    return os.path.join(git_sources_dir, "infrahub-test-fixture-01")
