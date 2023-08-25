from typing import TYPE_CHECKING, Any, Dict, List, Optional

from graphene import Boolean, Enum, InputObjectType, Mutation, String
from graphql import GraphQLResolveInfo
from neo4j import AsyncSession

from infrahub.core.branch import ObjectConflict
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema import NodeSchema, ValidatorConclusion, ValidatorState
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import NodeNotFound
from infrahub.graphql.mutations.main import InfrahubMutationMixin
from infrahub.message_bus import messages

from .main import InfrahubMutationOptions

if TYPE_CHECKING:
    from infrahub.message_bus.rpc import InfrahubRpcClient


class CheckType(Enum):
    DATA = "data"
    REPOSITORY = "repository"
    SCHEMA = "schema"
    ALL = "all"


async def _get_conflicts(session: AsyncSession, proposed_change: Node) -> List[ObjectConflict]:
    source_branch = await registry.get_branch(session=session, branch=proposed_change.source_branch.value)
    diff = await source_branch.diff(session=session, branch_only=False)
    return await diff.get_conflicts_graph(session=session)


async def create_data_check(session: AsyncSession, proposed_change: Node) -> None:
    conflicts = await _get_conflicts(session=session, proposed_change=proposed_change)

    validator_obj = await Node.init(session=session, schema="InternalDataIntegrityValidator")

    initial_state = ValidatorState.COMPLETED
    initial_conclusion = ValidatorConclusion.SUCCESS
    started_at = Timestamp().to_string()
    params = {"completed_at": Timestamp().to_string()}
    if conflicts:
        initial_state = ValidatorState.IN_PROGRESS
        initial_conclusion = ValidatorConclusion.UNKNOWN
        params.pop("completed_at")

    await validator_obj.new(
        session=session,
        proposed_change=proposed_change.id,
        state=initial_state.value,
        conclusion=initial_conclusion.value,
        started_at=started_at,
        **params,
    )
    await validator_obj.save(session=session)

    for conflict in conflicts:
        conflict_obj = await Node.init(session=session, schema="InternalDataConflict")
        await conflict_obj.new(
            session=session,
            validator=validator_obj.id,
            paths=[str(conflict)],
            **params,
        )
        await conflict_obj.save(session=session)

    if conflicts:
        updated_validator_obj = await NodeManager.get_one_by_id_or_default_filter(
            id=validator_obj.id, schema_name="InternalDataIntegrityValidator", session=session
        )
        updated_validator_obj.state.value = ValidatorState.COMPLETED.value
        updated_validator_obj.conclusion.value = ValidatorConclusion.FAILURE.value
        updated_validator_obj.completed_at.value = Timestamp().to_string()
        await updated_validator_obj.save(session=session)


async def update_data_check(session: AsyncSession, proposed_change: Node) -> None:
    validations = await proposed_change.validations.get_peers(session=session)
    data_check = None
    for validation in validations.values():
        if validation._schema.kind == "InternalDataIntegrityValidator":
            data_check = validation
            break

    if not data_check:
        await create_data_check(session=session, proposed_change=proposed_change)
        return

    conflicts = await _get_conflicts(session=session, proposed_change=proposed_change)

    state = ValidatorState.COMPLETED
    conclusion = ValidatorConclusion.SUCCESS

    started_at = Timestamp().to_string()
    completed_at = Timestamp().to_string()
    if conflicts:
        state = ValidatorState.COMPLETED
        conclusion = ValidatorConclusion.FAILURE

    conflict_objects = []
    for conflict in conflicts:
        conflict_obj = await Node.init(session=session, schema="InternalDataConflict")
        await conflict_obj.new(
            session=session,
            validator=data_check.id,
            paths=[str(conflict)],
        )
        await conflict_obj.save(session=session)
        conflict_objects.append(conflict_obj.id)

    previous_relationships = await data_check.conflicts.get_relationships(session=session)
    for rel in previous_relationships:
        await rel.delete(session=session)

    data_check.state_value = state.value
    data_check.conclusion.value = conclusion.value
    data_check.conflicts.update = conflict_objects
    data_check.started_at.value = started_at
    data_check.completed_at.value = completed_at
    await data_check.save(session=session)


class InfrahubProposedChangeMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(
        cls, schema: NodeSchema = None, _meta=None, **options
    ):  # pylint: disable=arguments-differ
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
        branch: Optional[str] = None,
        at: Optional[str] = None,
    ):
        session: AsyncSession = info.context.get("infrahub_session")
        rpc_client: InfrahubRpcClient = info.context.get("infrahub_rpc_client")

        proposed_change, result = await super().mutate_create(root=root, info=info, data=data, branch=branch, at=at)

        await create_data_check(session=session, proposed_change=proposed_change)

        events = [
            messages.RequestProposedChangeDataIntegrity(proposed_change=proposed_change.id),
            messages.RequestProposedChangeRepositoryChecks(proposed_change=proposed_change.id),
            messages.RequestProposedChangeSchemaIntegrity(proposed_change=proposed_change.id),
        ]
        for event in events:
            await rpc_client.send(event)

        return proposed_change, result


async def get_proposed_change(identifier: str, session: AsyncSession) -> Node:
    proposed_change = await NodeManager.get_one_by_id_or_default_filter(
        id=identifier, schema_name="CoreProposedChange", session=session
    )
    if not proposed_change:
        raise NodeNotFound(
            branch_name="-global-",
            node_type="CoreProposedChange",
            identifier=identifier,
            message="The requested proposed change wasn't found",
        )

    return proposed_change


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
        session: AsyncSession = info.context.get("infrahub_session")
        rpc_client: InfrahubRpcClient = info.context.get("infrahub_rpc_client")

        identifier = data.get("id", "")
        proposed_change = await get_proposed_change(identifier=identifier, session=session)
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
        session: AsyncSession = info.context.get("infrahub_session")
        rpc_client: InfrahubRpcClient = info.context.get("infrahub_rpc_client")

        check_type = data.get("check_type")

        identifier = data.get("id", "")
        proposed_change = await get_proposed_change(identifier=identifier, session=session)

        if check_type == CheckType.DATA:
            await rpc_client.send(messages.RequestProposedChangeDataIntegrity(proposed_change=proposed_change.id))
            # Once the data integrity check is handled in the worker nodes the below call will be removed
            await update_data_check(session=session, proposed_change=proposed_change)
        elif check_type == CheckType.REPOSITORY:
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
