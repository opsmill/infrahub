from __future__ import annotations

from ipaddress import ip_network
from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk.protocols import CoreAccount, CoreProposedChange
from prefect import get_client

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.proposed_change.constants import ProposedChangeState
from infrahub.service_portal import tasks
from infrahub.service_portal.constants import ServiceRequestStatus
from infrahub.service_portal.models import ServiceRequestRun
from infrahub.service_portal.tasks import request_branch_name
from infrahub.workflows.catalogue import SERVICE_REQUEST_RUN
from tests.helpers.events import query_events_by_name
from tests.helpers.test_app import TestInfrahubApp

from .conftest import (
    ACTIVATE_GENERATOR,
    ACTIVATE_TARGETS,
    ALLOCATE_GENERATOR,
    SERVICE_KIND,
    port_id,
    service_port_ids,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.node import InfrahubNode
    from prefect.client.orchestration import PrefectClient

    from infrahub.database import InfrahubDatabase
    from infrahub.services.adapters.workflow.local import WorkflowLocalExecution

TEMPLATE_KIND = f"Template{SERVICE_KIND}"

CREATED_BY = """
query CreatedBy($id: ID!) {
    %(kind)s(ids: [$id]) { edges { node_metadata { created_by { id } } } }
}
"""

GROUP_MEMBERS = """
query Members($name: String!) {
    CoreStandardGroup(name__value: $name) {
        edges { node { members { edges { node { id } relationship_metadata { created_by { id } } } } } }
    }
}
"""


class TestServiceRequestWorkflow(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def prefect_client(self, prefect_test_fixture: None) -> AsyncGenerator[PrefectClient, None]:
        async with get_client(sync_client=False) as client:
            yield client

    @pytest.fixture(scope="class")
    async def requester(self, dedicated_internet_repo: InfrahubNode, client: InfrahubClient) -> InfrahubNode:
        return await client.get(kind=CoreAccount, name__value="unprivileged")

    @pytest.fixture(scope="class")
    async def entry(self, dedicated_internet_repo: InfrahubNode, client: InfrahubClient) -> InfrahubNode:
        template = await client.create(kind=TEMPLATE_KIND, template_name="gold", ip_package="large")
        await template.save()
        entry = await client.create(
            kind=InfrahubKind.SERVICECATALOGENTRY,
            name="Dedicated Internet",
            target_kind=SERVICE_KIND,
            generators=[ALLOCATE_GENERATOR, ACTIVATE_GENERATOR],
            fields=["name", "location", "bandwidth"],
            template=template,
        )
        await entry.save()
        return entry

    @staticmethod
    async def submit(db: InfrahubDatabase, entry: InfrahubNode, requester: InfrahubNode, **inputs: Any) -> str:
        """Store a submitted request as the ServiceRequestSubmit mutation does, without running its workflow.

        `inputs` are attribute values, stored in the create-input shape the mutation accepts.
        """
        request = await Node.init(db=db, schema=InfrahubKind.SERVICEREQUEST)
        await request.new(
            db=db,
            inputs={
                "value": {
                    "location": {"hfid": ["site-a"]},
                    "bandwidth": {"value": "1000"},
                    **{name: {"value": value} for name, value in inputs.items()},
                }
            },
            entry=entry.id,
            requester=requester.id,
        )
        await request.save(db=db)
        return request.id

    @staticmethod
    async def run(workflow: WorkflowLocalExecution, request_id: str, requester: InfrahubNode) -> None:
        context = InfrahubContext.init(
            branch=registry.get_branch_from_registry(),
            account=AccountSession(account_id=requester.id, auth_type=AuthType.JWT),
        )
        await workflow.execute_workflow(
            workflow=SERVICE_REQUEST_RUN,
            context=context,
            parameters={"model": ServiceRequestRun(request_id=request_id)},
        )

    @staticmethod
    async def created_by(client: InfrahubClient, kind: str, node_id: str, branch: str | None = None) -> str:
        result = await client.execute_graphql(
            query=CREATED_BY % {"kind": kind}, variables={"id": node_id}, branch_name=branch
        )
        return result[kind]["edges"][0]["node_metadata"]["created_by"]["id"]

    @pytest.fixture(scope="class")
    async def fulfilled(
        self,
        db: InfrahubDatabase,
        workflow_local: WorkflowLocalExecution,
        entry: InfrahubNode,
        requester: InfrahubNode,
    ) -> str:
        request_id = await self.submit(db=db, entry=entry, requester=requester, name="acme-hq")
        await self.run(workflow=workflow_local, request_id=request_id, requester=requester)
        return request_id

    async def test_review_mode_builds_branch_and_opens_one_proposed_change(
        self, fulfilled: str, client: InfrahubClient
    ) -> None:
        request = await client.get(kind=InfrahubKind.SERVICEREQUEST, id=fulfilled, prefetch_relationships=True)
        branch = request_branch_name(fulfilled)
        service = await client.get(kind=SERVICE_KIND, name__value="acme-hq", branch=branch)
        changes = await client.filters(
            kind=CoreProposedChange, source_branch__value=branch, state__value=ProposedChangeState.OPEN.value
        )

        assert request.status.value == ServiceRequestStatus.IN_REVIEW.value
        assert request.branch.value == branch
        assert [change.id for change in changes] == [request.proposed_change.id]
        assert changes[0].destination_branch.value == registry.default_branch
        assert request.message.value == "Waiting for an engineer to review the change"
        assert await client.filters(kind=SERVICE_KIND, name__value="acme-hq") == []
        assert await client.get(kind="IpamVLAN", name__value="vlan-acme-hq", branch=branch)
        assert service.vlan.id
        assert service.prefix.id
        assert service.gateway_ip_address.id

    async def test_parity_with_direct_generator_run(self, fulfilled: str, client: InfrahubClient) -> None:
        branch = request_branch_name(fulfilled)
        service = await client.get(kind=SERVICE_KIND, name__value="acme-hq", branch=branch, prefetch_relationships=True)

        assert service.status.value == "active"
        assert 1000 <= service.vlan.peer.vlan_id.value <= 2000
        assert service.prefix.peer.prefix.value.prefixlen == 29
        assert service.prefix.peer.prefix.value.subnet_of(ip_network("203.0.113.0/24"))
        assert service.gateway_ip_address.peer.address.value.ip in ip_network("172.16.1.0/24")
        assert await service_port_ids(client, branch, service.id) == [
            await port_id(client, branch, "core-a1", "port-1")
        ]

    async def test_template_values_fill_fields_not_submitted(self, fulfilled: str, client: InfrahubClient) -> None:
        service = await client.get(kind=SERVICE_KIND, name__value="acme-hq", branch=request_branch_name(fulfilled))

        assert service.ip_package.value == "large"
        assert service.bandwidth.value == "1000"

    async def test_requester_is_credited_with_the_request_writes_only(
        self, db: InfrahubDatabase, fulfilled: str, client: InfrahubClient, requester: InfrahubNode
    ) -> None:
        branch = request_branch_name(fulfilled)
        request = await client.get(kind=InfrahubKind.SERVICEREQUEST, id=fulfilled, prefetch_relationships=True)
        service = await client.get(kind=SERVICE_KIND, name__value="acme-hq", branch=branch)
        vlan = await client.get(kind="IpamVLAN", name__value="vlan-acme-hq", branch=branch)
        members = await client.execute_graphql(
            query=GROUP_MEMBERS, variables={"name": ACTIVATE_TARGETS}, branch_name=branch
        )
        membership = next(
            edge
            for edge in members["CoreStandardGroup"]["edges"][0]["node"]["members"]["edges"]
            if edge["node"]["id"] == service.id
        )
        async with db.start_session() as dbs:
            request_branch = await Branch.get_by_name(db=dbs, name=branch)

        assert await self.created_by(client, SERVICE_KIND, service.id, branch) == requester.id
        assert membership["relationship_metadata"]["created_by"]["id"] == requester.id
        assert request_branch.created_by == requester.id
        assert await self.created_by(client, "CoreProposedChange", request.proposed_change.id) == requester.id
        assert await self.created_by(client, "IpamVLAN", vlan.id, branch) != requester.id

    async def test_status_and_message_changes_emit_node_updated_events(
        self, fulfilled: str, prefect_client: PrefectClient
    ) -> None:
        events = await query_events_by_name(
            client=prefect_client, event_name="infrahub.node.updated", resource_id=f"infrahub.node.{fulfilled}"
        )
        updated_fields = [
            {resource["infrahub.field.name"] for resource in event.related if "infrahub.field.name" in resource}
            for event in events
        ]

        assert any("status" in fields for fields in updated_fields)
        assert any("message" in fields for fields in updated_fields)

    async def test_rerun_reuses_branch_service_and_proposed_change(
        self,
        fulfilled: str,
        client: InfrahubClient,
        workflow_local: WorkflowLocalExecution,
        requester: InfrahubNode,
    ) -> None:
        branch = request_branch_name(fulfilled)
        before = await client.get(kind=InfrahubKind.SERVICEREQUEST, id=fulfilled, prefetch_relationships=True)

        await self.run(workflow=workflow_local, request_id=fulfilled, requester=requester)

        after = await client.get(kind=InfrahubKind.SERVICEREQUEST, id=fulfilled, prefetch_relationships=True)
        branches = [name for name in await client.branch.all() if name.startswith(branch)]
        changes = await client.filters(kind=CoreProposedChange, source_branch__value=branch)
        services = await client.filters(kind=SERVICE_KIND, name__value="acme-hq", branch=branch)

        assert branches == [branch]
        assert [change.id for change in changes] == [before.proposed_change.id]
        assert len(services) == 1
        assert after.proposed_change.id == before.proposed_change.id
        assert after.status.value == ServiceRequestStatus.IN_REVIEW.value

    async def test_generator_error_stops_before_proposed_change(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        workflow_local: WorkflowLocalExecution,
        entry: InfrahubNode,
        requester: InfrahubNode,
    ) -> None:
        request_id = await self.submit(db=db, entry=entry, requester=requester, name="acme-fail", fail_generator=True)

        with pytest.raises(RuntimeError, match=f"Generator {ACTIVATE_GENERATOR} failed"):
            await self.run(workflow=workflow_local, request_id=request_id, requester=requester)

        request = await client.get(kind=InfrahubKind.SERVICEREQUEST, id=request_id)
        changes = await client.filters(kind=CoreProposedChange, source_branch__value=request_branch_name(request_id))
        assert request.status.value == ServiceRequestStatus.GENERATING.value
        assert changes == []

    async def test_object_outside_target_group_stops_before_proposed_change(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        workflow_local: WorkflowLocalExecution,
        entry: InfrahubNode,
        requester: InfrahubNode,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A generator whose targets don't hold the object runs zero times, which stops the workflow."""

        async def skip_group_join(**kwargs: Any) -> None: ...

        monkeypatch.setattr(tasks, "_add_to_target_group", skip_group_join)
        request_id = await self.submit(db=db, entry=entry, requester=requester, name="acme-stray")

        with pytest.raises(RuntimeError, match=f"Generator {ALLOCATE_GENERATOR} did not run for the service object"):
            await self.run(workflow=workflow_local, request_id=request_id, requester=requester)

        request = await client.get(kind=InfrahubKind.SERVICEREQUEST, id=request_id)
        changes = await client.filters(kind=CoreProposedChange, source_branch__value=request_branch_name(request_id))
        assert request.status.value == ServiceRequestStatus.GENERATING.value
        assert changes == []
