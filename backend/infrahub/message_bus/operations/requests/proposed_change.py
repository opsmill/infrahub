from typing import List

from neo4j import AsyncSession

from infrahub.core.branch import ObjectConflict
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema import ValidatorConclusion, ValidatorState
from infrahub.core.timestamp import Timestamp
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices

log = get_logger()


async def _create_data_check(session: AsyncSession, proposed_change: Node) -> None:
    conflicts = await _get_conflicts(session=session, proposed_change=proposed_change)

    validator_obj = await Node.init(session=session, schema="CoreDataValidator")

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
        label="Data Integrity",
        proposed_change=proposed_change.id,
        state=initial_state.value,
        conclusion=initial_conclusion.value,
        started_at=started_at,
        **params,
    )
    await validator_obj.save(session=session)

    for conflict in conflicts:
        conflict_obj = await Node.init(session=session, schema="CoreDataCheck")
        await conflict_obj.new(
            session=session,
            label="Data Conflict",
            origin="internal",
            kind="DataIntegrity",
            validator=validator_obj.id,
            conclusion="failure",
            severity="critical",
            paths=[str(conflict)],
            **params,
        )
        await conflict_obj.save(session=session)

    if conflicts:
        updated_validator_obj = await NodeManager.get_one_by_id_or_default_filter(
            id=validator_obj.id, schema_name="CoreDataValidator", session=session
        )
        updated_validator_obj.state.value = ValidatorState.COMPLETED.value
        updated_validator_obj.conclusion.value = ValidatorConclusion.FAILURE.value
        updated_validator_obj.completed_at.value = Timestamp().to_string()
        await updated_validator_obj.save(session=session)


async def _get_conflicts(session: AsyncSession, proposed_change: Node) -> List[ObjectConflict]:
    source_branch = await registry.get_branch(session=session, branch=proposed_change.source_branch.value)
    diff = await source_branch.diff(session=session, branch_only=False)
    return await diff.get_conflicts_graph(session=session)


async def data_integrity(message: messages.RequestProposedChangeDataIntegrity, service: InfrahubServices) -> None:
    """Triggers a data integrity validation check on the provided proposed change to start."""
    log.info(f"Got a request to process data integrity defined in proposed_change: {message.proposed_change}")
    async with service.database.session as session:
        proposed_change = await NodeManager.get_one_by_id_or_default_filter(
            id=message.proposed_change, schema_name="CoreProposedChange", session=session
        )
        validations = await proposed_change.validations.get_peers(session=session)
        data_check = None
        for validation in validations.values():
            if validation._schema.kind == "CoreDataValidator":
                data_check = validation
                break

        if not data_check:
            await _create_data_check(session=session, proposed_change=proposed_change)
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
            conflict_obj = await Node.init(session=session, schema="CoreDataCheck")
            await conflict_obj.new(
                session=session,
                label="Data Conflict",
                origin="internal",
                kind="DataIntegrity",
                validator=data_check.id,
                conclusion="failure",
                severity="critical",
                paths=[str(conflict)],
            )
            await conflict_obj.save(session=session)
            conflict_objects.append(conflict_obj.id)

        previous_relationships = await data_check.checks.get_relationships(session=session)
        for rel in previous_relationships:
            await rel.delete(session=session)

        data_check.state_value = state.value
        data_check.conclusion.value = conclusion.value
        data_check.checks.update = conflict_objects
        data_check.started_at.value = started_at
        data_check.completed_at.value = completed_at
        await data_check.save(session=session)


async def schema_integrity(
    message: messages.RequestProposedChangeSchemaIntegrity, service: InfrahubServices  # pylint: disable=unused-argument
) -> None:
    log.info(f"Got a request to process schema integrity defined in proposed_change: {message.proposed_change}")


async def repository_checks(message: messages.RequestProposedChangeRepositoryChecks, service: InfrahubServices) -> None:
    log.info(f"Got a request to process checks defined in proposed_change: {message.proposed_change}")
    change_proposal = await service.client.get(kind="CoreProposedChange", id=message.proposed_change)

    repositories = await service.client.all(kind="CoreRepository", branch=change_proposal.source_branch.value)
    for repository in repositories:
        msg = messages.RequestRepositoryChecks(
            proposed_change=message.proposed_change,
            repository=repository.id,
            source_branch=change_proposal.source_branch.value,
            target_branch=change_proposal.destination_branch.value,
        )
        msg.assign_meta(parent=message)
        await service.send(message=msg)


async def refresh_artifacts(message: messages.RequestProposedChangeRefreshArtifacts, service: InfrahubServices) -> None:
    log.info(f"Refreshing artifacts for change_proposal={message.proposed_change}")
    proposed_change = await service.client.get(kind="CoreProposedChange", id=message.proposed_change)
    artifact_definitions = await service.client.all(
        kind="CoreArtifactDefinition", branch=proposed_change.source_branch.value
    )
    for artifact_definition in artifact_definitions:
        msg = messages.RequestArtifactDefinitionGenerate(
            artifact_definition=artifact_definition.id, branch=proposed_change.source_branch.value
        )
        msg.assign_meta(parent=message)
        await service.send(message=msg)
