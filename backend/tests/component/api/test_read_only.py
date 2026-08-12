import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch, create_default_menu
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from tests.conftest import do_car_person_schema_unregistered
from tests.helpers.test_app import TestInfrahubApp
from tests.helpers.test_client import InfrahubTestClient


class TestApiReadOnly(TestInfrahubApp):
    """Read-only API endpoint tests sharing a single application setup.

    Tests in this class must not mutate the database, the schema, or settings after
    their class-scoped fixtures ran; tests exercising mutating endpoints belong in
    their own modules.
    """

    @pytest.fixture(scope="class")
    def admin_headers(self, api_admin_token: str) -> dict[str, str]:
        return {"X-INFRAHUB-KEY": api_admin_token}

    @pytest.fixture(scope="class")
    def unprivileged_headers(self, api_unprivileged_token: str) -> dict[str, str]:
        return {"X-INFRAHUB-KEY": api_unprivileged_token}

    @pytest.fixture(scope="class")
    async def default_menu(self, db: InfrahubDatabase, initialize_registry: None) -> None:
        await create_default_menu(db=db)

    @pytest.fixture(scope="class")
    async def branch2(self, db: InfrahubDatabase, initialize_registry: None) -> Branch:
        return await create_branch(branch_name="branch2", db=db)

    @pytest.fixture(scope="class")
    async def car_person_data(
        self, db: InfrahubDatabase, default_branch: Branch, initialize_registry: None
    ) -> dict[str, Node]:
        registry.schema.register_schema(schema=do_car_person_schema_unregistered(), branch=default_branch.name)
        # The app initialization reloaded the branch registry from the database, so the
        # default_branch fixture object is no longer the instance requests resolve; refresh
        # the schema hash on the active instance.
        branch = registry.get_branch_from_registry(branch=default_branch.name)
        branch.update_schema_hash()
        await branch.save(db=db)

        p1 = await Node.init(db=db, schema="TestPerson")
        await p1.new(db=db, name="John", height=180)
        await p1.save(db=db)
        p2 = await Node.init(db=db, schema="TestPerson")
        await p2.new(db=db, name="Jane", height=170)
        await p2.save(db=db)
        c1 = await Node.init(db=db, schema="TestCar")
        await c1.new(db=db, name="volt", nbr_seats=3, is_electric=True, owner=p1)
        await c1.save(db=db)
        c2 = await Node.init(db=db, schema="TestCar")
        await c2.new(db=db, name="bolt", nbr_seats=2, is_electric=True, owner=p1)
        await c2.save(db=db)
        c3 = await Node.init(db=db, schema="TestCar")
        await c3.new(db=db, name="nolt", nbr_seats=4, is_electric=True, owner=p2)
        await c3.save(db=db)

        return {"p1": p1, "p2": p2, "c1": c1, "c2": c2, "c3": c3}

    async def test_get_invalid(self, test_client: InfrahubTestClient) -> None:
        response = await test_client.get("/api/so-such-route")

        assert response.status_code == 404
        assert response.json()
        assert response.json()["errors"]
        assert response.json()["errors"] == [
            {"message": "The requested endpoint /api/so-such-route does not exist", "extensions": {"code": 404}}
        ]

    async def test_openapi(self, test_client: InfrahubTestClient) -> None:
        """Validate that the OpenAPI specs can be generated."""
        response = await test_client.get("/api/openapi.json")

        assert response.status_code == 200
        assert response.json() is not None

    async def test_get_menu_not_admin(
        self, test_client: InfrahubTestClient, unprivileged_headers: dict[str, str], default_menu: None
    ) -> None:
        response = await test_client.get("/api/menu", headers=unprivileged_headers)

        assert response.status_code == 200
        assert response.json() is not None
        data = response.json()
        internal_menu_items = [item["identifier"] for item in data["sections"]["internal"]]
        assert "BuiltinAdmin" not in internal_menu_items

    async def test_get_menu_admin(
        self, test_client: InfrahubTestClient, admin_headers: dict[str, str], default_menu: None
    ) -> None:
        response = await test_client.get("/api/menu", headers=admin_headers)

        assert response.status_code == 200
        assert response.json() is not None
        data = response.json()
        internal_menu_items = [item["identifier"] for item in data["sections"]["internal"]]
        assert "BuiltinAdmin" in internal_menu_items

    async def test_graphql_endpoint(
        self, test_client: InfrahubTestClient, admin_headers: dict[str, str], car_person_data: dict[str, Node]
    ) -> None:
        query = """
        query {
            TestPerson {
                edges {
                    node {
                        name {
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

        response = await test_client.post("/graphql", json={"query": query}, headers=admin_headers)

        assert response.status_code == 200
        assert "errors" not in response.json()
        assert response.json()["data"] is not None
        result = response.json()["data"]

        result_per_name = {result["node"]["name"]["value"]: result for result in result["TestPerson"]["edges"]}

        assert sorted(result_per_name.keys()) == ["Jane", "John"]
        assert len(result_per_name["John"]["node"]["cars"]["edges"]) == 2
        assert len(result_per_name["Jane"]["node"]["cars"]["edges"]) == 1

    async def test_graphql_options(
        self, test_client: InfrahubTestClient, admin_headers: dict[str, str], branch2: Branch
    ) -> None:
        response = await test_client.options("/graphql", headers=admin_headers)

        assert response.status_code == 200
        assert "Allow" in response.headers
        assert response.headers["Allow"] == "GET, POST, OPTIONS"

        response = await test_client.options("/graphql/branch2", headers=admin_headers)

        assert response.status_code == 200
        assert "Allow" in response.headers
        assert response.headers["Allow"] == "GET, POST, OPTIONS"

        response = await test_client.options("/graphql/notvalid", headers=admin_headers)

        assert response.status_code == 404

    async def test_read_profile(self, test_client: InfrahubTestClient, admin_headers: dict[str, str]) -> None:
        query = """
        query {
            AccountProfile {
                name {
                    value
                }
            }
        }
        """

        response = await test_client.post("/graphql", json={"query": query}, headers=admin_headers)

        assert response.status_code == 200
        assert response.json() == {"data": {"AccountProfile": {"name": {"value": "admin"}}}}

    async def test_download_schema(
        self, test_client: InfrahubTestClient, admin_headers: dict[str, str], branch2: Branch
    ) -> None:
        response = await test_client.get("/schema.graphql", headers=admin_headers)
        assert response.status_code == 200

        response = await test_client.get("/schema.graphql?branch=branch2", headers=admin_headers)
        assert response.status_code == 200

        response = await test_client.get("/schema.graphql?branch=notvalid", headers=admin_headers)
        assert response.status_code == 400
