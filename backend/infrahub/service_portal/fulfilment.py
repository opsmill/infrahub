from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub_sdk.protocols import CoreGeneratorDefinition, CoreGeneratorInstance, CoreProposedChange

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
from infrahub.service_portal.validation import get_entry_mode
from infrahub.workflows.catalogue import BRANCH_CREATE, REQUEST_GENERATOR_DEFINITION_RUN

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.services.adapters.event import InfrahubEventService
    from infrahub.services.adapters.workflow import InfrahubWorkflow

ADD_TO_GROUP = """
mutation AddToGroup($group: String!, $member: String!, $context: ContextInput) {
    RelationshipAdd(data: {id: $group, name: "members", nodes: [{id: $member}]}, context: $context) { ok }
}
"""


def request_branch_name(request_id: str) -> str:
    return f"service-request-{request_id.replace('-', '')[:8]}"


class ServiceRequestStateWriter:
    """Writes the backend-owned fields of a service request and announces each change.

    These fields are read-only in the generated API, so they are saved directly on the node; the
    node update event is emitted here so webhooks and event rules still see status changes.
    """

    def __init__(
        self, database: InfrahubDatabase, event_service: InfrahubEventService, context: InfrahubContext
    ) -> None:
        self.database = database
        self.event_service = event_service
        self.context = context

    async def update(
        self,
        request_id: str,
        *,
        status: ServiceRequestStatus | None = None,
        message: str | None = None,
        branch_name: str | None = None,
        proposed_change_id: str | None = None,
    ) -> None:
        """Set the given agnostic fields; a field left as None keeps its current value."""
        attributes = {"status": status.value if status else None, "message": message, "branch": branch_name}
        await self._save(
            request_id=request_id,
            branch=registry.get_branch_from_registry(),
            attributes={name: value for name, value in attributes.items() if value is not None},
            relationships={"proposed_change": proposed_change_id} if proposed_change_id else {},
        )

    async def set_service(self, request_id: str, service_id: str, branch: Branch) -> None:
        # `service` is branch-aware and only resolves on the request branch.
        await self._save(request_id=request_id, branch=branch, attributes={}, relationships={"service": service_id})

    async def _save(
        self, request_id: str, branch: Branch, attributes: dict[str, str], relationships: dict[str, str]
    ) -> None:
        async with self.database.start_session() as db:
            node = await NodeManager.get_one(
                db=db, id=request_id, kind=InfrahubKind.SERVICEREQUEST, branch=branch, raise_on_error=True
            )
            for name, value in attributes.items():
                node.get_attribute(name).value = value
            for name, peer_id in relationships.items():
                await node.get_relationship(name).update(db=db, data=peer_id)
            await node.save(db=db, user_id=self.context.account.account_id, fields=[*attributes, *relationships])

        if not node.node_changelog.has_changes:
            return
        await self.event_service.send(
            event=NodeUpdatedEvent(
                kind=InfrahubKind.SERVICEREQUEST,
                node_id=request_id,
                changelog=node.node_changelog,
                fields=sorted(node.node_changelog.updated_fields),
                meta=EventMeta.from_context(context=self.context.to_event_context(), branch=branch),
            )
        )


class ServiceRequestRunner:
    """Fulfils a review-mode service request up to an open proposed change.

    Three accounts stay apart: the submit caller only authorized the submission, the requester owns every
    write that belongs to the request (branch, service object, group joins, proposed change), and the worker
    runs the generators and writes request state. Requester writes go through the worker's client with the
    requester as the request context, so permissions stay the worker's while attribution is the requester's.
    """

    def __init__(
        self,
        database: InfrahubDatabase,
        workflow: InfrahubWorkflow,
        client: InfrahubClient,
        state: ServiceRequestStateWriter,
        worker_context: InfrahubContext,
    ) -> None:
        self.database = database
        self.workflow = workflow
        self.client = client
        self.state = state
        self.worker_context = worker_context

    async def run(self, request_id: str, context: InfrahubContext) -> str:
        """Fulfil the request and return the id of its open proposed change.

        Running it again for the same request reuses the branch, the service object and the open proposed change.

        Raises:
            ValueError: When the request's catalog entry isn't in review mode.
            RuntimeError: When a generator has no target group, didn't run for the service or failed.

        """
        async with self.database.start_session() as db:
            request = await NodeManager.get_one(db=db, id=request_id, kind=CoreServiceRequest, raise_on_error=True)
            entry = await request.entry.get_peer(db=db, raise_on_error=True)
            requester = await request.requester.get_peer(db=db, raise_on_error=True)
            template = await entry.template.get_peer(db=db)
            entry_name = entry.name.value
            target_kind = entry.target_kind.value
            generators: list[str] = entry.generators.value or []
            inputs = request.inputs.value if isinstance(request.inputs.value, dict) else {}

        if get_entry_mode(entry) != ServiceCatalogEntryMode.REVIEW:
            raise ValueError(f"Service catalog entry {entry_name!r} isn't in review mode")  # STUB(Phase 7): direct mode

        requester_context = InfrahubContext(
            branch=context.branch, account=AccountSession(account_id=requester.id, auth_type=context.account.auth_type)
        )
        branch_name = request_branch_name(request_id)

        await self.state.update(
            request_id, status=ServiceRequestStatus.GENERATING, message="Preparing a workspace for your request"
        )
        branch = await self._ensure_branch(name=branch_name, context=requester_context)
        await self.state.update(request_id, branch_name=branch_name)

        async with self.database.start_session() as db:
            on_branch = await NodeManager.get_one(
                db=db, id=request_id, kind=CoreServiceRequest, branch=branch, raise_on_error=True
            )
            existing_service = await on_branch.service.get_peer(db=db)

        await self.state.update(request_id, message=f"Creating your {entry_name}")
        if existing_service:
            service_id = await self._mutate(
                mutation=f"{target_kind}Update",
                data={**inputs, "id": existing_service.id},
                branch=branch_name,
                context=requester_context,
            )
        else:
            data = dict(inputs)
            if template:
                data["object_template"] = {"id": template.id}
            service_id = await self._mutate(
                mutation=f"{target_kind}Create", data=data, branch=branch_name, context=requester_context
            )
        await self.state.set_service(request_id, service_id=service_id, branch=branch)

        for index, generator_name in enumerate(generators, start=1):
            await self.state.update(request_id, message=f"Configuring your service: step {index} of {len(generators)}")
            definition = await self.client.get(
                kind=CoreGeneratorDefinition,
                name__value=generator_name,
                branch=branch_name,
                prefetch_relationships=True,
                populate_store=True,
            )
            if not definition.targets.id:
                raise RuntimeError(f"Generator {generator_name} has no target group")
            await self._add_to_target_group(
                group_id=definition.targets.id, member_id=service_id, branch=branch_name, context=requester_context
            )
            await self._run_generator(definition=definition, service_id=service_id, branch=branch_name)

        await self.state.update(request_id, message="Sending the change to engineers for review")
        proposed_change_id = await self._open_proposed_change(
            name=f"{entry_name} (request {branch_name.removeprefix('service-request-')})",
            branch=branch_name,
            context=requester_context,
        )
        await self.state.update(
            request_id,
            proposed_change_id=proposed_change_id,
            status=ServiceRequestStatus.IN_REVIEW,
            message="Waiting for an engineer to review the change",
        )
        return proposed_change_id

    async def _ensure_branch(self, name: str, context: InfrahubContext) -> Branch:
        async with self.database.start_session() as db:
            try:
                return await registry.get_branch(db=db, branch=name)
            except BranchNotFoundError:
                pass

        await self.workflow.execute_workflow(
            workflow=BRANCH_CREATE,
            context=context,
            parameters={"model": BranchCreateModel(name=name, sync_with_git=False)},
        )
        async with self.database.start_session() as db:
            return await registry.get_branch(db=db, branch=name)

    async def _mutate(self, mutation: str, data: dict[str, Any], branch: str, context: InfrahubContext) -> str:
        """Run a generated create/update mutation under `context` and return the object id."""
        query = f"""
        mutation Write($data: {mutation}Input!, $context: ContextInput) {{
            {mutation}(data: $data, context: $context) {{ ok object {{ id }} }}
        }}
        """
        response = await self.client.execute_graphql(
            query=query,
            variables={"data": data, "context": _context_variable(context)},
            branch_name=branch,
            tracker="service-request-write",
        )
        return response[mutation]["object"]["id"]

    async def _add_to_target_group(self, group_id: str, member_id: str, branch: str, context: InfrahubContext) -> None:
        await self.client.execute_graphql(
            query=ADD_TO_GROUP,
            variables={"group": group_id, "member": member_id, "context": _context_variable(context)},
            branch_name=branch,
            tracker="service-request-add-to-group",
        )

    async def _run_generator(self, definition: CoreGeneratorDefinition, service_id: str, branch: str) -> None:
        """Run one generator definition for exactly the service object and wait for its result.

        Raises:
            RuntimeError: When the generator didn't run for the object or its instance ended in error.

        """
        name = definition.name.value
        try:
            await self.workflow.execute_workflow(
                workflow=REQUEST_GENERATOR_DEFINITION_RUN,
                context=self.worker_context,
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
        instances = await self.client.filters(
            kind=CoreGeneratorInstance, definition__ids=[definition.id], object__ids=[service_id], branch=branch
        )
        if not instances:
            raise RuntimeError(f"Generator {name} did not run for the service object")
        if any(instance.status.value == GeneratorInstanceStatus.ERROR.value for instance in instances):
            raise RuntimeError(f"Generator {name} failed")

    async def _open_proposed_change(self, name: str, branch: str, context: InfrahubContext) -> str:
        """Open a proposed change from `branch` to the default branch, reusing one that is already open."""
        open_changes = await self.client.filters(
            kind=CoreProposedChange, source_branch__value=branch, state__value=ProposedChangeState.OPEN.value
        )
        if open_changes:
            return open_changes[0].id
        return await self._mutate(
            mutation="CoreProposedChangeCreate",
            data={
                "name": {"value": name},
                "source_branch": {"value": branch},
                "destination_branch": {"value": registry.default_branch},
            },
            branch=registry.default_branch,
            context=context,
        )


def _context_variable(context: InfrahubContext) -> dict[str, Any]:
    return context.to_request_context().model_dump(exclude_none=True, exclude={"priority"})
