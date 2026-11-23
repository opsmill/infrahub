from dataclasses import dataclass

from infrahub_sdk import InfrahubClient
from infrahub_sdk.protocols import CoreArtifactCheck
from prefect import flow
from prefect.settings import get_current_settings

from infrahub import config
from infrahub.artifacts.models import CheckArtifactCreate
from infrahub.artifacts.render_request import request_external_render
from infrahub.artifacts.render_result import (
    RENDER_FAILED_MESSAGE,
    RENDER_SUCCEEDED_MESSAGE,
    WAITING_FOR_EXTERNAL_ENGINE_MESSAGE,
)
from infrahub.core.constants import ArtifactStatus, InfrahubKind, ValidatorConclusion
from infrahub.core.timestamp import Timestamp
from infrahub.core.validators.checks_runner import CheckPending, CheckResult
from infrahub.git.repository import get_initialized_repo
from infrahub.tasks.artifact import define_artifact
from infrahub.workers.dependencies import get_client, get_event_service
from infrahub.workflows.utils import add_tags


@dataclass(frozen=True)
class ArtifactCheckResult:
    changed: bool | None = None
    checksum: str | None = None
    artifact_id: str | None = None
    storage_id: str | None = None


@flow(name="git-repository-check-artifact-create", flow_run_name="Check artifact creation")
async def create(model: CheckArtifactCreate) -> CheckResult:
    await add_tags(branches=[model.branch_name], nodes=[model.target_id])

    client = get_client()
    client.request_context = model.context.to_request_context()

    if model.transform_type == InfrahubKind.TRANSFORMEXTERNAL:
        return await _request_external_render(client=client, model=model)

    repo = await get_initialized_repo(
        client=client,
        repository_id=model.repository_id,
        name=model.repository_name,
        repository_kind=model.repository_kind,
        infrahub_branch_name=model.branch_name,
        commit=model.commit,
    )

    artifact, artifact_created = await define_artifact(model=model)

    severity = "info"
    artifact_result = ArtifactCheckResult()
    check_message = RENDER_FAILED_MESSAGE

    try:
        result = await repo.render_artifact(artifact=artifact, artifact_created=artifact_created, message=model)
        artifact_result = ArtifactCheckResult(
            changed=result.changed,
            checksum=result.checksum,
            artifact_id=result.artifact_id,
            storage_id=result.storage_id,
        )
        check_message = RENDER_SUCCEEDED_MESSAGE
        conclusion = ValidatorConclusion.SUCCESS

    # Check boundary: any render failure must be recorded as a failed artifact check, not crash the flow
    except Exception as exc:  # noqa: BLE001
        artifact.status.value = "Error"
        await artifact.save()
        severity = "critical"
        conclusion = ValidatorConclusion.FAILURE
        check_message += f": {exc!s}"

    await write_artifact_check(
        client=client,
        model=model,
        conclusion=conclusion,
        severity=severity,
        message=check_message,
        artifact_result=artifact_result,
    )
    return conclusion


async def _request_external_render(client: InfrahubClient, model: CheckArtifactCreate) -> CheckResult:
    artifact, _ = await define_artifact(model=model)
    artifact_result = ArtifactCheckResult(artifact_id=artifact.id)
    # The check is stored before the request is emitted so that the engine's reply always finds it.
    await write_artifact_check(
        client=client,
        model=model,
        conclusion=ValidatorConclusion.UNKNOWN,
        severity="info",
        message=WAITING_FOR_EXTERNAL_ENGINE_MESSAGE,
        artifact_result=artifact_result,
    )
    # Check boundary: a failure after the waiting check is stored must conclude it, or it stays unknown.
    try:
        request = await request_external_render(
            client=client,
            event_service=await get_event_service(),
            artifact=artifact,
            model=model,
            transformation_name=model.transformation_name,
            transformation_version=model.transformation_version,
            public_url=config.SETTINGS.main.public_url,
            max_event_size_bytes=get_current_settings().server.events.maximum_size_bytes,
        )
        error = request.error
    except Exception as exc:  # noqa: BLE001
        artifact.status.value = ArtifactStatus.ERROR.value
        await artifact.save()
        error = str(exc)
    if error is None:
        return CheckPending.PENDING

    await write_artifact_check(
        client=client,
        model=model,
        conclusion=ValidatorConclusion.FAILURE,
        severity="critical",
        message=f"{RENDER_FAILED_MESSAGE}: {error}",
        artifact_result=artifact_result,
    )
    return ValidatorConclusion.FAILURE


async def write_artifact_check(
    client: InfrahubClient,
    model: CheckArtifactCreate,
    conclusion: ValidatorConclusion,
    severity: str,
    message: str,
    artifact_result: ArtifactCheckResult,
) -> None:
    check_name = f"{model.artifact_name}: {model.target_name}"
    existing_check = await client.filters(
        kind=CoreArtifactCheck, validator__ids=[model.validator_id], name__value=check_name
    )

    if existing_check:
        check = existing_check[0]
        check.created_at.value = Timestamp().to_string()
        check.message.value = message
        check.conclusion.value = conclusion.value
        check.severity.value = severity
        check.changed.value = artifact_result.changed
        check.checksum.value = artifact_result.checksum
        check.artifact_id.value = artifact_result.artifact_id
        check.storage_id.value = artifact_result.storage_id
        await check.save()
        return

    check = await client.create(
        kind=CoreArtifactCheck,
        data={
            "name": check_name,
            "origin": model.repository_id,
            "kind": "ArtifactDefinition",
            "validator": model.validator_id,
            "created_at": Timestamp().to_string(),
            "message": message,
            "conclusion": conclusion.value,
            "severity": severity,
            "changed": artifact_result.changed,
            "checksum": artifact_result.checksum,
            "artifact_id": artifact_result.artifact_id,
            "storage_id": artifact_result.storage_id,
        },
    )
    await check.save()
