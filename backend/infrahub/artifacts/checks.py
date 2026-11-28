from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.protocols import CoreArtifactCheck

from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.constants import Severity, ValidatorConclusion


def artifact_check_name(*, artifact_name: str, target_name: str) -> str:
    return f"{artifact_name}: {target_name}"


async def save_artifact_check(
    client: InfrahubClient,
    *,
    validator_id: str,
    check_id: str | None,
    artifact_id: str | None,
    name: str,
    origin: str,
    conclusion: ValidatorConclusion,
    severity: Severity,
    message: str,
) -> CoreArtifactCheck:
    """Write the check of one target, updating the check found by its ID, else by its artifact, else creating it."""
    if check_id:
        existing_checks = await client.filters(kind=CoreArtifactCheck, ids=[check_id], validator__ids=[validator_id])
    elif artifact_id:
        existing_checks = await client.filters(
            kind=CoreArtifactCheck, validator__ids=[validator_id], artifact_id__value=artifact_id
        )
    else:
        existing_checks = []

    if existing_checks:
        check = existing_checks[0]
        check.name.value = name
        check.created_at.value = Timestamp().to_string()
        check.conclusion.value = conclusion.value
        check.severity.value = severity.value
        check.message.value = message
        check.changed.value = None
        check.checksum.value = None
        check.artifact_id.value = artifact_id
        check.storage_id.value = None
        await check.save()
        return check

    check = await client.create(
        kind=CoreArtifactCheck,
        data={
            "id": check_id,
            "name": name,
            "origin": origin,
            "kind": "ArtifactDefinition",
            "validator": validator_id,
            "created_at": Timestamp().to_string(),
            "message": message,
            "conclusion": conclusion.value,
            "severity": severity.value,
            "artifact_id": artifact_id,
        },
    )
    await check.create()
    return check
