from typing import TYPE_CHECKING, Any, Dict, Optional

from graphene import Boolean, Enum, InputObjectType, Mutation, String
from graphql import GraphQLResolveInfo

from infrahub import config, lock
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import ProposedChangeState, ValidatorConclusion
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError
from infrahub.graphql.mutations.main import InfrahubMutationMixin
from infrahub.log import get_log_data
from infrahub.message_bus import Meta, messages
from infrahub.services import services
from infrahub.worker import WORKER_IDENTITY

from .main import InfrahubMutationOptions

if TYPE_CHECKING:
    from infrahub.message_bus.rpc import InfrahubRpcClient


class CheckType(Enum):
    ARTIFACT = "artifact"
    DATA = "data"
    REPOSITORY = "repository"
    SCHEMA = "schema"
    USER = "user"
    ALL = "all"


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
    ):
        rpc_client: InfrahubRpcClient = info.context.get("infrahub_rpc_client")

        proposed_change, result = await super().mutate_create(root=root, info=info, data=data, branch=branch, at=at)

        events = [
            messages.RequestProposedChangeRefreshArtifacts(proposed_change=proposed_change.id),
            messages.RequestProposedChangeDataIntegrity(proposed_change=proposed_change.id),
            messages.RequestProposedChangeRepositoryChecks(proposed_change=proposed_change.id),
            messages.RequestProposedChangeSchemaIntegrity(proposed_change=proposed_change.id),
        ]
        for event in events:
            await rpc_client.send(event)

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
        db: InfrahubDatabase = info.context.get("infrahub_database")
        rpc_client: InfrahubRpcClient = info.context.get("infrahub_rpc_client")

        obj = await NodeManager.get_one_by_id_or_default_filter(
            db=db,
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

        async with db.start_transaction() as dbt:
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
                        validator_kind != "CoreDataValidator"
                        and validation.conclusion.value != ValidatorConclusion.SUCCESS.value
                    ):
                        # Ignoring Data integrity checks as they are handled again later
                        raise ValidationError("Unable to merge proposed change containing failing checks")
                    if validator_kind == "CoreDataValidator":
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
                    await source_branch.merge(rpc_client=rpc_client, db=dbt, conflict_resolution=conflict_resolution)

                    # Copy the schema from the origin branch and set the hash and the schema_changed_at value
                    origin_branch = await source_branch.get_origin_branch(db=dbt)
                    updated_schema = await registry.schema.load_schema_from_db(db=dbt, branch=origin_branch)
                    registry.schema.set_schema_branch(name=origin_branch.name, schema=updated_schema)
                    origin_branch.update_schema_hash()

                    await origin_branch.save(db=dbt)

                if config.SETTINGS.broker.enable and info.context.get("background"):
                    log_data = get_log_data()
                    request_id = log_data.get("request_id", "")
                    message = messages.EventBranchMerge(
                        source_branch=source_branch.name,
                        target_branch=config.SETTINGS.main.default_branch,
                        meta=Meta(initiator_id=WORKER_IDENTITY, request_id=request_id),
                    )
                    info.context.get("background").add_task(services.send, message)

        return proposed_change, result


class ProposedChangeRequestRunCheckInput(InputObjectType):
    id = String(required=True)
    check_type = CheckType(required=True)


class ProposedChangeRequestRefreshArtifactsInput(InputObjectType):
    id = String(required=True)


class ProposedChangeRequestRefreshArtifacts(Mutation):
    class Arguments:
        data = ProposedChangeRequestRefreshArtifactsInput(required=True)

    ok = Boolean()

    @classmethod
    async def mutate(
        cls,
        root: dict,  # pylint: disable=unused-argument
        info: GraphQLResolveInfo,
        data: Dict[str, Any],
    ) -> Dict[str, bool]:
        db: InfrahubDatabase = info.context.get("infrahub_database")
        rpc_client: InfrahubRpcClient = info.context.get("infrahub_rpc_client")

        identifier = data.get("id", "")
        proposed_change = await NodeManager.get_one_by_id_or_default_filter(
            id=identifier, schema_name="CoreProposedChange", db=db
        )
        state = ProposedChangeState(proposed_change.state.value)
        state.validate_state_check_run()

        await rpc_client.send(messages.RequestProposedChangeRefreshArtifacts(proposed_change=proposed_change.id))
        return {"ok": True}


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
        db: InfrahubDatabase = info.context.get("infrahub_database")
        rpc_client: InfrahubRpcClient = info.context.get("infrahub_rpc_client")

        check_type = data.get("check_type")

        identifier = data.get("id", "")
        proposed_change = await NodeManager.get_one_by_id_or_default_filter(
            id=identifier, schema_name="CoreProposedChange", db=db
        )
        state = ProposedChangeState(proposed_change.state.value)
        state.validate_state_check_run()

        if check_type == CheckType.ARTIFACT:
            await rpc_client.send(messages.RequestProposedChangeRefreshArtifacts(proposed_change=proposed_change.id))
        elif check_type == CheckType.DATA:
            await rpc_client.send(messages.RequestProposedChangeDataIntegrity(proposed_change=proposed_change.id))
        elif check_type in [CheckType.REPOSITORY, CheckType.USER]:
            await rpc_client.send(messages.RequestProposedChangeRepositoryChecks(proposed_change=proposed_change.id))
        elif check_type == CheckType.SCHEMA:
            await rpc_client.send(messages.RequestProposedChangeSchemaIntegrity(proposed_change=proposed_change.id))
        else:
            events = [
                messages.RequestProposedChangeDataIntegrity(proposed_change=proposed_change.id),
                messages.RequestProposedChangeRepositoryChecks(proposed_change=proposed_change.id),
                messages.RequestProposedChangeSchemaIntegrity(proposed_change=proposed_change.id),
                messages.RequestProposedChangeRefreshArtifacts(proposed_change=proposed_change.id),
            ]
            for event in events:
                await rpc_client.send(event)

        return {"ok": True}
