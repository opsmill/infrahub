from typing import TYPE_CHECKING, Any, Self

from graphene import Boolean, Field, InputObjectType, Mutation, String
from graphql import GraphQLResolveInfo

from infrahub.core.account import GlobalPermission
from infrahub.core.branch import Branch
from infrahub.core.constants import (
    CheckType,
    GlobalPermissions,
    InfrahubKind,
    PermissionDecision,
)
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.database import InfrahubDatabase, retry_db_transaction
from infrahub.exceptions import BranchNotFoundError, PermissionDeniedError, ValidationError
from infrahub.graphql.mutations.main import InfrahubMutationMixin
from infrahub.graphql.types.enums import CheckType as GraphQLCheckType
from infrahub.message_bus import messages
from infrahub.proposed_change.constants import ProposedChangeState
from infrahub.workflows.catalogue import PROPOSED_CHANGE_MERGE

from ..types.task import TaskInfo
from .main import InfrahubMutationOptions

if TYPE_CHECKING:
    from ..initialization import GraphqlContext


class InfrahubProposedChangeMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(cls, schema: NodeSchema = None, _meta=None, **options) -> None:
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
    ) -> tuple[Node, Self]:
        graphql_context: GraphqlContext = info.context

        async with graphql_context.db.start_transaction() as dbt:
            proposed_change, result = await super().mutate_create(info=info, data=data, branch=branch, database=dbt)
            destination_branch = proposed_change.destination_branch.value
            source_branch = await _get_source_branch(db=dbt, name=proposed_change.source_branch.value)
            if destination_branch == source_branch.name:
                raise ValidationError(input_value="The source and destination branch can't be the same")
            if destination_branch != "main":
                raise ValidationError(
                    input_value="Currently only the 'main' branch is supported as a destination for a proposed change"
                )

        if graphql_context.service:
            message_list = [
                messages.RequestProposedChangePipeline(
                    proposed_change=proposed_change.id,
                    source_branch=source_branch.name,
                    source_branch_sync_with_git=source_branch.sync_with_git,
                    destination_branch=destination_branch,
                    context=graphql_context.get_context(),
                ),
            ]

            for message in message_list:
                await graphql_context.service.message_bus.send(message=message)

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
        state.validate_editability()

        updated_state = None
        if state_update := data.get("state", {}).get("value"):
            updated_state = ProposedChangeState(state_update)
            state.validate_state_transition(updated_state)

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

        message = messages.RequestProposedChangePipeline(
            proposed_change=proposed_change.id,
            source_branch=source_branch.name,
            source_branch_sync_with_git=source_branch.sync_with_git,
            destination_branch=destination_branch,
            check_type=check_type,
            context=graphql_context.get_context(),
        )
        if graphql_context.service:
            await graphql_context.service.message_bus.send(message=message)

        return {"ok": True}


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
            proposed_change.save(db=db)

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


async def _get_source_branch(db: InfrahubDatabase, name: str) -> Branch:
    try:
        return await Branch.get_by_name(name=name, db=db)
    except BranchNotFoundError:
        raise ValidationError(
            input_value="The specified source branch for this proposed change was not found."
        ) from None
