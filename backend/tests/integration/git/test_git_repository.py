from pathlib import Path
from typing import AsyncGenerator

import pytest
import yaml
from fast_depends import dependency_provider
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.exceptions import NodeNotFoundError
from infrahub_sdk.protocols import CoreCheckDefinition, CoreGraphQLQuery, CoreTransformJinja2, CoreTransformPython

from infrahub import config
from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import first_time_initialization, initialization
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.utils import count_relationships, delete_all_nodes
from infrahub.database import InfrahubDatabase
from infrahub.git import InfrahubRepository
from infrahub.server import app, lifespan
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.utils import get_models_dir
from infrahub.workers.dependencies import build_database
from infrahub.workflows.initialization import setup_task_manager
from tests.helpers.file_repo import FileRepo
from tests.helpers.test_app import TestInfrahubApp
from tests.helpers.test_client import InfrahubTestClient
from tests.integration.conftest import IntegrationHelper


async def load_infrastructure_schema(db: InfrahubDatabase) -> None:
    base_dir = get_models_dir() / "base"

    default_branch_name = registry.default_branch
    branch_schema = registry.schema.get_schema_branch(name=default_branch_name)
    tmp_schema = branch_schema.duplicate()

    for file_name in base_dir.iterdir():
        file_path = base_dir / file_name

        if file_path.suffix in (".yml", ".yaml"):
            schema_txt = file_path.read_text(encoding="utf-8")
            loaded_schema = yaml.safe_load(schema_txt)
            tmp_schema.load_schema(schema=SchemaRoot(**loaded_schema))
    tmp_schema.process()

    await registry.schema.update_schema_branch(schema=tmp_schema, db=db, branch=default_branch_name, update_db=True)


class TestInfrahubClient:
    @pytest.fixture(scope="class")
    async def workflow_local(self, prefect_test_fixture: None) -> AsyncGenerator[WorkflowLocalExecution, None]:
        original = config.OVERRIDE.workflow
        workflow = WorkflowLocalExecution()
        await setup_task_manager()
        config.OVERRIDE.workflow = workflow
        yield workflow
        config.OVERRIDE.workflow = original

    @pytest.fixture(scope="class")
    async def base_dataset(
        self, db: InfrahubDatabase, redis: dict[int, int] | None, nats: dict[int, int] | None
    ) -> None:
        await delete_all_nodes(db=db)
        await first_time_initialization(db=db)
        await load_infrastructure_schema(db=db)
        await initialization(db=db)

    @pytest.fixture(scope="class")
    async def test_client(
        self,
        base_dataset: None,
        workflow_local: WorkflowLocalExecution,
        db_class: InfrahubDatabase,
    ) -> AsyncGenerator[InfrahubTestClient, None]:
        async def _db(singleton: bool = True) -> InfrahubDatabase:
            return db_class

        with dependency_provider.scope(build_database, _db):
            async with lifespan(app):
                yield InfrahubTestClient(app=app)

    @pytest.fixture
    async def client(self, test_client: InfrahubTestClient, integration_helper: IntegrationHelper) -> InfrahubClient:
        admin_token = await integration_helper.create_token()
        config = Config(api_token=admin_token, requester=test_client.async_request)
        return InfrahubClient(config=config)

    @pytest.fixture(scope="class")
    async def query_99(self, db: InfrahubDatabase, test_client: InfrahubTestClient) -> Node:
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
        self,
        test_client: InfrahubTestClient,
        client: InfrahubClient,
        db: InfrahubDatabase,
        git_repo_infrahub_demo_edge_integration: FileRepo,
        git_repos_dir: Path,
    ) -> InfrahubRepository:
        # Create the repository in the Graph
        obj = await Node.init(schema=InfrahubKind.REPOSITORY, db=db)
        await obj.new(
            db=db,
            name=git_repo_infrahub_demo_edge_integration.name,
            description="test repository",
            location="git@github.com:mock/test.git",
        )
        await obj.save(db=db)

        # Initialize the repository on the file system
        repo = await InfrahubRepository.new(
            id=obj.id,
            name=git_repo_infrahub_demo_edge_integration.name,
            location=git_repo_infrahub_demo_edge_integration.path,
            client=client,
        )

        return repo

    async def test_import_schema_files(
        self, db: InfrahubDatabase, client: InfrahubClient, repo: InfrahubRepository
    ) -> None:
        commit = repo.get_commit_value(branch_name="main")
        config_file = await repo.get_repository_config(branch_name="main", commit=commit)  # type: ignore[call-overload]
        assert config_file
        await repo.import_schema_files(branch_name="main", commit=commit, config_file=config_file)  # type: ignore[call-overload]

        assert await client.schema.get(kind="DemoEdgeFabric", refresh=True)

    async def test_import_schema_files_from_directory(
        self, db: InfrahubDatabase, client: InfrahubClient, repo: InfrahubRepository
    ) -> None:
        commit = repo.get_commit_value(branch_name="main")
        config_file = await repo.get_repository_config(branch_name="main", commit=commit)  # type: ignore[call-overload]
        assert config_file

        config_file.schemas = [Path("schemas")]
        await repo.import_schema_files(branch_name="main", commit=commit, config_file=config_file)  # type: ignore[call-overload]

        assert await client.schema.get(kind="DemoEdgeFabric", refresh=True)

    async def test_import_all_graphql_query(
        self, db: InfrahubDatabase, client: InfrahubClient, repo: InfrahubRepository
    ) -> None:
        commit = repo.get_commit_value(branch_name="main")
        config_file = await repo.get_repository_config(branch_name="main", commit=commit)  # type: ignore[call-overload]
        assert config_file

        await repo.import_all_graphql_query(branch_name="main", commit=commit, config_file=config_file)  # type: ignore[call-overload]

        queries = await client.all(kind=CoreGraphQLQuery)
        assert len(queries) == 10

        # Validate if the function is idempotent, another import just after the first one shouldn't change anything
        nbr_relationships_before = await count_relationships(db=db)
        await repo.import_all_graphql_query(branch_name="main", commit=commit, config_file=config_file)  # type: ignore[call-overload]
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

        await repo.import_all_graphql_query(branch_name="main", commit=commit, config_file=config_file)  # type: ignore[call-overload]

        modified_query = await client.get(kind=CoreGraphQLQuery, id=queries[0].id)
        assert modified_query.query.value == value_before_change

        with pytest.raises(NodeNotFoundError):
            await client.get(kind=CoreGraphQLQuery, id=obj.id)

    async def test_import_all_python_files(
        self, db: InfrahubDatabase, client: InfrahubClient, repo: InfrahubRepository, query_99: Node
    ) -> None:
        for group in ["backbone_services", "maintenance_circuits", "provisioning_circuits", "upstream_interfaces"]:
            obj = await Node.init(schema=InfrahubKind.STANDARDGROUP, db=db)
            await obj.new(
                db=db,
                name=group,
            )
            await obj.save(db=db)

        commit = repo.get_commit_value(branch_name="main")
        config_file = await repo.get_repository_config(branch_name="main", commit=commit)  # type: ignore[call-overload]
        assert config_file

        await repo.import_all_python_files(branch_name="main", commit=commit, config_file=config_file)  # type: ignore[call-overload]

        check_definitions = await client.all(kind=CoreCheckDefinition)
        assert len(check_definitions) >= 1

        transforms = await client.all(kind=CoreTransformPython)
        assert len(transforms) >= 2

        # Validate if the function is idempotent, another import just after the first one shouldn't change anything
        nbr_relationships_before = await count_relationships(db=db)
        await repo.import_all_python_files(branch_name="main", commit=commit, config_file=config_file)  # type: ignore[call-overload]
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

        obj2 = await Node.init(schema=InfrahubKind.TRANSFORMPYTHON, db=db)
        await obj2.new(
            db=db,
            name="soontobedeletedtransform",
            query=str(query_99.id),
            file_path="mytransform.py",
            class_name="MyTransform",
            repository=str(repo.id),
        )
        await obj2.save(db=db)

        await repo.import_all_python_files(branch_name="main", commit=commit, config_file=config_file)  # type: ignore[call-overload]

        modified_check0 = await client.get(kind=CoreCheckDefinition, id=check_definitions[0].id)
        assert modified_check0.timeout.value == check_timeout_value_before_change
        assert modified_check0.query.id == check_query_value_before_change

        modified_transform0 = await client.get(kind=CoreTransformPython, id=transforms[0].id)
        modified_transform1 = await client.get(kind=CoreTransformPython, id=transforms[1].id)

        assert modified_transform0.timeout.value == transform_timeout_value_before_change
        assert modified_transform1.query.id == transform_query_value_before_change

        with pytest.raises(NodeNotFoundError):
            await client.get(kind=CoreCheckDefinition, id=obj1.id)

        with pytest.raises(NodeNotFoundError):
            await client.get(kind=CoreTransformPython, id=obj2.id)

    async def test_import_all_yaml_files(
        self, db: InfrahubDatabase, client: InfrahubClient, repo: InfrahubRepository, query_99: Node
    ) -> None:
        commit = repo.get_commit_value(branch_name="main")
        config_file = await repo.get_repository_config(branch_name="main", commit=commit)  # type: ignore[call-overload]
        assert config_file
        await repo.import_jinja2_transforms(branch_name="main", commit=commit, config_file=config_file)  # type: ignore[call-overload]

        rfiles = await client.all(kind=CoreTransformJinja2)
        assert len(rfiles) == 2

        # Validate if the function is idempotent, another import just after the first one shouldn't change anything
        nbr_relationships_before = await count_relationships(db=db)
        await repo.import_jinja2_transforms(branch_name="main", commit=commit, config_file=config_file)  # type: ignore[call-overload]
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

        await repo.import_jinja2_transforms(branch_name="main", commit=commit, config_file=config_file)  # type: ignore[call-overload]

        modified_rfile = await client.get(kind=CoreTransformJinja2, id=rfiles[0].id)
        assert modified_rfile.template_path.value == rfile_template_path_value_before_change
        assert modified_rfile.query.id == rfile_query_value_before_change

        with pytest.raises(NodeNotFoundError):
            await client.get(kind=CoreTransformJinja2, id=obj.id)


class TestGetMissingFile(TestInfrahubApp):
    async def test_get_missing_file(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        git_repo_car_dealership: FileRepo,
        test_client: InfrahubTestClient,
    ) -> None:
        # Ideally above tests would rely on `TestInfrahubApp.repo` instead of TestInfrahubClient
        # and we would reuse `TestInfrahubClient.repo` fixture here.
        obj = await Node.init(schema=InfrahubKind.REPOSITORY, db=db)
        await obj.new(
            db=db,
            name=git_repo_car_dealership.name,
            description="test repository",
            location="git@github.com:mock/test.git",
        )
        await obj.save(db=db)

        # Initialize the repository on the file system
        repo = await InfrahubRepository.new(
            id=obj.id, name=git_repo_car_dealership.name, location=git_repo_car_dealership.path, client=client
        )

        commit = repo.get_commit_value(branch_name="main")
        missing_file_name = "i_do_not_exist.txt"
        response = await test_client.get(
            url=f"/api/file/{repo.id}/{missing_file_name}?commit={commit}",
            headers={"Authorization": "Token XXXX"},
        )
        errors = response.json()["errors"]
        assert len(errors) == 1
        assert errors[0]["message"] == f"Unable to find the file at 'car-dealership::{commit}::{missing_file_name}'."
        assert errors[0]["extensions"]["code"] == 404
