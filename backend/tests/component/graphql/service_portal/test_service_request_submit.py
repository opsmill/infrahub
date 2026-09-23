from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreServiceRequest
from infrahub.permissions.constants import PermissionDecisionFlag
from infrahub.service_portal.models import ServiceRequestRun
from infrahub.services import InfrahubServices
from infrahub.workflows.catalogue import SERVICE_REQUEST_RUN
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.graphql import graphql_mutation

from .conftest import ServicePortalData, TemplateEntry, create_account, session_for

if TYPE_CHECKING:
    from graphql import ExecutionResult

    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase

SUBMIT = """
mutation($entry_id: String!, $inputs: GenericScalar!) {
    ServiceRequestSubmit(data: {entry_id: $entry_id, inputs: $inputs}) {
        ok
        request { id }
        task { id }
    }
}
"""


async def submit(
    db: InfrahubDatabase, workflow: WorkflowRecorder, account: Node, entry: Node, inputs: Any
) -> ExecutionResult:
    service = await InfrahubServices.new(database=db, workflow=workflow)
    return await graphql_mutation(
        query=SUBMIT,
        db=db,
        service=service,
        account_session=session_for(account),
        variables={"entry_id": entry.id, "inputs": inputs},
    )


def valid_inputs(data: ServicePortalData) -> dict[str, Any]:
    return {
        "name": {"value": "circuit-01"},
        "speed": {"value": "small"},
        "vlan": {"value": 100},
        "provider": {"id": data.provider.id},
    }


async def test_submit_creates_a_submitted_request(db: InfrahubDatabase, service_portal_data: ServicePortalData) -> None:
    data = service_portal_data
    workflow = WorkflowRecorder()
    inputs = valid_inputs(data)

    result = await submit(db=db, workflow=workflow, account=data.requester, entry=data.entry, inputs=inputs)

    assert not result.errors
    assert result.data
    response = result.data["ServiceRequestSubmit"]
    requests = await NodeManager.query(db=db, schema=CoreServiceRequest, prefetch_relationships=True)
    assert [request.id for request in requests] == [response["request"]["id"]]
    request = requests[0]
    assert request.status.value.value == "submitted"
    assert request.inputs.value == inputs
    assert await request.requester.get_peer_id(db=db) == data.requester.id
    assert await request.entry.get_peer_id(db=db) == data.entry.id
    assert request.task_id.value == response["task"]["id"]
    assert response["ok"] is True
    assert workflow.calls == [
        {
            "kind": "submit",
            "workflow": SERVICE_REQUEST_RUN,
            "parameters": {"model": ServiceRequestRun(request_id=request.id)},
            "tags": [],
        }
    ]


async def test_submit_omits_required_fields_the_template_sets(
    db: InfrahubDatabase, service_portal_data: ServicePortalData, template_entry: TemplateEntry
) -> None:
    data = service_portal_data
    workflow = WorkflowRecorder()

    result = await submit(
        db=db,
        workflow=workflow,
        account=data.requester,
        entry=template_entry.entry,
        inputs={"name": {"value": "circuit-02"}},
    )

    assert not result.errors
    assert result.data
    assert result.data["ServiceRequestSubmit"]["ok"] is True
    assert len(workflow.submit_calls) == 1


@dataclass
class RejectedInputsCase:
    name: str
    message: str
    inputs: dict[str, Any] = field(default_factory=dict)
    """Merged over the valid inputs."""
    drop: str | None = None
    """Valid input key left out."""


@pytest.mark.parametrize(
    "case",
    [
        RejectedInputsCase(
            name="not_allowlisted",
            inputs={"color": {"value": "red"}},
            message="color is not a field of this service at color",
        ),
        RejectedInputsCase(
            name="object_template",
            inputs={"object_template": {"id": "anything"}},
            message="The object template is set by the service and can't be submitted at object_template",
        ),
        RejectedInputsCase(
            name="bad_format",
            inputs={"vlan": {"value": "one hundred"}},
            message="one hundred is not a valid Number at vlan",
        ),
        RejectedInputsCase(
            name="regex",
            inputs={"name": {"value": "Circuit 01"}},
            message="Circuit 01 must conform with the regex: '^[a-z0-9-]+$' at name",
        ),
        RejectedInputsCase(
            name="dropdown_choice",
            inputs={"speed": {"value": "huge"}},
            message="huge must be one of 'large, small' at speed",
        ),
        RejectedInputsCase(
            name="missing_required",
            drop="provider",
            message="A value must be provided for provider at provider",
        ),
    ],
    ids=lambda case: case.name,
)
async def test_submit_rejects_invalid_inputs(
    db: InfrahubDatabase, service_portal_data: ServicePortalData, case: RejectedInputsCase
) -> None:
    data = service_portal_data
    workflow = WorkflowRecorder()
    inputs = valid_inputs(data) | case.inputs
    inputs.pop(case.drop or "", None)

    result = await submit(db=db, workflow=workflow, account=data.requester, entry=data.entry, inputs=inputs)

    assert result.errors
    assert [error.message for error in result.errors] == [case.message]
    assert await NodeManager.query(db=db, schema=InfrahubKind.SERVICEREQUEST) == []
    assert workflow.calls == []


async def test_submit_rejects_a_relationship_to_the_wrong_kind(
    db: InfrahubDatabase, service_portal_data: ServicePortalData
) -> None:
    data = service_portal_data
    workflow = WorkflowRecorder()
    inputs = valid_inputs(data) | {"provider": {"id": data.tag.id}}

    result = await submit(db=db, workflow=workflow, account=data.requester, entry=data.entry, inputs=inputs)

    assert result.errors
    assert [error.message for error in result.errors] == [f"{data.tag.id} is not a TestingProvider at provider"]
    assert await NodeManager.query(db=db, schema=InfrahubKind.SERVICEREQUEST) == []
    assert workflow.calls == []


async def test_submit_rejects_a_pool_that_does_not_exist(
    db: InfrahubDatabase, service_portal_data: ServicePortalData
) -> None:
    data = service_portal_data
    workflow = WorkflowRecorder()
    inputs = valid_inputs(data) | {"vlan": {"from_pool": {"id": data.provider.id}}}

    result = await submit(db=db, workflow=workflow, account=data.requester, entry=data.entry, inputs=inputs)

    assert result.errors
    assert [error.message for error in result.errors] == [f"{data.provider.id} is not a CoreResourcePool at vlan"]
    assert await NodeManager.query(db=db, schema=InfrahubKind.SERVICEREQUEST) == []


async def test_submit_rejects_a_caller_without_create_permission_on_branches(
    db: InfrahubDatabase, service_portal_data: ServicePortalData
) -> None:
    data = service_portal_data
    workflow = WorkflowRecorder()
    account = await create_account(db=db, name="default-only", create_decision=PermissionDecisionFlag.ALLOW_DEFAULT)

    result = await submit(db=db, workflow=workflow, account=account, entry=data.entry, inputs=valid_inputs(data))

    assert result.errors
    assert [error.message for error in result.errors] == [
        "You are not allowed to create TestingCircuit objects on a branch"
    ]
    assert await NodeManager.query(db=db, schema=InfrahubKind.SERVICEREQUEST) == []
    assert workflow.calls == []


async def test_submit_rejects_a_direct_mode_entry(db: InfrahubDatabase, service_portal_data: ServicePortalData) -> None:
    data = service_portal_data
    workflow = WorkflowRecorder()

    result = await submit(
        db=db, workflow=workflow, account=data.requester, entry=data.direct_entry, inputs=valid_inputs(data)
    )

    assert result.errors
    assert [error.message for error in result.errors] == ["Services in direct mode can't be requested yet at entry_id"]
    assert await NodeManager.query(db=db, schema=InfrahubKind.SERVICEREQUEST) == []
    assert workflow.calls == []
