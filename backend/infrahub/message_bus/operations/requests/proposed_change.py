from typing import List

from infrahub.core.branch import ObjectConflict
from infrahub.core.constants import ProposedChangeState
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema import ValidatorConclusion, ValidatorState
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.log import get_logger
from infrahub.message_bus import InfrahubMessage, messages
from infrahub.services import InfrahubServices

log = get_logger()


async def _create_data_check(db: InfrahubDatabase, proposed_change: Node) -> Node:
    validations = await proposed_change.validations.get_peers(db=db)

    for validation in validations.values():
        if validation._schema.kind == "CoreDataValidator":
            return validation

    validator_obj = await Node.init(db=db, schema="CoreDataValidator")
    await validator_obj.new(
        db=db,
        label="Data Integrity",
        state=ValidatorState.QUEUED.value,
        conclusion=ValidatorConclusion.UNKNOWN.value,
        proposed_change=proposed_change.id,
    )
    await validator_obj.save(db=db)
    return validator_obj


async def _get_conflicts(db: InfrahubDatabase, proposed_change: Node) -> List[ObjectConflict]:
    source_branch = await registry.get_branch(db=db, branch=proposed_change.source_branch.value)
    diff = await source_branch.diff(db=db, branch_only=False)
    return await diff.get_conflicts_graph(db=db)


async def cancel(message: messages.RequestProposedChangeDataIntegrity, service: InfrahubServices) -> None:
    """Cancel a proposed change."""
    log.info("Cancelling proposed change", id=message.proposed_change)
    proposed_change = await service.client.get(kind="CoreProposedChange", id=message.proposed_change)
    proposed_change.state.value = ProposedChangeState.CANCELED.value
    await proposed_change.save()


async def data_integrity(message: messages.RequestProposedChangeDataIntegrity, service: InfrahubServices) -> None:
    """Triggers a data integrity validation check on the provided proposed change to start."""
    log.info(f"Got a request to process data integrity defined in proposed_change: {message.proposed_change}")
    async with service.database.start_transaction() as db:
        proposed_change = await NodeManager.get_one_by_id_or_default_filter(
            id=message.proposed_change, schema_name="CoreProposedChange", db=db
        )

        data_check = await _create_data_check(db=db, proposed_change=proposed_change)

        data_check.state.value = ValidatorState.IN_PROGRESS.value
        data_check.conclusion.value = ValidatorConclusion.UNKNOWN.value
        data_check.started_at.value = Timestamp().to_string()
        data_check.completed_at.value = ""
        await data_check.save(db=db)

        previous_checks = await data_check.checks.get_peers(db=db)

        conflicts = await _get_conflicts(db=db, proposed_change=proposed_change)

        conclusion = ValidatorConclusion.FAILURE

        check_objects = []
        keep_check = []
        if not conflicts:
            conclusion = ValidatorConclusion.SUCCESS
            check = None
            for previous_check in previous_checks.values():
                if previous_check.conflicts.value == []:
                    check = previous_check
                    keep_check.append(check.id)

            if not check:
                check = await Node.init(db=db, schema="CoreDataCheck")
                await check.new(
                    db=db,
                    label="Data Conflict",
                    origin="internal",
                    kind="DataIntegrity",
                    validator=data_check.id,
                    conclusion="success",
                    severity="info",
                    conflicts=[],
                )
                await check.save(db=db)
            check_objects.append(check.id)

        for conflict in conflicts:
            conflicts_data = [
                {
                    "name": conflict.name,
                    "node_id": conflict.id,
                    "kind": conflict.kind,
                    "path_type": conflict.path_type.value,
                    "path": conflict.conflict_path,
                    "property_name": conflict.property_name,
                    "change_type": conflict.change_type,
                    "changes": [change.dict() for change in conflict.changes],
                }
            ]
            conflict_obj = None
            for previous_check in previous_checks.values():
                if previous_check.conflicts.value == conflicts_data:
                    conflict_obj = previous_check
                    keep_check.append(conflict_obj.id)

            if not conflict_obj:
                conflict_obj = await Node.init(db=db, schema="CoreDataCheck")

                await conflict_obj.new(
                    db=db,
                    label="Data Conflict",
                    origin="internal",
                    kind="DataIntegrity",
                    validator=data_check.id,
                    conclusion="failure",
                    severity="critical",
                    conflicts=conflicts_data,
                )

                await conflict_obj.save(db=db)
            check_objects.append(conflict_obj.id)

        for check_id, previous_check in previous_checks.items():
            if check_id not in keep_check:
                await previous_check.delete(db=db)

        data_check.state.value = ValidatorState.COMPLETED.value
        data_check.conclusion.value = conclusion.value
        data_check.checks.update = check_objects
        data_check.completed_at.value = Timestamp().to_string()
        await data_check.save(db=db)


async def schema_integrity(
    message: messages.RequestProposedChangeSchemaIntegrity,
    service: InfrahubServices,  # pylint: disable=unused-argument
) -> None:
    log.info(f"Got a request to process schema integrity defined in proposed_change: {message.proposed_change}")


async def repository_checks(message: messages.RequestProposedChangeRepositoryChecks, service: InfrahubServices) -> None:
    log.info(f"Got a request to process checks defined in proposed_change: {message.proposed_change}")
    change_proposal = await service.client.get(kind="CoreProposedChange", id=message.proposed_change)

    repositories = await service.client.all(kind="CoreRepository", branch=change_proposal.source_branch.value)
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
    proposed_change = await service.client.get(kind="CoreProposedChange", id=message.proposed_change)
    artifact_definitions = await service.client.all(
        kind="CoreArtifactDefinition", branch=proposed_change.source_branch.value
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
