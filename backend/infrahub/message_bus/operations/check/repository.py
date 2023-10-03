from infrahub import lock
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import CheckError
from infrahub.git.repository import InfrahubRepository
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices

log = get_logger()


async def check_definition(message: messages.CheckRepositoryCheckDefinition, service: InfrahubServices):
    validator = await service.client.get(kind="CoreRepositoryValidator", id=message.validator_id)
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
            existing_check.typename == "CoreStandardCheck"
            and existing_check.kind.value == "CheckDefinition"
            and existing_check.name.value == message.class_name
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
            kind="CoreStandardCheck",
            data={
                "name": message.class_name,
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
        value=conclusion,
        expires=7200,
    )


async def merge_conflicts(message: messages.CheckRepositoryMergeConflicts, service: InfrahubServices):
    """Runs a check to see if there are merge conflicts between two branches."""
    log.info(
        "Checking for merge conflicts",
        repository_id=message.repository_id,
        proposed_change_id=message.proposed_change,
    )

    success_condition = "-"
    validator = await service.client.get(kind="CoreRepositoryValidator", id=message.validator_id)
    await validator.checks.fetch()

    repo = await InfrahubRepository.init(id=message.repository_id, name=message.repository_name)
    async with lock.registry.get(name=message.repository_name, namespace="repository"):
        conflicts = await repo.get_conflicts(source_branch=message.source_branch, dest_branch=message.target_branch)

    existing_checks = {}
    for relationship in validator.checks.peers:
        existing_check = relationship.peer
        if existing_check.typename == "CoreFileCheck" and existing_check.kind.value == "MergeConflictCheck":
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
                    kind="CoreFileCheck",
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

    else:
        if success_condition in existing_checks:
            existing_checks[success_condition].created_at.value = Timestamp().to_string()
            await existing_checks[success_condition].save()
            existing_checks.pop(success_condition)
        else:
            check = await service.client.create(
                kind="CoreFileCheck",
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
