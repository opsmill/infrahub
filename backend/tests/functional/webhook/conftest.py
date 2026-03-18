from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncGenerator

import pytest
from prefect.client.orchestration import PrefectClient, get_client

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.workflows.catalogue import WEBHOOK_CONFIGURE, WEBHOOK_PROCESS, WORKER_POOLS
from infrahub.workflows.initialization import setup_worker_pools
from tests.constants import TestKind
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import CAR_SCHEMA, load_schema

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


BRANCH_CREATED_PAYLOAD: dict[str, Any] = {
    "context": {
        "event": {
            "id": "24790022-2bc8-42ab-a447-bf3e84675901",
            "name": "infrahub.branch.created",
            "ancestors": [],
            "parent_id": None,
        },
        "branch": {"id": "182853ef-58a3-b3cc-3e80-c5161f4171c1", "name": "-global-"},
        "account": {
            "auth_type": "api",
            "account_id": "182853f2-3a43-c7f9-3e84-c5152eff4b17",
            "session_id": None,
            "authenticated": None,
        },
    }
}


@pytest.fixture(scope="class")
async def initial_dataset(
    db: InfrahubDatabase,
    register_core_schema: SchemaBranch,
    client: InfrahubClient,
    git_repos_source_dir_module_scope: Path,
    prefect_test_fixture: None,
) -> None:
    await load_schema(db, schema=CAR_SCHEMA)

    john = await Node.init(schema=TestKind.PERSON, db=db)
    await john.new(db=db, name="John", height=175, age=25, description="The famous Joe Doe")
    await john.save(db=db)

    koenigsegg = await Node.init(schema=TestKind.MANUFACTURER, db=db)
    await koenigsegg.new(db=db, name="Koenigsegg")
    await koenigsegg.save(db=db)

    people = await Node.init(schema=InfrahubKind.STANDARDGROUP, db=db)
    await people.new(db=db, name="people", members=[john])
    await people.save(db=db)

    jesko = await Node.init(schema=TestKind.CAR, db=db)
    await jesko.new(
        db=db,
        name="Jesko",
        color="Red",
        description="A limited production mid-engine sports car",
        owner=john,
        manufacturer=koenigsegg,
    )
    await jesko.save(db=db)

    FileRepo(name="car-dealership", sources_directory=git_repos_source_dir_module_scope)
    client_repository = await client.create(
        kind=InfrahubKind.REPOSITORY,
        data={"name": "car-dealership", "location": f"{git_repos_source_dir_module_scope}/car-dealership"},
    )
    await client_repository.save()


@pytest.fixture(scope="class")
async def prefect_client(prefect_test_fixture: None) -> AsyncGenerator[PrefectClient, None]:
    async with get_client(sync_client=False) as client:
        yield client


@pytest.fixture(scope="class")
async def webhook_deployment(db: InfrahubDatabase, prefect_client: PrefectClient) -> None:
    await setup_worker_pools(client=prefect_client)
    await WEBHOOK_PROCESS.save(client=prefect_client, work_pool=WORKER_POOLS[0])
    await WEBHOOK_CONFIGURE.save(client=prefect_client, work_pool=WORKER_POOLS[0])


@pytest.fixture(scope="class")
async def webhook1(db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient) -> Node:
    webhook = await Node.init(schema=InfrahubKind.STANDARDWEBHOOK, db=db)
    await webhook.new(
        db=db,
        name="Webhook1",
        url="https://url.mock",
        shared_key="1234567890",
        validate_certificates=False,
        event_type="infrahub.branch.created",
        branch_scope="all_branches",
    )
    await webhook.save(db=db)
    return webhook


@pytest.fixture(scope="class")
async def webhook2(db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient) -> Node:
    transform = await client.get(
        kind=InfrahubKind.TRANSFORMPYTHON, name__value="WebhookTransformer", raise_when_missing=True
    )

    webhook = await Node.init(schema=InfrahubKind.CUSTOMWEBHOOK, db=db)
    await webhook.new(
        db=db,
        name="Webhook2",
        url="https://url.mock",
        validate_certificates=False,
        event_type="infrahub.node.updated",
        branch_scope="all_branches",
        transformation=transform.id,
    )
    await webhook.save(db=db)
    return webhook


@pytest.fixture(scope="class")
async def webhook3(db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient) -> Node:
    webhook = await Node.init(schema=InfrahubKind.CUSTOMWEBHOOK, db=db)
    await webhook.new(
        db=db,
        name="Webhook3",
        url="https://url.mock",
        validate_certificates=False,
        event_type="infrahub.node.created",
        branch_scope="other_branches",
    )
    await webhook.save(db=db)
    return webhook


@pytest.fixture(scope="class")
async def webhook4(db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient) -> Node:
    webhook = await Node.init(schema=InfrahubKind.STANDARDWEBHOOK, db=db)
    await webhook.new(
        db=db,
        name="Webhook4",
        url="https://url.mock",
        shared_key="1234567890",
        validate_certificates=False,
        node_kind="BuiltinTag",
        event_type="infrahub.node.created",
        branch_scope="all_branches",
    )
    await webhook.save(db=db)
    return webhook


@pytest.fixture(scope="class")
async def inactive_webhook(db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient) -> Node:
    webhook = await Node.init(schema=InfrahubKind.STANDARDWEBHOOK, db=db)
    await webhook.new(
        db=db,
        name="InactiveWebhook",
        url="https://url.mock",
        shared_key="1234567890",
        validate_certificates=False,
        event_type="infrahub.node.created",
        branch_scope="all_branches",
        active=False,
    )
    await webhook.save(db=db)
    return webhook
