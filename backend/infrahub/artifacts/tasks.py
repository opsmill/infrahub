from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.protocols import CoreArtifact, CoreArtifactCheck
from prefect import flow, get_run_logger

from infrahub.artifacts.models import ArtifactCheckResult, CheckArtifactCreate
from infrahub.core.constants import ValidatorConclusion
from infrahub.core.timestamp import Timestamp
from infrahub.git.repository import get_initialized_repo
from infrahub.tasks.artifact import define_artifact
from infrahub.workers.dependencies import get_client
from infrahub.workflows.utils import add_tags

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient


async def _prepare_check(client: InfrahubClient, model: CheckArtifactCreate) -> CoreArtifactCheck:
    check_name = f"{model.artifact_name}: {model.target_name}"
    if model.check_id:
        existing_checks = await client.filters(
            kind=CoreArtifactCheck, ids=[model.check_id], validator__ids=[model.validator_id]
        )
    elif model.artifact_id:
        existing_checks = await client.filters(
            kind=CoreArtifactCheck, validator__ids=[model.validator_id], artifact_id__value=model.artifact_id
        )
    else:
        existing_checks = []
    if existing_checks:
        check = existing_checks[0]
        check.name.value = check_name
        check.created_at.value = Timestamp().to_string()
        check.conclusion.value = ValidatorConclusion.UNKNOWN.value
        check.severity.value = "info"
        check.message.value = "Rendering artifact"
        check.changed.value = None
        check.checksum.value = None
        check.artifact_id.value = model.artifact_id
        check.storage_id.value = None
    else:
        check = await client.create(
            kind=CoreArtifactCheck,
            data={
                "id": model.check_id,
                "name": check_name,
                "origin": model.repository_id,
                "kind": "ArtifactDefinition",
                "validator": model.validator_id,
                "created_at": Timestamp().to_string(),
                "message": "Rendering artifact",
                "conclusion": ValidatorConclusion.UNKNOWN.value,
                "severity": "info",
                "artifact_id": model.artifact_id,
            },
        )
    if existing_checks:
        await check.save()
    else:
        await check.create()

    return check


@flow(name="git-repository-check-artifact-create", flow_run_name="Check artifact creation")
async def create(model: CheckArtifactCreate) -> ArtifactCheckResult:
    await add_tags(branches=[model.branch_name], nodes=[model.target_id])

    client = get_client()
    client.request_context = model.context.to_request_context()
    log = get_run_logger()

    check = await _prepare_check(client=client, model=model)

    artifact: CoreArtifact | None = None
    try:
        repo = await get_initialized_repo(
            client=client,
            repository_id=model.repository_id,
            name=model.repository_name,
            repository_kind=model.repository_kind,
            infrahub_branch_name=model.branch_name,
            commit=model.commit,
        )
        artifact, artifact_created = await define_artifact(model=model)
        check.artifact_id.value = artifact.id
        result = await repo.render_artifact(artifact=artifact, artifact_created=artifact_created, message=model)
        check.changed.value = result.changed
        check.checksum.value = result.checksum
        check.artifact_id.value = result.artifact_id
        check.storage_id.value = result.storage_id
        check.message.value = "Artifact rendered successfully"
        conclusion = ValidatorConclusion.SUCCESS

    # Preparation and user transformation failures must remain visible as retryable check failures.
    except Exception as exc:  # noqa: BLE001
        conclusion = ValidatorConclusion.FAILURE
        check.severity.value = "critical"
        check.message.value = f"Failed to render artifact: {exc}"
        if artifact is not None:
            artifact.status.value = "Error"
            try:
                await artifact.save()
            # Reporting the artifact status must not hide the original check failure.
            except Exception:
                log.exception("Unable to record the artifact error status")

    check.conclusion.value = conclusion.value
    await check.save()

    return ArtifactCheckResult(conclusion=conclusion, check_id=check.id)
