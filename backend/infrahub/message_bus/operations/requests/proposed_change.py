from typing import List

from infrahub.core.constants import DiffAction, InfrahubKind, ProposedChangeState
from infrahub.core.integrity.object_conflict.conflict_recorder import ObjectConflictValidatorRecorder
from infrahub.core.manager import NodeManager
from infrahub.core.registry import registry
from infrahub.core.validators.uniqueness.checker import UniquenessChecker
from infrahub.log import get_logger
from infrahub.message_bus import InfrahubMessage, messages
from infrahub.services import InfrahubServices

log = get_logger()


async def cancel(message: messages.RequestProposedChangeCancel, service: InfrahubServices) -> None:
    """Cancel a proposed change."""
    log.info("Cancelling proposed change", id=message.proposed_change)
    proposed_change = await service.client.get(kind=InfrahubKind.PROPOSEDCHANGE, id=message.proposed_change)
    proposed_change.state.value = ProposedChangeState.CANCELED.value
    await proposed_change.save()


async def data_integrity(message: messages.RequestProposedChangeDataIntegrity, service: InfrahubServices) -> None:
    """Triggers a data integrity validation check on the provided proposed change to start."""
    log.info(f"Got a request to process data integrity defined in proposed_change: {message.proposed_change}")

    proposed_change = await NodeManager.get_one_by_id_or_default_filter(
        id=message.proposed_change, schema_name=InfrahubKind.PROPOSEDCHANGE, db=service.database
    )
    source_branch = await registry.get_branch(db=service.database, branch=proposed_change.source_branch.value)
    diff = await source_branch.diff(db=service.database, branch_only=False)
    conflicts = await diff.get_conflicts_graph(db=service.database)

    async with service.database.start_transaction() as db:
        object_conflict_validator_recorder = ObjectConflictValidatorRecorder(
            db=db, validator_kind=InfrahubKind.DATAVALIDATOR, validator_label="Data Integrity"
        )
        await object_conflict_validator_recorder.record_conflicts(message.proposed_change, conflicts)


async def schema_integrity(
    message: messages.RequestProposedChangeSchemaIntegrity,
    service: InfrahubServices,  # pylint: disable=unused-argument
) -> None:
    log.info(f"Got a request to process schema integrity defined in proposed_change: {message.proposed_change}")
    proposed_change = await NodeManager.get_one_by_id_or_default_filter(
        id=message.proposed_change, schema_name=InfrahubKind.PROPOSEDCHANGE, db=service.database
    )

    raw_diff = await service.client.get_diff_summary(branch=proposed_change.source_branch.value)

    altered_schema_kinds = set()
    for node_diff in raw_diff:
        if node_diff["branch"] == proposed_change.source_branch.value and {DiffAction.ADDED, DiffAction.UPDATED} & set(
            node_diff["actions"]
        ):
            altered_schema_kinds.add(node_diff["kind"])

    uniqueness_checker = UniquenessChecker(db=service.database)
    uniqueness_conflicts = await uniqueness_checker.get_conflicts(
        schemas=altered_schema_kinds,
        source_branch=proposed_change.source_branch.value,
    )

    async with service.database.start_transaction() as db:
        object_conflict_validator_recorder = ObjectConflictValidatorRecorder(
            db=db, validator_kind=InfrahubKind.SCHEMAVALIDATOR, validator_label="Schema Integrity"
        )
        await object_conflict_validator_recorder.record_conflicts(message.proposed_change, uniqueness_conflicts)


async def repository_checks(message: messages.RequestProposedChangeRepositoryChecks, service: InfrahubServices) -> None:
    log.info(f"Got a request to process checks defined in proposed_change: {message.proposed_change}")
    change_proposal = await service.client.get(kind=InfrahubKind.PROPOSEDCHANGE, id=message.proposed_change)

    repositories = await service.client.all(
        kind=InfrahubKind.GENERICREPOSITORY, branch=change_proposal.source_branch.value
    )
    events: List[InfrahubMessage] = []
    for repository in repositories:
        events.append(
            messages.RequestRepositoryChecks(
                proposed_change=message.proposed_change,
                repository=repository.id,
                source_branch=change_proposal.source_branch.value,
                target_branch=change_proposal.destination_branch.value,
            )
        )
        events.append(
            messages.RequestRepositoryUserChecks(
                proposed_change=message.proposed_change,
                repository=repository.id,
                source_branch=change_proposal.source_branch.value,
                target_branch=change_proposal.destination_branch.value,
            )
        )
    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)


async def refresh_artifacts(message: messages.RequestProposedChangeRefreshArtifacts, service: InfrahubServices) -> None:
    log.info(f"Refreshing artifacts for change_proposal={message.proposed_change}")
    proposed_change = await service.client.get(kind=InfrahubKind.PROPOSEDCHANGE, id=message.proposed_change)
    artifact_definitions = await service.client.all(
        kind=InfrahubKind.ARTIFACTDEFINITION, branch=proposed_change.source_branch.value
    )
    for artifact_definition in artifact_definitions:
        msg = messages.RequestArtifactDefinitionCheck(
            artifact_definition=artifact_definition.id,
            proposed_change=message.proposed_change,
            source_branch=proposed_change.source_branch.value,
            target_branch=proposed_change.destination_branch.value,
        )

        msg.assign_meta(parent=message)
        await service.send(message=msg)
