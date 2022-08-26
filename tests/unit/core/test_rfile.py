import os
import tarfile

import pytest

import infrahub.config as config
from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.core.repository import Repository
from infrahub.core.rfile import RFile


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


def test_initialize_class(register_core_models_schema, edge_repo_main_only):

    rfile_schema = registry.get_schema("RFile")
    repo_schema = registry.get_schema("Repository")
    query_schema = registry.get_schema("GraphQLQuery")
    criticality_schema = registry.get_schema("Criticality")

    registry.node["RFile"] = RFile

    query = """
    query {
        criticality {
            name {
                value
            }
        }
    }
    """

    obj1 = Node(criticality_schema).new(name="low", level=4)
    obj1.save()

    obj2 = Node(criticality_schema).new(name="medium", level=3, description="My desc")
    obj2.save()

    repo1 = Repository(repo_schema).new(name="infrahub-demo-edge", location="notvalid").save()
    gql1 = Node(query_schema).new(name="query1", query=query).save()

    rfile1 = (
        RFile(rfile_schema)
        .new(name="rfile1", template_path="mytemplate.j2", template_repository=repo1, query=gql1)
        .save()
    )

    assert rfile1.id
    assert rfile1.get_query() == query
