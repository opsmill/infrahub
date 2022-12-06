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


@pytest.mark.asyncio
async def test_initialize_class(session, register_core_models_schema, edge_repo_main_only):

    rfile_schema = await registry.get_schema(session=session, name="RFile")
    repo_schema = await registry.get_schema(session=session, name="Repository")
    query_schema = await registry.get_schema(session=session, name="GraphQLQuery")
    criticality_schema = await registry.get_schema(session=session, name="Criticality")

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

    obj1 = await Node.init(session=session, schema=criticality_schema)
    await obj1.new(session=session, name="low", level=4)
    await obj1.save(session=session)

    obj2 = await Node.init(session=session, schema=criticality_schema)
    await obj2.new(session=session, name="medium", level=3, description="My desc")
    await obj2.save(session=session)

    repo1 = await Repository.init(session=session, schema=repo_schema)
    await repo1.new(session=session, name="infrahub-demo-edge", location="notvalid")
    await repo1.save(session=session)

    gql1 = await Node.init(session=session, schema=query_schema)
    await gql1.new(session=session, name="query1", query=query)
    await gql1.save(session=session)

    rfile1 = await RFile.init(session=session, schema=rfile_schema)
    await rfile1.new(
        session=session, name="rfile1", template_path="mytemplate.j2", template_repository=repo1, query=gql1
    )
    await rfile1.save(session=session)

    assert rfile1.id
    assert await rfile1.get_query(session=session) == query
