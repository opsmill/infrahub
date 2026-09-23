from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Boolean, Field, InputField, InputObjectType, Mutation, ObjectType, String
from graphene.types.generic import GenericScalar

from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreServiceCatalogEntry, CoreServiceRequest
from infrahub.core.registry import registry
from infrahub.exceptions import ValidationError
from infrahub.graphql.context import apply_external_context
from infrahub.graphql.types.context import ContextInput
from infrahub.graphql.types.task import TaskInfo
from infrahub.service_portal.constants import ServiceCatalogEntryMode, ServiceRequestStatus
from infrahub.service_portal.models import ServiceRequestRun
from infrahub.service_portal.validation import (
    get_entry_mode,
    get_request_permission,
    get_target_schema,
    validate_request_inputs,
)
from infrahub.workflows.catalogue import SERVICE_REQUEST_RUN

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from ..initialization import GraphqlContext


class ServiceRequestSubmitInput(InputObjectType):
    entry_id = InputField(String, required=True, description="ID of the catalog entry of the requested service")
    inputs = InputField(
        GenericScalar,
        required=True,
        description="Form values keyed by field name, in the shape of the target kind's create input",
    )


class ServiceRequestInfo(ObjectType):
    id = Field(String, required=True, description="ID of the service request")


class ServiceRequestSubmit(Mutation):
    class Arguments:
        data = ServiceRequestSubmitInput(required=True)
        context = ContextInput(required=False)

    ok = Boolean()
    request = Field(ServiceRequestInfo, required=False)
    task = Field(TaskInfo, required=False)

    @classmethod
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: ServiceRequestSubmitInput,
        context: ContextInput | None = None,
    ) -> ServiceRequestSubmit:
        graphql_context: GraphqlContext = info.context
        db = graphql_context.db
        await apply_external_context(graphql_context=graphql_context, context_input=context)
        # The catalog is published on the default branch, whatever branch the request is sent on
        branch = registry.get_branch_from_registry()
        inputs: Any = data.inputs

        entry = await NodeManager.get_one(
            db=db, id=str(data.entry_id), kind=CoreServiceCatalogEntry, branch=branch, raise_on_error=True
        )
        if get_entry_mode(entry) != ServiceCatalogEntryMode.REVIEW:
            # STUB(Phase 7): direct mode
            raise ValidationError({"entry_id": "Services in direct mode can't be requested yet"})
        target_schema = get_target_schema(db=db, entry=entry, branch=branch)
        if target_schema is None:
            raise ValidationError({"entry_id": f"The service creates {entry.target_kind.value}, which isn't a node"})

        graphql_context.active_permissions.raise_for_permission(
            permission=get_request_permission(target_schema),
            message=f"You are not allowed to create {target_schema.kind} objects on a branch",
        )
        await validate_request_inputs(db=db, branch=branch, entry=entry, target_schema=target_schema, inputs=inputs)

        request = await Node.init(db=db, schema=CoreServiceRequest, branch=branch)
        await request.new(
            db=db,
            status=ServiceRequestStatus.SUBMITTED.value,
            inputs={"value": inputs},
            entry=entry,
            requester=graphql_context.active_account_session.account_id,
        )
        await request.save(db=db)

        workflow = await graphql_context.active_service.workflow.submit_workflow(
            workflow=SERVICE_REQUEST_RUN,
            context=graphql_context.get_context(),
            parameters={"model": ServiceRequestRun(request_id=request.id)},
        )
        request.task_id.value = str(workflow.id)
        await request.save(db=db)

        return cls(ok=True, request={"id": request.id}, task={"id": str(workflow.id)})
