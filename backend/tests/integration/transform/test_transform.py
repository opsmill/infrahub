from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from infrahub_sdk import Config, InfrahubClient

from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import first_time_initialization, initialization
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase
from infrahub.git import InfrahubRepository
from infrahub.server import app, app_initialization
from infrahub.services import InfrahubServices, services
from tests.adapters.log import FakeTaskReportLogger
from tests.constants import TestKind
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp
from tests.helpers.test_client import InfrahubTestClient

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from tests.helpers.file_repo import FileRepo


@pytest.fixture
def init_service():
    original = services.service
    service = InfrahubServices(client=InfrahubClient())
    services.service = service
    yield service
    services.service = original


class TestTransforms(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def base_dataset(self, db: InfrahubDatabase):
        await delete_all_nodes(db=db)
        await first_time_initialization(db=db)
        await load_schema(db, schema=CAR_SCHEMA)

        await initialization(db=db)

        john = await Node.init(schema=TestKind.PERSON, db=db)
        await john.new(db=db, name="John", height=175, age=25)
        await john.save(db=db)

        people = await Node.init(schema=InfrahubKind.STANDARDGROUP, db=db)
        await people.new(db=db, name="people", members=[john])
        await people.save(db=db)

        query1 = """
        query PersonWithTheirCars($name: String!) {
            TestingPerson(name__value: $name) {
                edges {
                    node {
                        name {
                            value
                        }
                        age {
                            value
                        }
                        cars {
                            edges {
                                node {
                                    name {
                                        value
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        q1 = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
        await q1.new(db=db, name="query01", query=query1)
        await q1.save(db=db)

    @pytest.fixture(scope="class")
    async def test_client(
        self,
        base_dataset,
        redis: dict[int, int] | None,
        nats: dict[int, int] | None,
    ) -> InfrahubTestClient:
        await app_initialization(app)
        return InfrahubTestClient(app=app)

    @pytest.fixture(scope="class")
    async def client(self, test_client: InfrahubTestClient, integration_helper):  # type: ignore[override]
        admin_token = await integration_helper.create_token()
        config = Config(api_token=admin_token, requester=test_client.async_request)

        return InfrahubClient(config=config)

    @pytest.fixture(scope="class")
    async def repo(self, test_client, client, db: InfrahubDatabase, git_repo_car_dealership: FileRepo, git_repos_dir):
        # Create the repository in the Graph
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
            id=obj.id,
            name=git_repo_car_dealership.name,
            location=git_repo_car_dealership.path,
            task_report=FakeTaskReportLogger(),
            client=client,
        )

        return repo

    async def test_transform_jinja(self, db: InfrahubDatabase, client: InfrahubClient, repo: InfrahubRepository):
        repositories = await NodeManager.query(db=db, schema=InfrahubKind.REPOSITORY)
        queries = await NodeManager.query(db=db, schema=InfrahubKind.GRAPHQLQUERY)

        t1 = await Node.init(db=db, schema=InfrahubKind.TRANSFORMJINJA2)
        await t1.new(
            db=db,
            name="test-rfile",
            query=str(queries[0].id),
            repository=str(repositories[0].id),
            template_path="templates/person_with_cars.j2",
        )
        await t1.save(db=db)

        response = await client._get(url=f"{client.address}/api/transform/jinja2/test-rfile?name=John")
        assert response.text == "Name: John"

    async def test_transform_python(
        self, db: InfrahubDatabase, client: InfrahubClient, init_service, repo: InfrahubRepository
    ):
        repositories = await NodeManager.query(db=db, schema=InfrahubKind.REPOSITORY)
        queries = await NodeManager.query(db=db, schema=InfrahubKind.GRAPHQLQUERY)

        t2 = await Node.init(db=db, schema=InfrahubKind.TRANSFORMPYTHON)
        await t2.new(
            db=db,
            name="test-python-transform",
            query=str(queries[0].id),
            repository=str(repositories[0].id),
            class_name="PersonWithCarsTransform",
            file_path="transforms/person_with_cars_transform.py",
        )
        await t2.save(db=db)

        response = await client._get(url=f"{client.address}/api/transform/python/test-python-transform?name=John")
        assert response.json() == {"name": "John"}
