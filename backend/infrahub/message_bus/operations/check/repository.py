from infrahub import lock
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import CheckError
from infrahub.git.repository import InfrahubRepository
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices

log = get_logger()


async def check_definition(message: messages.CheckRepositoryCheckDefinition, service: InfrahubServices):
    repo = await InfrahubRepository.init(id=message.repository_id, name=message.repository_name)

    try:
        check = await repo.execute_python_check(
            branch_name=message.branch_name,
            location=message.file_path,
            class_name=message.class_name,
            client=service.client,
            commit=message.commit,
        )
    except CheckError:
        log.warning("The check failed")
        return

    if check.passed:
        log.info("The check passed")
    else:
        log.warning("The check failed")


async def merge_conflicts(message: messages.CheckRepositoryMergeConflicts, service: InfrahubServices):
    """Runs a check to see if there are merge conflicts between two branches."""
    log.info(
        "Checking for merge conflicts",
        repository_id=message.repository_id,
        proposed_change_id=message.proposed_change,
    )

    success_condition = "-"
    validator = await service.client.get(kind="CoreRepositoryValidator", id=message.validator_id)
    validator.state.value = "in_progress"
    validator.started_at.value = Timestamp().to_string()
    validator.completed_at.value = ""
    await validator.save()
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
        # await existing_checks[previous_result].delete()
        await previous_result.delete()

    validator.state.value = "completed"
    validator.conclusion.value = validator_conclusion
    validator.completed_at.value = Timestamp().to_string()
    await validator.save()
