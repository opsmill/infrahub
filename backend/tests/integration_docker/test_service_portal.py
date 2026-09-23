from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import httpx
import pytest
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.protocols import CoreProposedChange
from infrahub_sdk.testing.docker import TestInfrahubDockerClient
from infrahub_sdk.testing.repository import GitRepo, GitRepoType

from infrahub.core.constants import InfrahubKind, PermissionAction
from infrahub.permissions.constants import PermissionDecisionFlag
from infrahub.proposed_change.constants import ProposedChangeState
from infrahub.service_portal.constants import ServiceRequestStatus
from tests.helpers.fixtures import get_fixtures_dir

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk.node import InfrahubNode

# Stack start, repository import, both generators and the proposed change outlast the 5 minute default.
pytestmark = [pytest.mark.shard_b, pytest.mark.timeout(900)]

REPOSITORY_NAME = "dedicated-internet"
SERVICE_KIND = "ServiceDedicatedInternet"
REQUESTER = "requester"
REQUESTER_PASSWORD = "Requester-Password-123"
DEADLINE_SECONDS = 300

SUBMIT = """
mutation Submit($entry: String!, $inputs: GenericScalar!) {
    ServiceRequestSubmit(data: {entry_id: $entry, inputs: $inputs}) { ok request { id } task { id } }
}
"""


class TestServicePortalClientDisconnect(TestInfrahubDockerClient):
    @pytest.fixture(scope="class")
    async def entry(self, client: InfrahubClient, remote_repos_dir: Path) -> InfrahubNode:
        repo = GitRepo(
            type=GitRepoType.INTEGRATED,
            name=REPOSITORY_NAME,
            src_directory=get_fixtures_dir() / "repos" / REPOSITORY_NAME / "initial__main",
            dst_directory=remote_repos_dir,
        )
        await repo.add_to_infrahub(client=client)
        # Importing the schema, objects and generators takes longer than the default 30 s wait
        assert await repo.wait_for_sync_to_complete(client=client, retries=60)

        entry = await client.create(
            kind=InfrahubKind.SERVICECATALOGENTRY,
            name="Dedicated Internet",
            target_kind=SERVICE_KIND,
            generators=["dedicated_internet_allocate", "dedicated_internet_activate"],
            fields=["name", "location", "bandwidth", "ip_package"],
        )
        await entry.save()
        return entry

    @pytest.fixture(scope="class")
    async def requester(self, client: InfrahubClient) -> InfrahubNode:
        """An account that may view everything and create the service kind on branches only."""
        # Every deployment ships an allow-all view permission; the requester reuses it.
        view = await client.get(
            kind=InfrahubKind.OBJECTPERMISSION,
            namespace__value="*",
            name__value="*",
            action__value=PermissionAction.VIEW.value,
            decision__value=PermissionDecisionFlag.ALLOW_ALL.value,
        )
        create = await client.create(
            kind=InfrahubKind.OBJECTPERMISSION,
            namespace="Service",
            name="DedicatedInternet",
            action=PermissionAction.CREATE.value,
            decision=PermissionDecisionFlag.ALLOW_OTHER.value,
        )
        await create.save()
        role = await client.create(kind=InfrahubKind.ACCOUNTROLE, name="requesters", permissions=[view, create])
        await role.save()
        account = await client.create(kind=InfrahubKind.ACCOUNT, name=REQUESTER, password=REQUESTER_PASSWORD)
        await account.save()
        group = await client.create(kind=InfrahubKind.ACCOUNTGROUP, name="requesters", roles=[role], members=[account])
        await group.save()
        return account

    async def test_request_completes_after_submitting_client_disconnects(
        self, client: InfrahubClient, entry: InfrahubNode, requester: InfrahubNode
    ) -> None:
        site = await client.get(kind="LocationSite", name__value="site-a")
        async with httpx.AsyncClient(base_url=client.address) as submitter:
            login = await submitter.post(
                "/api/auth/login", json={"username": REQUESTER, "password": REQUESTER_PASSWORD}
            )
            login.raise_for_status()
            response = await submitter.post(
                "/graphql",
                headers={"Authorization": f"Bearer {login.json()['access_token']}"},
                json={
                    "query": SUBMIT,
                    "variables": {
                        "entry": entry.id,
                        "inputs": {
                            "name": {"value": "acme-hq"},
                            "location": {"id": site.id},
                            "bandwidth": {"value": "1000"},
                            "ip_package": {"value": "small"},
                        },
                    },
                },
            )
        # The submitting client is closed: from here on only the task worker drives the request.
        response.raise_for_status()
        payload = response.json()
        assert "errors" not in payload, payload
        request_id = payload["data"]["ServiceRequestSubmit"]["request"]["id"]

        observer = InfrahubClient(config=Config(address=client.address, username="admin", password="infrahub"))
        request = await observer.get(kind=InfrahubKind.SERVICEREQUEST, id=request_id, prefetch_relationships=True)
        for _ in range(DEADLINE_SECONDS // 5):
            if request.status.value not in {
                ServiceRequestStatus.SUBMITTED.value,
                ServiceRequestStatus.GENERATING.value,
            }:
                break
            await asyncio.sleep(5)
            request = await observer.get(kind=InfrahubKind.SERVICEREQUEST, id=request_id, prefetch_relationships=True)

        assert request.status.value == ServiceRequestStatus.IN_REVIEW.value, request.message.value
        assert request.requester.id == requester.id
        assert request.proposed_change.id
        changes = await observer.filters(
            kind=CoreProposedChange,
            source_branch__value=request.branch.value,
            state__value=ProposedChangeState.OPEN.value,
        )
        assert [change.id for change in changes] == [request.proposed_change.id]
