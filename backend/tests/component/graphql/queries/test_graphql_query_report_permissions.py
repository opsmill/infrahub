from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.constants import InfrahubKind, PermissionAction, PermissionDecision
from infrahub.core.node import Node
from infrahub.core.protocols import CoreAccount
from infrahub.graphql.cost.tasks import refresh_query_cost_statistics
from tests.component.graphql.cost.helpers import get_counting_database

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from httpx import Response

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from tests.adapters.cache import MemoryCache
    from tests.component.graphql.conftest import PermissionsHelper

TEST_KINDS_VIEWER_TOKEN = "test-kinds-viewer"
PERSON_VIEWER_TOKEN = "person-viewer"

PERSONS_CARS_QUERY = (
    "query { TestPerson { edges { node { name { value } cars { edges { node { name { value } } } } } } } }"
)

REPORT_QUERY = """
query ($q: String!, $variables: GenericScalar) {
  InfrahubGraphQLQueryReport(query: $q, variables: $variables) {
    cost_estimate {
      mode
      fields { path source expected { nodes } worst_case_is_bound }
    }
  }
}
"""


async def _create_viewer(db: InfrahubDatabase, name: str, kind_name: str, token: str) -> CoreAccount:
    """Create an account that can view the kinds of the Test namespace matching `kind_name`, with an API token."""
    account = await Node.init(db=db, schema=CoreAccount)
    await account.new(db=db, name=name, password=name)
    await account.save(db=db)

    api_token = await Node.init(db=db, schema=InfrahubKind.ACCOUNTTOKEN)
    await api_token.new(db=db, token=token, account=account)
    await api_token.save(db=db)

    permission = await Node.init(db=db, schema=InfrahubKind.OBJECTPERMISSION)
    await permission.new(
        db=db,
        namespace="Test",
        name=kind_name,
        action=PermissionAction.VIEW.value,
        decision=PermissionDecision.ALLOW_DEFAULT.value,
    )
    await permission.save(db=db)

    role = await Node.init(db=db, schema=InfrahubKind.ACCOUNTROLE)
    await role.new(db=db, name=name, permissions=[permission])
    await role.save(db=db)

    group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group.new(db=db, name=name, roles=[role], members=[account])
    await group.save(db=db)
    return account


@pytest.fixture
async def report_viewers(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
    memory_cache: MemoryCache,
    permissions_helper: PermissionsHelper,
) -> PermissionsHelper:
    """The first account can view TestPerson and TestCar, the second account TestPerson only; statistics are refreshed."""
    person = await Node.init(db=db, schema="TestPerson")
    await person.new(db=db, name="Carol")
    await person.save(db=db)
    for index in range(2):
        car = await Node.init(db=db, schema="TestCar")
        await car.new(db=db, name=f"carol-{index}", owner=person)
        await car.save(db=db)
    await refresh_query_cost_statistics()

    permissions_helper._default_branch = default_branch
    permissions_helper._first = await _create_viewer(
        db=db, name="test-kinds-viewer", kind_name="*", token=TEST_KINDS_VIEWER_TOKEN
    )
    permissions_helper._second = await _create_viewer(
        db=db, name="person-viewer", kind_name="Person", token=PERSON_VIEWER_TOKEN
    )
    return permissions_helper


def _post(client: TestClient, query: str, token: str, variables: dict[str, Any]) -> Response:
    return client.post("/graphql", json={"query": query, "variables": variables}, headers={"X-INFRAHUB-KEY": token})


async def test_account_without_view_permission_gets_the_error_of_running_the_query(
    counting_client: TestClient, report_viewers: PermissionsHelper
) -> None:
    with counting_client:
        running = _post(client=counting_client, query=PERSONS_CARS_QUERY, token=PERSON_VIEWER_TOKEN, variables={})
        database = get_counting_database(client=counting_client)
        database.reset_counts()
        report = _post(
            client=counting_client,
            query=REPORT_QUERY,
            token=PERSON_VIEWER_TOKEN,
            variables={"q": PERSONS_CARS_QUERY, "variables": {}},
        )
        estimate_queries = [name for name in database.query_counts if name.startswith("graphql-cost-")]

    assert running.status_code == 403
    assert running.json()["data"] is None
    running_messages = [error["message"] for error in running.json()["errors"]]
    assert len(running_messages) == 1
    assert report.status_code == 200
    assert report.json()["data"] is None
    assert [error["message"] for error in report.json()["errors"]] == running_messages
    assert estimate_queries == []


async def test_account_with_view_permission_gets_the_estimate(
    counting_client: TestClient, report_viewers: PermissionsHelper
) -> None:
    with counting_client:
        database = get_counting_database(client=counting_client)
        database.reset_counts()
        report = _post(
            client=counting_client,
            query=REPORT_QUERY,
            token=TEST_KINDS_VIEWER_TOKEN,
            variables={"q": PERSONS_CARS_QUERY, "variables": {}},
        )
        first_step_queries = database.count_for("graphql-cost-first-step-nodes")

    assert report.status_code == 200
    assert "errors" not in report.json()
    assert report.json()["data"]["InfrahubGraphQLQueryReport"]["cost_estimate"] == {
        "mode": "COUNTED_FIRST_STEP",
        "fields": [
            {"path": "TestPerson", "source": "COUNTED", "expected": {"nodes": 1}, "worst_case_is_bound": True},
            {"path": "TestPerson/cars", "source": "COUNTED", "expected": {"nodes": 2}, "worst_case_is_bound": True},
        ],
    }
    assert first_step_queries == 1
