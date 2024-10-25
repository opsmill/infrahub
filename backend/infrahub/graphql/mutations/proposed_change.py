from typing import TYPE_CHECKING, Any, Optional

from graphene import Boolean, InputObjectType, Mutation, String
from graphql import GraphQLResolveInfo

from infrahub.core.account import GlobalPermission
from infrahub.core.branch import Branch
from infrahub.core.constants import (
    CheckType,
    GlobalPermissions,
    InfrahubKind,
    PermissionDecision,
    ProposedChangeState,
    ValidatorConclusion,
)
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema import NodeSchema
from infrahub.database import InfrahubDatabase, retry_db_transaction
from infrahub.exceptions import BranchNotFoundError, ValidationError
from infrahub.graphql.mutations.main import InfrahubMutationMixin
from infrahub.graphql.types.enums import CheckType as GraphQLCheckType
from infrahub.message_bus import messages
from infrahub.workflows.catalogue import BRANCH_MERGE

from .main import InfrahubMutationOptions

if TYPE_CHECKING:
    from ..initialization import GraphqlContext


class InfrahubProposedChangeMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(cls, schema: NodeSchema = None, _meta=None, **options):  # pylint: disable=arguments-differ
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
        at: str,
        database: Optional[InfrahubDatabase] = None,
    ):
        context: GraphqlContext = info.context
        db: InfrahubDatabase = info.context.db

        async with db.start_transaction() as dbt:
            proposed_change, result = await super().mutate_create(
                info=info, data=data, branch=branch, at=at, database=dbt
            )
            destination_branch = proposed_change.destination_branch.value
            source_branch = await _get_source_branch(db=dbt, name=proposed_change.source_branch.value)
            if destination_branch == source_branch.name:
                raise ValidationError(input_value="The source and destination branch can't be the same")
            if destination_branch != "main":
                raise ValidationError(
                    input_value="Currently only the 'main' branch is supported as a destination for a proposed change"
                )

        if context.service:
            message_list = [
                messages.RequestProposedChangePipeline(
                    proposed_change=proposed_change.id,
                    source_branch=source_branch.name,
                    source_branch_sync_with_git=source_branch.sync_with_git,
                    destination_branch=destination_branch,
                ),
            ]

            for message in message_list:
                await context.service.send(message=message)

        return proposed_change, result

    @classmethod
    @retry_db_transaction(name="proposed_change_update")
    async def mutate_update(  # pylint: disable=too-many-branches
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        at: str,
        database: Optional[InfrahubDatabase] = None,
        node: Optional[Node] = None,
    ):
        context: GraphqlContext = info.context

        has_merge_permission = False
        if context.account_session:
            for permission_backend in registry.permission_backends:
                if has_merge_permission := await permission_backend.has_permission(
                    db=context.db,
                    account_id=context.active_account_session.account_id,
                    permission=GlobalPermission(
                        action=GlobalPermissions.MERGE_PROPOSED_CHANGE.value,
                        decision=PermissionDecision.ALLOW_ALL.value,
                    ),
                    branch=branch,
                ):
                    break
        else:
            has_merge_permission = True

        obj = await NodeManager.get_one_by_id_or_default_filter(
            db=context.db,
            kind=cls._meta.schema.kind,
            id=data.get("id"),
            branch=branch,
            at=at,
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
        if updated_state == ProposedChangeState.MERGED and not has_merge_permission:
            raise ValidationError("You do not have the permission to merge proposed changes")

        async with context.db.start_transaction() as dbt:
            proposed_change, result = await super().mutate_update(
                info=info, data=data, branch=branch, at=at, database=dbt, node=obj
            )

            if updated_state == ProposedChangeState.MERGED:
                conflict_resolution: dict[str, bool] = {}
                source_branch = await Branch.get_by_name(db=dbt, name=proposed_change.source_branch.value)
                validations = await proposed_change.validations.get_peers(db=dbt)
                for validation in validations.values():
                    validator_kind = validation.get_kind()
                    if (
                        validator_kind != InfrahubKind.DATAVALIDATOR
                        and validation.conclusion.value.value != ValidatorConclusion.SUCCESS.value
                    ):
                        # Ignoring Data integrity checks as they are handled again later
                        raise ValidationError("Unable to merge proposed change containing failing checks")
                    if validator_kind == InfrahubKind.DATAVALIDATOR:
                        data_checks = await validation.checks.get_peers(db=dbt)
                        for check in data_checks.values():
                            if check.conflicts.value and not check.keep_branch.value:
                                raise ValidationError(
                                    "Data conflicts found on branch and missing decisions about what branch to keep"
                                )
                            if check.conflicts.value:
                                keep_source_value = check.keep_branch.value.value == "source"
                                conflict_resolution[check.conflicts.value[0]["path"]] = keep_source_value

                await context.service.workflow.execute_workflow(
                    workflow=BRANCH_MERGE,
                    parameters={"branch": source_branch.name, "conflict_resolution": conflict_resolution},
                )

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
        root: dict,  # pylint: disable=unused-argument
        info: GraphQLResolveInfo,
        data: dict[str, Any],
    ) -> dict[str, bool]:
        context: GraphqlContext = info.context

        check_type = data.get("check_type") or CheckType.ALL

        identifier = data.get("id", "")
        proposed_change = await NodeManager.get_one_by_id_or_default_filter(
            id=identifier, kind=InfrahubKind.PROPOSEDCHANGE, db=context.db
        )
        state = ProposedChangeState(proposed_change.state.value.value)
        state.validate_state_check_run()

        destination_branch = proposed_change.destination_branch.value
        source_branch = await _get_source_branch(db=context.db, name=proposed_change.source_branch.value)

        message = messages.RequestProposedChangePipeline(
            proposed_change=proposed_change.id,
            source_branch=source_branch.name,
            source_branch_sync_with_git=source_branch.sync_with_git,
            destination_branch=destination_branch,
            check_type=check_type,
        )
        if context.service:
            await context.service.send(message=message)

        return {"ok": True}


async def _get_source_branch(db: InfrahubDatabase, name: str) -> Branch:
    try:
        return await Branch.get_by_name(name=name, db=db)
    except BranchNotFoundError:
        raise ValidationError(
            input_value="The specified source branch for this proposed change was not found."
        ) from None
