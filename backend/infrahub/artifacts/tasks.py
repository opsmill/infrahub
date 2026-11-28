from __future__ import annotations

from typing import TYPE_CHECKING

from prefect import flow, get_run_logger

from infrahub.artifacts.checks import artifact_check_name, save_artifact_check
from infrahub.artifacts.models import CheckArtifactCreate  # noqa: TC001  needed for prefect flow
from infrahub.artifacts.repositories import get_artifact_repositories
from infrahub.core.constants import Severity, ValidatorConclusion
from infrahub.tasks.artifact import define_artifact
from infrahub.workers.dependencies import get_client
from infrahub.workflows.utils import add_tags

if TYPE_CHECKING:
    from infrahub_sdk.protocols import CoreArtifact


@flow(name="git-repository-check-artifact-create", flow_run_name="Check artifact creation")
async def create(model: CheckArtifactCreate) -> ValidatorConclusion:
    await add_tags(branches=[model.branch_name], nodes=[model.target_id])

    client = get_client()
    client.request_context = model.context.to_request_context()
    repositories = get_artifact_repositories()
    log = get_run_logger()

    check = await save_artifact_check(
        client=client,
        validator_id=model.validator_id,
        check_id=model.check_id,
        artifact_id=model.artifact_id,
        name=artifact_check_name(artifact_name=model.artifact_name, target_name=model.target_name),
        origin=model.repository_id,
        conclusion=ValidatorConclusion.UNKNOWN,
        severity=Severity.INFO,
        message="Rendering artifact",
    )

    artifact: CoreArtifact | None = None
    try:
        repo = await repositories.open(client=client, model=model)
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
        check.severity.value = Severity.CRITICAL.value
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

    return conclusion
