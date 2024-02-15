from typing import TYPE_CHECKING, Any, Dict, Optional

from graphene import Boolean, InputObjectType, Mutation, String
from graphql import GraphQLResolveInfo

from infrahub import config, lock
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import CheckType, InfrahubKind, ProposedChangeState, ValidatorConclusion
from infrahub.core.manager import NodeManager
from infrahub.core.merge import BranchMerger
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import BranchNotFound, ValidationError
from infrahub.graphql.mutations.main import InfrahubMutationMixin
from infrahub.graphql.types.enums import CheckType as GraphQLCheckType
from infrahub.log import get_log_data
from infrahub.message_bus import Meta, messages
from infrahub.services import services
from infrahub.worker import WORKER_IDENTITY

from .main import InfrahubMutationOptions

if TYPE_CHECKING:
    from .. import GraphqlContext


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
    async def mutate_create(
        cls,
        root: dict,
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
                root=root, info=info, data=data, branch=branch, at=at, database=dbt
            )
            destination_branch = proposed_change.destination_branch.value
            source_branch = await _get_source_branch(db=dbt, name=proposed_change.source_branch.value)
            if destination_branch == source_branch.name:
                raise ValidationError(input_value="The source and destination branch can't be the same")
            if destination_branch != "main":
                raise ValidationError(
                    input_value="Currently only the 'main' branch is supported as a destination for a proposed change"
                )

        message = messages.RequestProposedChangePipeline(
            proposed_change=proposed_change.id,
            source_branch=source_branch.name,
            source_branch_data_only=source_branch.is_data_only,
            destination_branch=destination_branch,
        )
        await context.rpc_client.send(message)

        return proposed_change, result

    @classmethod
    async def mutate_update(
        cls,
        root: dict,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        at: str,
        database: Optional[InfrahubDatabase] = None,
        node: Optional[Node] = None,
    ):
        context: GraphqlContext = info.context

        obj = await NodeManager.get_one_by_id_or_default_filter(
            db=context.db,
            schema_name=cls._meta.schema.kind,
            id=data.get("id"),
            branch=branch,
            at=at,
            include_owner=True,
            include_source=True,
        )
        state = ProposedChangeState(obj.state.value)
        updated_state = None
        if state_update := data.get("state", {}).get("value"):
            updated_state = ProposedChangeState(state_update)
            state.validate_state_transition(updated_state)

        async with context.db.start_transaction() as dbt:
            proposed_change, result = await super().mutate_update(
                root=root, info=info, data=data, branch=branch, at=at, database=dbt, node=obj
            )

            if updated_state == ProposedChangeState.MERGED:
                conflict_resolution: Dict[str, bool] = {}
                source_branch = await Branch.get_by_name(db=dbt, name=proposed_change.source_branch.value)
                validations = await proposed_change.validations.get_peers(db=dbt)
                for validation in validations.values():
                    validator_kind = validation.get_kind()
                    if (
                        validator_kind != InfrahubKind.DATAVALIDATOR
                        and validation.conclusion.value != ValidatorConclusion.SUCCESS.value
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
                                keep_source_value = check.keep_branch.value == "source"
                                conflict_resolution[check.conflicts.value[0]["path"]] = keep_source_value

                async with lock.registry.global_graph_lock():
                    merger = BranchMerger(branch=source_branch)
                    await merger.merge(rpc_client=context.rpc_client, db=dbt, conflict_resolution=conflict_resolution)

                    # Copy the schema from the origin branch and set the hash and the schema_changed_at value
                    origin_branch = await source_branch.get_origin_branch(db=dbt)
                    updated_schema = await registry.schema.load_schema_from_db(db=dbt, branch=origin_branch)
                    registry.schema.set_schema_branch(name=origin_branch.name, schema=updated_schema)
                    origin_branch.update_schema_hash()

                    await origin_branch.save(db=dbt)

                if config.SETTINGS.broker.enable and context.background:
                    log_data = get_log_data()
                    request_id = log_data.get("request_id", "")
                    message = messages.EventBranchMerge(
                        source_branch=source_branch.name,
                        target_branch=config.SETTINGS.main.default_branch,
                        meta=Meta(initiator_id=WORKER_IDENTITY, request_id=request_id),
                    )
                    context.background.add_task(services.send, message)

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
        data: Dict[str, Any],
    ) -> Dict[str, bool]:
        context: GraphqlContext = info.context

        check_type = data.get("check_type") or CheckType.ALL

        identifier = data.get("id", "")
        proposed_change = await NodeManager.get_one_by_id_or_default_filter(
            id=identifier, schema_name=InfrahubKind.PROPOSEDCHANGE, db=context.db
        )
        state = ProposedChangeState(proposed_change.state.value)
        state.validate_state_check_run()

        destination_branch = proposed_change.destination_branch.value
        source_branch = await _get_source_branch(db=context.db, name=proposed_change.source_branch.value)

        message = messages.RequestProposedChangePipeline(
            proposed_change=proposed_change.id,
            source_branch=source_branch.name,
            source_branch_data_only=source_branch.is_data_only,
            destination_branch=destination_branch,
            check_type=check_type,
        )
        await context.rpc_client.send(message)

        return {"ok": True}


async def _get_source_branch(db: InfrahubDatabase, name: str) -> Branch:
    try:
        return await Branch.get_by_name(name=name, db=db)
    except BranchNotFound:
        raise ValidationError(
            input_value="The specified source branch for this proposed change was not found."
        ) from None
