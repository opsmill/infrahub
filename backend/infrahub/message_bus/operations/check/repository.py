from infrahub.core.timestamp import Timestamp
from infrahub.git.repository import InfrahubRepository
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices

log = get_logger()


async def merge_conflicts(message: messages.CheckRepositoryMergeConflicts, service: InfrahubServices):
    """Runs a check to see if there are merge conflicts between two branches."""
    log.info(
        "Checking for merge conflicts",
        repository_id=message.repository_id,
        proposed_change_id=message.proposed_change,
    )
    validator = await service.client.get(kind="CoreRepositoryValidator", id=message.validator_id)
    validator.state.value = "in_progress"
    validator.started_at.value = Timestamp().to_string()
    validator.completed_at.value = ""
    await validator.save()
    await validator.checks.fetch()

    repo = await InfrahubRepository.init(id=message.repository_id, name=message.repository_name)
    conflicts = await repo.get_conflicts(source_branch=message.source_branch, dest_branch=message.target_branch)

    conclusion = "success"
    severity = "info"
    validator_conclusion = "success"
    check = None
    if conflicts:
        conclusion = "failure"
        severity = "critical"
        validator_conclusion = "failure"

    for relationship in validator.checks.peers:
        existing_check = relationship.peer
        if existing_check.typename == "CoreFileCheck" and existing_check.kind.value == "MergeConflictCheck":
            check = existing_check

    if check:
        check.created_at.value = Timestamp().to_string()
        check.files.value = conflicts
        check.conclusion.value = conclusion
        check.severity.value = severity
    else:
        check = await service.client.create(
            kind="CoreFileCheck",
            data={
                "name": "Merge Conflict Check",
                "origin": "ConflictCheck",
                "kind": "MergeConflictCheck",
                "validator": message.validator_id,
                "created_at": Timestamp().to_string(),
                "files": conflicts,
                "conclusion": conclusion,
                "severity": severity,
            },
        )

    await check.save()

    validator.state.value = "completed"
    validator.conclusion.value = validator_conclusion
    validator.completed_at.value = Timestamp().to_string()
    await validator.save()
