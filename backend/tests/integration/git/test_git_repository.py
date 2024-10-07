import os
from pathlib import Path

import pytest
import yaml
from infrahub_sdk import Config, InfrahubClient, NodeNotFoundError

from infrahub import config
from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import first_time_initialization, initialization
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.utils import count_relationships, delete_all_nodes
from infrahub.database import InfrahubDatabase
from infrahub.git import InfrahubRepository
from infrahub.server import app, app_initialization
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.utils import get_models_dir
from tests.adapters.log import FakeTaskReportLogger
from tests.helpers.file_repo import FileRepo
from tests.helpers.test_client import InfrahubTestClient

# pylint: disable=unused-argument


async def load_infrastructure_schema(db: InfrahubDatabase):
    base_dir = get_models_dir() / "base"

    default_branch_name = registry.default_branch
    branch_schema = registry.schema.get_schema_branch(name=default_branch_name)
    tmp_schema = branch_schema.duplicate()

    for file_name in os.listdir(base_dir):
        file_path = os.path.join(base_dir, file_name)

        if file_path.endswith((".yml", ".yaml")):
            schema_txt = Path(file_path).read_text(encoding="utf-8")
            loaded_schema = yaml.safe_load(schema_txt)
            tmp_schema.load_schema(schema=SchemaRoot(**loaded_schema))
    tmp_schema.process()

    await registry.schema.update_schema_branch(schema=tmp_schema, db=db, branch=default_branch_name, update_db=True)


class TestInfrahubClient:
    @pytest.fixture(scope="class")
    def workflow_local(prefect_test_fixture):
        original = config.OVERRIDE.workflow
        workflow = WorkflowLocalExecution()
        config.OVERRIDE.workflow = workflow
        yield workflow
        config.OVERRIDE.workflow = original

    @pytest.fixture(scope="class")
    async def base_dataset(self, db: InfrahubDatabase, redis, nats):
        await delete_all_nodes(db=db)
        await first_time_initialization(db=db)
        await load_infrastructure_schema(db=db)
        await initialization(db=db)

    @pytest.fixture(scope="class")
    async def test_client(
        self,
        base_dataset,
        workflow_local,
    ) -> InfrahubTestClient:
        await app_initialization(app)
        return InfrahubTestClient(app=app)

    @pytest.fixture
    async def client(self, test_client: InfrahubTestClient, integration_helper):
        admin_token = await integration_helper.create_token()
        config = Config(api_token=admin_token, requester=test_client.async_request)

        return InfrahubClient(config=config)

    @pytest.fixture(scope="class")
    async def query_99(self, db: InfrahubDatabase, test_client):
        obj = await Node.init(schema=InfrahubKind.GRAPHQLQUERY, db=db)
        await obj.new(
            db=db,
            name="query99",
            query="query query99 { CoreRepository { edges { node { id }}}}",
        )
        await obj.save(db=db)
        return obj

    @pytest.fixture
    async def repo(
        self, test_client, client, db: InfrahubDatabase, git_repo_infrahub_demo_edge: FileRepo, git_repos_dir
    ):
        # Create the repository in the Graph
        obj = await Node.init(schema=InfrahubKind.REPOSITORY, db=db)
        await obj.new(
            db=db,
            name=git_repo_infrahub_demo_edge.name,
            description="test repository",
            location="git@github.com:mock/test.git",
        )
        await obj.save(db=db)

        # Initialize the repository on the file system
        repo = await InfrahubRepository.new(
            id=obj.id,
            name=git_repo_infrahub_demo_edge.name,
            location=git_repo_infrahub_demo_edge.path,
            task_report=FakeTaskReportLogger(),
            client=client,
        )

        return repo

    async def test_import_schema_files(self, db: InfrahubDatabase, client: InfrahubClient, repo: InfrahubRepository):
        commit = repo.get_commit_value(branch_name="main")
        config_file = await repo.get_repository_config(branch_name="main", commit=commit)
        assert config_file
        await repo.import_schema_files(branch_name="main", commit=commit, config_file=config_file)

        assert await client.schema.get(kind="DemoEdgeFabric", refresh=True)

    async def test_import_schema_files_from_directory(
        self, db: InfrahubDatabase, client: InfrahubClient, repo: InfrahubRepository
    ):
        commit = repo.get_commit_value(branch_name="main")
        config_file = await repo.get_repository_config(branch_name="main", commit=commit)
        assert config_file

        config_file.schemas = [Path("schemas")]
        await repo.import_schema_files(branch_name="main", commit=commit, config_file=config_file)

        assert await client.schema.get(kind="DemoEdgeFabric", refresh=True)

    async def test_import_all_graphql_query(
        self, db: InfrahubDatabase, client: InfrahubClient, repo: InfrahubRepository
    ):
        commit = repo.get_commit_value(branch_name="main")
        config_file = await repo.get_repository_config(branch_name="main", commit=commit)
        assert config_file

        await repo.import_all_graphql_query(branch_name="main", commit=commit, config_file=config_file)

        queries = await client.all(kind=InfrahubKind.GRAPHQLQUERY)
        assert len(queries) == 5

        # Validate if the function is idempotent, another import just after the first one shouldn't change anything
        nbr_relationships_before = await count_relationships(db=db)
        await repo.import_all_graphql_query(branch_name="main", commit=commit, config_file=config_file)
        assert await count_relationships(db=db) == nbr_relationships_before

        # 1. Modify an object to validate if its being properly updated
        # 2. Add an object that doesn't exist in GIt and validate that it's been deleted
        value_before_change = queries[0].query.value
        queries[0].query.value = "query myquery { LocationSite { edges { node { id }}}}"
        await queries[0].save()

        obj = await Node.init(schema=InfrahubKind.GRAPHQLQUERY, db=db)
        await obj.new(
            db=db,
            name="soontobedeletedquery",
            query="query soontobedeletedquery { LocationSite { edges { node { id }}}}",
            repository=str(repo.id),
        )
        await obj.save(db=db)

        await repo.import_all_graphql_query(branch_name="main", commit=commit, config_file=config_file)

        modified_query = await client.get(kind=InfrahubKind.GRAPHQLQUERY, id=queries[0].id)
        assert modified_query.query.value == value_before_change

        with pytest.raises(NodeNotFoundError):
            await client.get(kind=InfrahubKind.GRAPHQLQUERY, id=obj.id)

    async def test_import_all_python_files(
        self, db: InfrahubDatabase, client: InfrahubClient, repo: InfrahubRepository, query_99
    ):
        commit = repo.get_commit_value(branch_name="main")
        config_file = await repo.get_repository_config(branch_name="main", commit=commit)
        assert config_file

        await repo.import_all_python_files(branch_name="main", commit=commit, config_file=config_file)

        check_definitions = await client.all(kind=InfrahubKind.CHECKDEFINITION)
        assert len(check_definitions) >= 1

        transforms = await client.all(kind="CoreTransformPython")
        assert len(transforms) >= 2

        # Validate if the function is idempotent, another import just after the first one shouldn't change anything
        nbr_relationships_before = await count_relationships(db=db)
        await repo.import_all_python_files(branch_name="main", commit=commit, config_file=config_file)
        assert await count_relationships(db=db) == nbr_relationships_before

        # 1. Modify an object to validate if its being properly updated
        # 2. Add an object that doesn't exist in Git and validate that it's been deleted
        check_timeout_value_before_change = check_definitions[0].timeout.value
        check_query_value_before_change = check_definitions[0].query.id
        check_definitions[0].timeout.value = 44
        check_definitions[0].query = query_99.id
        await check_definitions[0].save()

        transform_timeout_value_before_change = transforms[0].timeout.value
        transforms[0].timeout.value = 44
        await transforms[0].save()

        transform_query_value_before_change = transforms[1].query.id
        transforms[1].query = query_99.id
        await transforms[1].save()

        # Create Object that will be deleted
        obj1 = await Node.init(schema=InfrahubKind.CHECKDEFINITION, db=db)
        await obj1.new(
            db=db,
            name="soontobedeletedcheck",
            query=str(query_99.id),
            file_path="check.py",
            class_name="MyCheck",
            repository=str(repo.id),
        )
        await obj1.save(db=db)

        obj2 = await Node.init(schema="CoreTransformPython", db=db)
        await obj2.new(
            db=db,
            name="soontobedeletedtransform",
            query=str(query_99.id),
            file_path="mytransform.py",
            class_name="MyTransform",
            repository=str(repo.id),
        )
        await obj2.save(db=db)

        await repo.import_all_python_files(branch_name="main", commit=commit, config_file=config_file)

        modified_check0 = await client.get(kind=InfrahubKind.CHECKDEFINITION, id=check_definitions[0].id)
        assert modified_check0.timeout.value == check_timeout_value_before_change
        assert modified_check0.query.id == check_query_value_before_change

        modified_transform0 = await client.get(kind="CoreTransformPython", id=transforms[0].id)
        modified_transform1 = await client.get(kind="CoreTransformPython", id=transforms[1].id)

        assert modified_transform0.timeout.value == transform_timeout_value_before_change
        assert modified_transform1.query.id == transform_query_value_before_change

        # FIXME not implemented yet
        with pytest.raises(NodeNotFoundError):
            await client.get(kind=InfrahubKind.CHECKDEFINITION, id=obj1.id)

        with pytest.raises(NodeNotFoundError):
            await client.get(kind="CoreTransformPython", id=obj2.id)

    async def test_import_all_yaml_files(
        self, db: InfrahubDatabase, client: InfrahubClient, repo: InfrahubRepository, query_99
    ):
        commit = repo.get_commit_value(branch_name="main")
        config_file = await repo.get_repository_config(branch_name="main", commit=commit)
        assert config_file
        await repo.import_jinja2_transforms(branch_name="main", commit=commit, config_file=config_file)

        rfiles = await client.all(kind=InfrahubKind.TRANSFORMJINJA2)
        assert len(rfiles) == 2

        # Validate if the function is idempotent, another import just after the first one shouldn't change anything
        nbr_relationships_before = await count_relationships(db=db)
        await repo.import_jinja2_transforms(branch_name="main", commit=commit, config_file=config_file)
        assert await count_relationships(db=db) == nbr_relationships_before

        # 1. Modify an object to validate if its being properly updated
        # 2. Add an object that doesn't exist in Git and validate that it's been deleted
        rfile_template_path_value_before_change = rfiles[0].template_path.value
        rfile_query_value_before_change = rfiles[0].query.id
        rfiles[0].template_path.value = "my_path"
        rfiles[0].query = query_99.id
        await rfiles[0].save()

        obj = await Node.init(schema=InfrahubKind.TRANSFORMJINJA2, db=db)
        await obj.new(
            db=db,
            name="soontobedeletedrfile",
            query=str(query_99.id),
            repository=str(repo.id),
            template_path="mytmp.j2",
        )
        await obj.save(db=db)

        await repo.import_jinja2_transforms(branch_name="main", commit=commit, config_file=config_file)

        modified_rfile = await client.get(kind=InfrahubKind.TRANSFORMJINJA2, id=rfiles[0].id)
        assert modified_rfile.template_path.value == rfile_template_path_value_before_change
        assert modified_rfile.query.id == rfile_query_value_before_change

        # FIXME not implemented yet
        with pytest.raises(NodeNotFoundError):
            await client.get(kind=InfrahubKind.TRANSFORMJINJA2, id=obj.id)
