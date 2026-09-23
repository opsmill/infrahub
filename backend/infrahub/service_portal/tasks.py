from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub_sdk.protocols import CoreGeneratorDefinition, CoreGeneratorInstance, CoreProposedChange
from prefect import flow, get_run_logger

from infrahub.auth.session import AccountSession
from infrahub.context import InfrahubContext
from infrahub.core.constants import GeneratorInstanceStatus, InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreServiceRequest
from infrahub.core.registry import registry
from infrahub.events import EventMeta
from infrahub.events.node_action import NodeUpdatedEvent
from infrahub.exceptions import BranchNotFoundError
from infrahub.generators.models import RequestGeneratorDefinitionRun, build_generator_definition
from infrahub.graphql.mutations.models import BranchCreateModel
from infrahub.proposed_change.constants import ProposedChangeState
from infrahub.service_portal.constants import ServiceCatalogEntryMode, ServiceRequestStatus
from infrahub.service_portal.models import ServiceRequestRun  # noqa: TC001 needed for prefect flow
from infrahub.service_portal.validation import get_entry_mode
from infrahub.workers.dependencies import get_client, get_database, get_event_service, get_workflow
from infrahub.workflows.catalogue import BRANCH_CREATE, REQUEST_GENERATOR_DEFINITION_RUN
from infrahub.workflows.utils import add_tags

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient

    from infrahub.core.branch import Branch

ADD_TO_GROUP = """
mutation AddToGroup($group: String!, $member: String!, $context: ContextInput) {
    RelationshipAdd(data: {id: $group, name: "members", nodes: [{id: $member}]}, context: $context) { ok }
}
"""

WORKER_ACCOUNT = "query { AccountProfile { id } }"


def _context_payload(client: InfrahubClient) -> dict[str, Any] | None:
    if not client.request_context:
        return None
    return client.request_context.model_dump(exclude_none=True, exclude={"priority"})


def request_branch_name(request_id: str) -> str:
    return f"service-request-{request_id.replace('-', '')[:8]}"


class ServiceRequestRecorder:
    """Writes the backend-owned fields of a service request and announces each change.

    These fields are read-only in the generated API, so they are saved directly on the node; the
    node update event is emitted here so webhooks and event rules still see status changes.
    """

    def __init__(self, request_id: str, context: InfrahubContext) -> None:
        self.request_id = request_id
        self.context = context

    async def record(self, on_branch: Branch | None = None, **fields: Any) -> None:
        # `service` is branch-aware and only resolves on the request branch; every other field is agnostic.
        branch = on_branch or registry.get_branch_from_registry()
        database = await get_database()
        async with database.start_session() as db:
            node = await NodeManager.get_one(
                db=db, id=self.request_id, kind=InfrahubKind.SERVICEREQUEST, branch=branch, raise_on_error=True
            )
            for name, value in fields.items():
                if name in node.get_schema().relationship_names:
                    await getattr(node, name).update(db=db, data=value)
                else:
                    getattr(node, name).value = value
            await node.save(db=db, user_id=self.context.account.account_id, fields=list(fields))

        if not node.node_changelog.has_changes:
            return
        event_service = await get_event_service()
        await event_service.send(
            event=NodeUpdatedEvent(
                kind=InfrahubKind.SERVICEREQUEST,
                node_id=self.request_id,
                changelog=node.node_changelog,
                fields=sorted(node.node_changelog.updated_fields),
                meta=EventMeta.from_context(context=self.context.to_event_context(), branch=branch),
            )
        )


async def _ensure_branch(name: str, context: InfrahubContext) -> Branch:
    database = await get_database()
    async with database.start_session() as db:
        try:
            return await registry.get_branch(db=db, branch=name)
        except BranchNotFoundError:
            pass

    await get_workflow().execute_workflow(
        workflow=BRANCH_CREATE,
        context=context,
        parameters={"model": BranchCreateModel(name=name, sync_with_git=False)},
    )
    async with database.start_session() as db:
        return await registry.get_branch(db=db, branch=name)


async def _write_service(
    client: InfrahubClient,
    branch: str,
    kind: str,
    inputs: dict[str, Any],
    service_id: str | None,
    template_id: str | None,
) -> str:
    """Create the service object, or update it when a previous run already created it."""
    if service_id:
        mutation, data = f"{kind}Update", {**inputs, "id": service_id}
    else:
        mutation, data = f"{kind}Create", dict(inputs)
        if template_id:
            data["object_template"] = {"id": template_id}

    query = f"""
    mutation Write($data: {mutation}Input!, $context: ContextInput) {{
        {mutation}(data: $data, context: $context) {{ ok object {{ id }} }}
    }}
    """
    response = await client.execute_graphql(
        query=query,
        variables={"data": data, "context": _context_payload(client)},
        branch_name=branch,
        tracker="service-request-write",
    )
    return response[mutation]["object"]["id"]


async def _add_to_target_group(client: InfrahubClient, group_id: str, member_id: str, branch: str) -> None:
    await client.execute_graphql(
        query=ADD_TO_GROUP,
        variables={"group": group_id, "member": member_id, "context": _context_payload(client)},
        branch_name=branch,
        tracker="service-request-add-to-group",
    )


async def _run_generator(
    worker_client: InfrahubClient,
    definition: CoreGeneratorDefinition,
    service_id: str,
    branch: str,
    context: InfrahubContext,
) -> None:
    """Run one generator definition for exactly the service object and wait for its result.

    Raises:
        RuntimeError: When the generator didn't run for the object or its instance ended in error.

    """
    name = definition.name.value
    try:
        await get_workflow().execute_workflow(
            workflow=REQUEST_GENERATOR_DEFINITION_RUN,
            context=context,
            parameters={
                "model": RequestGeneratorDefinitionRun(
                    generator_definition=build_generator_definition(definition),
                    branch=branch,
                    target_members=[service_id],
                )
            },
        )
    except Exception as exc:
        raise RuntimeError(f"Generator {name} failed") from exc
    instances = await worker_client.filters(
        kind=CoreGeneratorInstance, definition__ids=[definition.id], object__ids=[service_id], branch=branch
    )
    if not instances:
        raise RuntimeError(f"Generator {name} did not run for the service object")
    if any(instance.status.value == GeneratorInstanceStatus.ERROR.value for instance in instances):
        raise RuntimeError(f"Generator {name} failed")


@flow(name="service-request-run", flow_run_name="Fulfil service request {model.request_id}")
async def run_service_request(model: ServiceRequestRun, context: InfrahubContext) -> None:
    # STUB(Phase 2): an exception fails the task and leaves the request in `generating`.
    log = get_run_logger()
    await add_tags(nodes=[model.request_id])

    database = await get_database()
    async with database.start_session() as db:
        request = await NodeManager.get_one(db=db, id=model.request_id, kind=CoreServiceRequest, raise_on_error=True)
        entry = await request.entry.get_peer(db=db, raise_on_error=True)
        requester = await request.requester.get_peer(db=db, raise_on_error=True)
        template = await entry.template.get_peer(db=db)
        entry_name = entry.name.value
        target_kind = entry.target_kind.value
        generators: list[str] = entry.generators.value or []
        inputs = request.inputs.value if isinstance(request.inputs.value, dict) else {}

    if get_entry_mode(entry) != ServiceCatalogEntryMode.REVIEW:
        raise ValueError(f"Service catalog entry {entry_name!r} isn't in review mode")  # STUB(Phase 7): direct mode

    # Three accounts stay apart: the caller only authorized the submission, the requester owns every
    # write that belongs to the request, and the worker runs the generators and writes request state.
    worker_client = get_client().clone()
    worker_account_id = (await worker_client.execute_graphql(query=WORKER_ACCOUNT))["AccountProfile"]["id"]
    worker_context = InfrahubContext(
        branch=context.branch, account=AccountSession(account_id=worker_account_id, auth_type=context.account.auth_type)
    )
    requester_context = InfrahubContext(
        branch=context.branch, account=AccountSession(account_id=requester.id, auth_type=context.account.auth_type)
    )
    requester_client = get_client().clone()
    requester_client.request_context = requester_context.to_request_context()
    recorder = ServiceRequestRecorder(request_id=model.request_id, context=worker_context)

    branch_name = request_branch_name(model.request_id)
    await recorder.record(
        status=ServiceRequestStatus.GENERATING.value, message="Preparing a workspace for your request"
    )
    branch = await _ensure_branch(name=branch_name, context=requester_context)
    await recorder.record(branch=branch_name)

    async with database.start_session() as db:
        on_branch = await NodeManager.get_one(
            db=db, id=model.request_id, kind=CoreServiceRequest, branch=branch, raise_on_error=True
        )
        existing_service = await on_branch.service.get_peer(db=db)

    await recorder.record(message=f"Creating your {entry_name}")
    service_id = await _write_service(
        client=requester_client,
        branch=branch_name,
        kind=target_kind,
        inputs=inputs,
        service_id=existing_service.id if existing_service else None,
        template_id=template.id if template else None,
    )
    await recorder.record(on_branch=branch, service=service_id)

    for index, generator_name in enumerate(generators, start=1):
        await recorder.record(message=f"Configuring your service: step {index} of {len(generators)}")
        definition = await worker_client.get(
            kind=CoreGeneratorDefinition,
            name__value=generator_name,
            branch=branch_name,
            prefetch_relationships=True,
            populate_store=True,
        )
        if not definition.targets.id:
            raise RuntimeError(f"Generator {generator_name} has no target group")
        await _add_to_target_group(
            client=requester_client, group_id=definition.targets.id, member_id=service_id, branch=branch_name
        )
        await _run_generator(
            worker_client=worker_client,
            definition=definition,
            service_id=service_id,
            branch=branch_name,
            context=worker_context,
        )

    await recorder.record(message="Sending the change to engineers for review")
    open_changes = await requester_client.filters(
        kind=CoreProposedChange,
        source_branch__value=branch_name,
        state__value=ProposedChangeState.OPEN.value,
    )
    if open_changes:
        proposed_change = open_changes[0]
    else:
        proposed_change = await requester_client.create(
            kind=CoreProposedChange,
            name=f"{entry_name} (request {branch_name.removeprefix('service-request-')})",
            source_branch=branch_name,
            destination_branch=registry.default_branch,
        )
        await proposed_change.save()

    await recorder.record(
        proposed_change=proposed_change.id,
        status=ServiceRequestStatus.IN_REVIEW.value,
        message="Waiting for an engineer to review the change",
    )
    log.info(f"Service request {model.request_id} is in review with proposed change {proposed_change.id}")
