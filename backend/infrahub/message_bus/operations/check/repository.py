from typing import List

from infrahub_sdk import UUIDT

from infrahub import lock
from infrahub.core.constants import InfrahubKind
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import CheckError
from infrahub.git.repository import InfrahubRepository
from infrahub.log import get_logger
from infrahub.message_bus import InfrahubMessage, messages
from infrahub.services import InfrahubServices

log = get_logger()


async def check_definition(message: messages.CheckRepositoryCheckDefinition, service: InfrahubServices):
    definition = await service.client.get(kind=InfrahubKind.CHECKDEFINITION, id=message.check_definition_id)

    proposed_change = await service.client.get(kind=InfrahubKind.PROPOSEDCHANGE, id=message.proposed_change)
    validator_execution_id = str(UUIDT())
    check_execution_ids: List[str] = []
    await proposed_change.validations.fetch()
    validator = None
    events: List[InfrahubMessage] = []

    for relationship in proposed_change.validations.peers:
        existing_validator = relationship.peer

        if (
            existing_validator.typename == InfrahubKind.USERVALIDATOR
            and existing_validator.repository.id == message.repository_id
            and existing_validator.check_definition.id == message.check_definition_id
        ):
            validator = existing_validator
            service.log.info("Found the same validator", validator=validator)

    if validator:
        validator.conclusion.value = "unknown"
        validator.state.value = "queued"
        validator.started_at.value = ""
        validator.completed_at.value = ""
        await validator.save()
    else:
        validator = await service.client.create(
            kind=InfrahubKind.USERVALIDATOR,
            data={
                "label": f"Check: {definition.name.value}",
                "proposed_change": message.proposed_change,
                "repository": message.repository_id,
                "check_definition": message.check_definition_id,
            },
        )
        await validator.save()

    if definition.targets.id:
        # Check against a group of targets
        await definition.targets.fetch()
        group = definition.targets.peer
        await group.members.fetch()
        for relationship in group.members.peers:
            member = relationship.peer

            check_execution_id = str(UUIDT())
            check_execution_ids.append(check_execution_id)
            events.append(
                messages.CheckRepositoryUserCheck(
                    name=member.display_label,
                    validator_id=validator.id,
                    validator_execution_id=validator_execution_id,
                    check_execution_id=check_execution_id,
                    repository_id=message.repository_id,
                    repository_name=message.repository_name,
                    commit=message.commit,
                    file_path=message.file_path,
                    class_name=message.class_name,
                    branch_name=message.branch_name,
                    check_definition_id=message.check_definition_id,
                    proposed_change=message.proposed_change,
                    variables=member.extract(params=definition.parameters.value),
                )
            )

    else:
        check_execution_id = str(UUIDT())
        check_execution_ids.append(check_execution_id)
        events.append(
            messages.CheckRepositoryUserCheck(
                name=definition.name.value,
                validator_id=validator.id,
                validator_execution_id=validator_execution_id,
                check_execution_id=check_execution_id,
                repository_id=message.repository_id,
                repository_name=message.repository_name,
                commit=message.commit,
                file_path=message.file_path,
                class_name=message.class_name,
                branch_name=message.branch_name,
                check_definition_id=message.check_definition_id,
                proposed_change=message.proposed_change,
            )
        )

    checks_in_execution = ",".join(check_execution_ids)
    log.info("Checks in execution", checks=checks_in_execution)
    await service.cache.set(
        key=f"validator_execution_id:{validator_execution_id}:checks", value=checks_in_execution, expires=7200
    )
    events.append(
        messages.FinalizeValidatorExecution(
            start_time=Timestamp().to_string(),
            validator_id=validator.id,
            validator_execution_id=validator_execution_id,
            validator_type=InfrahubKind.USERVALIDATOR,
        )
    )

    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)


async def merge_conflicts(message: messages.CheckRepositoryMergeConflicts, service: InfrahubServices):
    """Runs a check to see if there are merge conflicts between two branches."""
    log.info(
        "Checking for merge conflicts",
        repository_id=message.repository_id,
        proposed_change_id=message.proposed_change,
    )

    success_condition = "-"
    validator = await service.client.get(kind=InfrahubKind.REPOSITORYVALIDATOR, id=message.validator_id)
    await validator.checks.fetch()

    repo = await InfrahubRepository.init(id=message.repository_id, name=message.repository_name)
    async with lock.registry.get(name=message.repository_name, namespace="repository"):
        conflicts = await repo.get_conflicts(source_branch=message.source_branch, dest_branch=message.target_branch)

    existing_checks = {}
    for relationship in validator.checks.peers:
        existing_check = relationship.peer
        if existing_check.typename == InfrahubKind.FILECHECK and existing_check.kind.value == "MergeConflictCheck":
            check_key = ""
            if existing_check.files.value:
                check_key = "".join(existing_check.files.value)
            check_key = f"-{check_key}"
            existing_checks[check_key] = existing_check

    validator_conclusion = "success"
    check = None
    if conflicts:
        validator_conclusion = "failure"
        for conflict in conflicts:
            conflict_key = f"-{conflict}"
            if conflict_key in existing_checks:
                existing_checks[conflict_key].created_at.value = Timestamp().to_string()
                await existing_checks[conflict_key].save()
                existing_checks.pop(conflict_key)
            else:
                check = await service.client.create(
                    kind=InfrahubKind.FILECHECK,
                    data={
                        "name": conflict,
                        "origin": "ConflictCheck",
                        "kind": "MergeConflictCheck",
                        "validator": message.validator_id,
                        "created_at": Timestamp().to_string(),
                        "files": [conflict],
                        "conclusion": "failure",
                        "severity": "critical",
                    },
                )
                await check.save()

    elif success_condition in existing_checks:
        existing_checks[success_condition].created_at.value = Timestamp().to_string()
        await existing_checks[success_condition].save()
        existing_checks.pop(success_condition)

    else:
        check = await service.client.create(
            kind=InfrahubKind.FILECHECK,
            data={
                "name": "Merge Conflict Check",
                "origin": "ConflictCheck",
                "kind": "MergeConflictCheck",
                "validator": message.validator_id,
                "created_at": Timestamp().to_string(),
                "conclusion": "success",
                "severity": "info",
            },
        )
        await check.save()

    for previous_result in existing_checks.values():
        await previous_result.delete()

    await service.cache.set(
        key=f"validator_execution_id:{message.validator_execution_id}:check_execution_id:{message.check_execution_id}",
        value=validator_conclusion,
        expires=7200,
    )


async def user_check(message: messages.CheckRepositoryUserCheck, service: InfrahubServices):
    validator = await service.client.get(kind=InfrahubKind.USERVALIDATOR, id=message.validator_id)
    await validator.checks.fetch()

    repo = await InfrahubRepository.init(id=message.repository_id, name=message.repository_name)
    conclusion = "failure"
    severity = "critical"
    log_entries = ""
    try:
        check_run = await repo.execute_python_check(
            branch_name=message.branch_name,
            location=message.file_path,
            class_name=message.class_name,
            client=service.client,
            commit=message.commit,
            params=message.variables,
        )
        if check_run.passed:
            conclusion = "success"
            severity = "info"
            log.info("The check passed", check_execution_id=message.check_execution_id)
        else:
            log.warning("The check reported failures", check_execution_id=message.check_execution_id)
        log_entries = check_run.log_entries
    except CheckError as exc:
        log.warning("The check failed to run", check_execution_id=message.check_execution_id)
        log_entries = f"FATAL Error/n:{exc.message}"

    check = None
    for relationship in validator.checks.peers:
        existing_check = relationship.peer
        if (
            existing_check.typename == InfrahubKind.STANDARDCHECK
            and existing_check.kind.value == "CheckDefinition"
            and existing_check.name.value == message.name
        ):
            check = existing_check

    if check:
        check.created_at.value = Timestamp().to_string()
        check.message.value = log_entries
        check.conclusion.value = conclusion
        check.severity.value = severity
        await check.save()
    else:
        check = await service.client.create(
            kind=InfrahubKind.STANDARDCHECK,
            data={
                "name": message.name,
                "origin": message.repository_id,
                "kind": "CheckDefinition",
                "validator": message.validator_id,
                "created_at": Timestamp().to_string(),
                "message": log_entries,
                "conclusion": conclusion,
                "severity": severity,
            },
        )
        await check.save()

    await service.cache.set(
        key=f"validator_execution_id:{message.validator_execution_id}:check_execution_id:{message.check_execution_id}",
        value="success",
        expires=7200,
    )
