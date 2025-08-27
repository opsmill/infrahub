from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

from graphene import Boolean, Enum, Field, InputObjectType, List, Mutation, String
from graphql import GraphQLResolveInfo

from infrahub import lock
from infrahub.core.account import GlobalPermission
from infrahub.core.branch import Branch
from infrahub.core.constants import (
    CheckType,
    GlobalPermissions,
    InfrahubKind,
    PermissionDecision,
)
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreProposedChange
from infrahub.core.schema import NodeSchema
from infrahub.database import InfrahubDatabase, retry_db_transaction
from infrahub.events import (
    EventMeta,
    ProposedChangeApprovalRevokedEvent,
    ProposedChangeApprovedEvent,
    ProposedChangeRejectedEvent,
    ProposedChangeRejectionRevokedEvent,
)
from infrahub.exceptions import BranchNotFoundError, PermissionDeniedError, ValidationError
from infrahub.graphql.mutations.main import InfrahubMutationMixin
from infrahub.graphql.types.enums import CheckType as GraphQLCheckType
from infrahub.graphql.types.task import TaskInfo
from infrahub.lock import InfrahubLock, build_object_lock_name
from infrahub.proposed_change.approval_revoker import do_revoke_approvals_on_updated_pcs
from infrahub.proposed_change.constants import ProposedChangeApprovalDecision, ProposedChangeState
from infrahub.proposed_change.models import RequestProposedChangePipeline
from infrahub.workers.dependencies import get_event_service
from infrahub.workflows.catalogue import PROPOSED_CHANGE_MERGE, REQUEST_PROPOSED_CHANGE_PIPELINE

from .main import InfrahubMutationOptions

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.node import Node
    from infrahub.events.models import InfrahubEvent

    from ..initialization import GraphqlContext

ProposedChangeApprovalDecisionInput = Enum.from_enum(ProposedChangeApprovalDecision)


class InfrahubProposedChangeMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(
        cls, schema: NodeSchema, _meta: InfrahubMutationOptions | None = None, **options: dict[str, Any]
    ) -> None:
        # Make sure schema is a valid NodeSchema Node Class
        if not isinstance(schema, NodeSchema):
            raise ValueError(f"You need to pass a valid NodeSchema in '{cls.__name__}.Meta', received '{schema}'")

        if not _meta:
            _meta = InfrahubMutationOptions(cls)
        _meta.schema = schema

        super().__init_subclass_with_meta__(_meta=_meta, **options)

    @classmethod
    @retry_db_transaction(name="proposed_change_create")
    async def mutate_create(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        database: InfrahubDatabase | None = None,  # noqa: ARG003
        override_data: dict[str, Any] | None = None,
    ) -> tuple[Node, Self]:
        graphql_context: GraphqlContext = info.context

        override_data = {"created_by": {"id": graphql_context.active_account_session.account_id}}
        state = data.get("state", {}).get("value")
        if state and state != ProposedChangeState.OPEN.value:
            raise ValidationError(input_value="A proposed change has to be in the open state during creation")

        async with graphql_context.db.start_transaction() as dbt:
            proposed_change, result = await super().mutate_create(
                info=info, data=data, branch=branch, database=dbt, override_data=override_data
            )
            destination_branch = proposed_change.destination_branch.value
            source_branch = await _get_source_branch(db=dbt, name=proposed_change.source_branch.value)
            if destination_branch == source_branch.name:
                raise ValidationError(input_value="The source and destination branch can't be the same")
            if destination_branch != "main":
                raise ValidationError(
                    input_value="Currently only the 'main' branch is supported as a destination for a proposed change"
                )

        if graphql_context.service:
            request_proposed_change_model = RequestProposedChangePipeline(
                proposed_change=proposed_change.id,
                source_branch=source_branch.name,
                source_branch_sync_with_git=source_branch.sync_with_git,
                destination_branch=destination_branch,
            )

            await graphql_context.service.workflow.submit_workflow(
                workflow=REQUEST_PROPOSED_CHANGE_PIPELINE,
                parameters={"model": request_proposed_change_model},
                context=graphql_context.get_context(),
            )

        return proposed_change, result

    @classmethod
    async def mutate_update(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        database: InfrahubDatabase | None = None,  # noqa: ARG003
        node: Node | None = None,  # noqa: ARG003
    ) -> tuple[Node, Self]:
        graphql_context: GraphqlContext = info.context

        obj = await NodeManager.get_one_by_id_or_default_filter(
            db=graphql_context.db,
            kind=cls._meta.schema.kind,
            id=data.get("id"),
            branch=branch,
            include_owner=True,
            include_source=True,
        )
        state = ProposedChangeState(obj.state.value.value)
        state.validate_updatable()

        updated_state = None
        if state_update := data.get("state", {}).get("value"):
            updated_state = ProposedChangeState(state_update)
            state.validate_state_transition(updated_state)

        # Check if the draft state will change (defaults to current draft state)
        will_be_draft = data.get("is_draft", {}).get("value", obj.is_draft.value)

        # Check before starting a transaction, stopping in the middle of the transaction seems to break with memgraph
        if updated_state == ProposedChangeState.MERGED and graphql_context.account_session:
            try:
                graphql_context.active_permissions.raise_for_permission(
                    permission=GlobalPermission(
                        action=GlobalPermissions.MERGE_PROPOSED_CHANGE.value,
                        decision=PermissionDecision.ALLOW_ALL.value,
                    )
                )
            except PermissionDeniedError as exc:
                raise ValidationError(str(exc)) from exc

        if updated_state == ProposedChangeState.MERGED:
            if will_be_draft:
                raise ValidationError("A draft proposed change is not allowed to be merged")
            data["state"]["value"] = ProposedChangeState.MERGING.value

        proposed_change, result = await super().mutate_update(
            info=info, data=data, branch=branch, database=graphql_context.db, node=obj
        )

        if updated_state == ProposedChangeState.MERGED:
            await graphql_context.service.workflow.execute_workflow(
                workflow=PROPOSED_CHANGE_MERGE,
                context=graphql_context.get_context(),
                parameters={
                    "proposed_change_id": proposed_change.id,
                    "proposed_change_name": proposed_change.name.value,
                },
            )
            # When the PROPOSED_CHANGE_MERGE succeeds it will have correctly changed the state
            # from the overridden "merging" value, so here we change it back to reflect the
            # correct value for the event that will be generated.
            proposed_change.node_changelog.attributes["state"].value = ProposedChangeState.MERGED.value

        return proposed_change, result


class ProposedChangeRequestRunCheckInput(InputObjectType):
    id = String(required=True)
    check_type = GraphQLCheckType(required=False)


class ProposedChangeRequestRunCheck(Mutation):
    class Arguments:
        data = ProposedChangeRequestRunCheckInput(required=True)

    ok = Boolean()

    @classmethod
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: dict[str, Any],
    ) -> dict[str, bool]:
        graphql_context: GraphqlContext = info.context

        check_type = data.get("check_type") or CheckType.ALL

        identifier = data.get("id", "")
        proposed_change = await NodeManager.get_one_by_id_or_default_filter(
            id=identifier, kind=InfrahubKind.PROPOSEDCHANGE, db=graphql_context.db
        )
        state = ProposedChangeState(proposed_change.state.value.value)
        state.validate_state_check_run()

        destination_branch = proposed_change.destination_branch.value
        source_branch = await _get_source_branch(db=graphql_context.db, name=proposed_change.source_branch.value)

        request_proposed_change_model = RequestProposedChangePipeline(
            proposed_change=proposed_change.id,
            source_branch=source_branch.name,
            source_branch_sync_with_git=source_branch.sync_with_git,
            destination_branch=destination_branch,
            check_type=check_type,
        )
        if graphql_context.service:
            await graphql_context.service.workflow.submit_workflow(
                workflow=REQUEST_PROPOSED_CHANGE_PIPELINE,
                parameters={"model": request_proposed_change_model},
                context=graphql_context.get_context(),
            )

        return {"ok": True}


class ProposedChangeReviewInput(InputObjectType):
    id = String(required=True, description="The ID of the proposed change to review.")
    decision = ProposedChangeApprovalDecisionInput(
        required=True, description="The decision for the proposed change review."
    )


class ProposedChangeReview(Mutation):
    class Arguments:
        data = ProposedChangeReviewInput(required=True)

    ok = Boolean()

    @classmethod
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: ProposedChangeReviewInput,
    ) -> dict[str, bool]:
        """
        This mutation is used to approve or reject a proposed change.
        It can also be used to undo an approval or rejection.
        """

        graphql_context: GraphqlContext = info.context
        graphql_context.active_permissions.raise_for_permission(
            permission=GlobalPermission(
                action=GlobalPermissions.REVIEW_PROPOSED_CHANGE.value, decision=PermissionDecision.ALLOW_ALL.value
            )
        )
        pc_id = str(data.id)
        lock_name = build_object_lock_name(pc_id)
        async with InfrahubLock(name=lock_name, connection=lock.registry.connection):
            proposed_change = await NodeManager.get_one_by_id_or_default_filter(
                id=pc_id, kind=CoreProposedChange, db=graphql_context.db, prefetch_relationships=True
            )
            state = ProposedChangeState(proposed_change.state.value.value)
            state.validate_reviewable()

            created_by = await proposed_change.created_by.get_peer(db=graphql_context.db)
            if created_by and created_by.id == graphql_context.active_account_session.account_id:
                raise ValidationError(input_value="You cannot review your own proposed changes")

            current_user = await NodeManager.get_one_by_id_or_default_filter(
                id=graphql_context.active_account_session.account_id,
                kind=InfrahubKind.GENERICACCOUNT,
                db=graphql_context.db,
            )

            async with graphql_context.db.start_session() as db:
                event = await cls._handle_decision(
                    db=db,
                    decision=data.decision,
                    proposed_change=proposed_change,
                    current_user=current_user,
                    context=graphql_context,
                )
                await proposed_change.save(db=db)

                if event:
                    event_service = await get_event_service()
                    await event_service.send(event=event)

        return {"ok": True}

    @classmethod
    async def _handle_decision(
        cls,
        db: InfrahubDatabase,
        decision: ProposedChangeApprovalDecision,
        proposed_change: CoreProposedChange,
        current_user: Node,
        context: GraphqlContext,
    ) -> InfrahubEvent | None:
        """Modify approved_by and rejected_by relationships of the prpoposed change based on the decision."""

        approved_by = await proposed_change.approved_by.get_peers(db=db)
        rejected_by = await proposed_change.rejected_by.get_peers(db=db)
        approved_by_ids = [node.id for _, node in approved_by.items()]
        rejected_by_ids = [node.id for _, node in rejected_by.items()]
        event: InfrahubEvent | None = None
        event_meta = EventMeta.from_context(context=context.get_context())

        match decision:
            case ProposedChangeApprovalDecision.APPROVE:
                if current_user.id in approved_by_ids:
                    raise ValidationError(input_value="You have already approved this proposed change")
                await proposed_change.approved_by.add(db=db, data=current_user)
                if current_user.id in rejected_by_ids:
                    await proposed_change.rejected_by.remove_locally(db=db, peer_id=current_user.id)

                event = ProposedChangeApprovedEvent(
                    proposed_change_id=proposed_change.id,
                    proposed_change_name=proposed_change.name.value,
                    proposed_change_state=proposed_change.state.value,
                    reviewer_account_id=current_user.id,
                    reviewer_account_name=current_user.name.value,
                    reviewer_decision=decision.value,
                    meta=event_meta,
                )

            case ProposedChangeApprovalDecision.CANCEL_APPROVE:
                if current_user.id not in approved_by_ids:
                    raise ValidationError(
                        input_value="You did not approve this proposed change yet, it can't be un-approved"
                    )
                await proposed_change.approved_by.remove_locally(db=db, peer_id=current_user.id)

                event = ProposedChangeApprovalRevokedEvent(
                    proposed_change_id=proposed_change.id,
                    proposed_change_name=proposed_change.name.value,
                    proposed_change_state=proposed_change.state.value,
                    reviewer_account_id=current_user.id,
                    reviewer_account_name=current_user.name.value,
                    reviewer_former_decision=ProposedChangeApprovalDecision.APPROVE.value,
                    meta=event_meta,
                )

            case ProposedChangeApprovalDecision.REJECT:
                if current_user.id in rejected_by_ids:
                    raise ValidationError(input_value="You have already rejected this proposed change")
                await proposed_change.rejected_by.add(db=db, data=current_user)
                if current_user.id in approved_by_ids:
                    await proposed_change.approved_by.remove_locally(db=db, peer_id=current_user.id)

                event = ProposedChangeRejectedEvent(
                    proposed_change_id=proposed_change.id,
                    proposed_change_name=proposed_change.name.value,
                    proposed_change_state=proposed_change.state.value,
                    reviewer_account_id=current_user.id,
                    reviewer_account_name=current_user.name.value,
                    reviewer_decision=decision.value,
                    meta=event_meta,
                )

            case ProposedChangeApprovalDecision.CANCEL_REJECT:
                if current_user.id not in rejected_by_ids:
                    raise ValidationError(
                        input_value="You did not reject this proposed change yet, it can't be un-rejected"
                    )
                await proposed_change.rejected_by.remove_locally(db=db, peer_id=current_user.id)

                event = ProposedChangeRejectionRevokedEvent(
                    proposed_change_id=proposed_change.id,
                    proposed_change_name=proposed_change.name.value,
                    proposed_change_state=proposed_change.state.value,
                    reviewer_account_id=current_user.id,
                    reviewer_account_name=current_user.name.value,
                    reviewer_former_decision=ProposedChangeApprovalDecision.REJECT.value,
                    meta=event_meta,
                )

            case _:
                raise ValidationError(input_value=f"Invalid decision {decision}")

        return event


class ProposedChangeMergeInput(InputObjectType):
    id = String(required=True)


class ProposedChangeMerge(Mutation):
    class Arguments:
        data = ProposedChangeMergeInput(required=True)
        wait_until_completion = Boolean(required=False)

    ok = Boolean()
    task = Field(TaskInfo, required=False)

    @classmethod
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: dict[str, Any],
        wait_until_completion: bool = True,
    ) -> dict[str, bool]:
        graphql_context: GraphqlContext = info.context
        task: dict | None = None

        identifier = data.get("id", "")
        proposed_change = await NodeManager.get_one(
            id=identifier, kind=InfrahubKind.PROPOSEDCHANGE, db=graphql_context.db, raise_on_error=True
        )
        state = ProposedChangeState(proposed_change.state.value.value)
        if state != ProposedChangeState.OPEN:
            raise ValidationError("Only proposed change in OPEN state can be merged")

        async with graphql_context.db.start_session() as db:
            proposed_change.state.value = ProposedChangeState.MERGING.value
            await proposed_change.save(db=db)

        if wait_until_completion:
            await graphql_context.service.workflow.execute_workflow(
                workflow=PROPOSED_CHANGE_MERGE,
                context=graphql_context.get_context(),
                parameters={
                    "proposed_change_id": proposed_change.id,
                    "proposed_change_name": proposed_change.name.value,
                },
            )
        else:
            workflow = await graphql_context.service.workflow.submit_workflow(
                workflow=PROPOSED_CHANGE_MERGE,
                context=graphql_context.get_context(),
                parameters={
                    "proposed_change_id": proposed_change.id,
                    "proposed_change_name": proposed_change.name.value,
                },
            )
            task = {"id": workflow.id}

        return cls(ok=True, task=task)


class ProposedChangeCheckForApprovalRevokeInput(InputObjectType):
    ids = Field(List(of_type=String, required=True), required=False)


class ProposedChangeCheckForApprovalRevoke(Mutation):
    class Arguments:
        data = ProposedChangeCheckForApprovalRevokeInput(required=True)

    ok = Boolean()

    @classmethod
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: dict[str, Any],
    ) -> dict[str, bool]:
        db = info.context.db
        ids: list[str] | None
        try:
            ids = data["ids"]
        except KeyError:
            ids = None

        await do_revoke_approvals_on_updated_pcs(db=db, proposed_changes_ids=ids)
        return cls(ok=True)


async def _get_source_branch(db: InfrahubDatabase, name: str) -> Branch:
    try:
        return await Branch.get_by_name(name=name, db=db)
    except BranchNotFoundError:
        raise ValidationError(
            input_value="The specified source branch for this proposed change was not found."
        ) from None
