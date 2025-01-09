from infrahub_sdk.uuidt import UUIDT
from prefect import flow
from prefect.logging import get_run_logger

from infrahub.core.constants import InfrahubKind
from infrahub.core.timestamp import Timestamp
from infrahub.message_bus import InfrahubMessage, messages
from infrahub.message_bus.types import KVTTL
from infrahub.services import InfrahubServices
from infrahub.workflows.utils import add_tags


@flow(name="repository-check", flow_run_name="Running repository checks for repository {message.repository}")
async def checks(message: messages.RequestRepositoryChecks, service: InfrahubServices) -> None:
    """Request to start validation checks on a specific repository."""
    await add_tags(branches=[message.source_branch], nodes=[message.proposed_change])
    log = get_run_logger()

    events: list[InfrahubMessage] = []

    repository = await service.client.get(
        kind=InfrahubKind.GENERICREPOSITORY, id=message.repository, branch=message.source_branch
    )
    proposed_change = await service.client.get(kind=InfrahubKind.PROPOSEDCHANGE, id=message.proposed_change)

    validator_execution_id = str(UUIDT())
    check_execution_ids: list[str] = []
    await proposed_change.validations.fetch()
    await repository.checks.fetch()

    validator_name = f"Repository Validator: {repository.name.value}"
    validator = None
    for relationship in proposed_change.validations.peers:
        existing_validator = relationship.peer

        if (
            existing_validator.typename == InfrahubKind.REPOSITORYVALIDATOR
            and existing_validator.repository.id == message.repository
        ):
            validator = existing_validator

    if validator:
        validator.conclusion.value = "unknown"
        validator.state.value = "queued"
        validator.started_at.value = ""
        validator.completed_at.value = ""
        await validator.save()
    else:
        validator = await service.client.create(
            kind=InfrahubKind.REPOSITORYVALIDATOR,
            data={
                "label": validator_name,
                "proposed_change": message.proposed_change,
                "repository": message.repository,
            },
        )
        await validator.save()

    check_execution_id = str(UUIDT())
    check_execution_ids.append(check_execution_id)
    log.info("Adding check for merge conflict")

    events.append(
        messages.CheckRepositoryMergeConflicts(
            validator_id=validator.id,
            validator_execution_id=validator_execution_id,
            check_execution_id=check_execution_id,
            proposed_change=message.proposed_change,
            repository_id=message.repository,
            repository_name=repository.name.value,
            source_branch=message.source_branch,
            target_branch=message.target_branch,
        )
    )

    checks_in_execution = ",".join(check_execution_ids)
    log.info(f"Checks in execution {checks_in_execution}")
    await service.cache.set(
        key=f"validator_execution_id:{validator_execution_id}:checks",
        value=checks_in_execution,
        expires=KVTTL.TWO_HOURS,
    )
    events.append(
        messages.FinalizeValidatorExecution(
            start_time=Timestamp().to_string(),
            validator_id=validator.id,
            validator_execution_id=validator_execution_id,
            validator_type=InfrahubKind.REPOSITORYVALIDATOR,
        )
    )

    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)


@flow(
    name="repository-users-check",
    flow_run_name="Evaluating user-defined checks on repository {message.repository_name}",
)
async def user_checks(message: messages.RequestRepositoryUserChecks, service: InfrahubServices) -> None:
    """Request to start validation checks on a specific repository for User-defined checks."""

    await add_tags(branches=[message.source_branch], nodes=[message.proposed_change])
    log = get_run_logger()

    events: list[InfrahubMessage] = []

    repository = await service.client.get(
        kind=InfrahubKind.GENERICREPOSITORY, id=message.repository_id, branch=message.source_branch, fragment=True
    )
    await repository.checks.fetch()

    for relationship in repository.checks.peers:
        log.info("Adding check for user defined check")
        check_definition = relationship.peer
        events.append(
            messages.CheckRepositoryCheckDefinition(
                check_definition_id=check_definition.id,
                repository_id=repository.id,
                repository_name=repository.name.value,
                commit=repository.commit.value,
                file_path=check_definition.file_path.value,
                class_name=check_definition.class_name.value,
                branch_name=message.source_branch,
                proposed_change=message.proposed_change,
                branch_diff=message.branch_diff,
            )
        )

    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)
