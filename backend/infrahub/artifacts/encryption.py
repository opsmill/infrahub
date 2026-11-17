from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

import httpx
from infrahub_sdk.exceptions import Error as SdkError

from infrahub.branch.status_checker import BranchStatusChecker
from infrahub.core import registry
from infrahub.core.account import ObjectPermission
from infrahub.core.constants import GLOBAL_BRANCH_NAME, ArtifactEncryption, PermissionAction
from infrahub.exceptions import BranchStatusError
from infrahub.log import get_logger
from infrahub.permissions.constants import PermissionDecisionFlag

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.merge.write_blocker import MergeWriteBlocker
    from infrahub.core.protocols import CoreArtifact
    from infrahub.database import InfrahubDatabase
    from infrahub.permissions import PermissionManager

log = get_logger()


async def record_artifact_encryption(*, sdk: InfrahubClient, artifact_id: str, branch_name: str) -> None:
    """Have the API server check the stored file of an artifact and store the result on the artifact.

    The encryption of an artifact is read-only for clients, so the API server is the only one that writes it. A
    failed request leaves the stored value as it was, and the next check of the artifact corrects it.
    """
    url = f"{sdk.address}/api/artifact/{artifact_id}/encryption?branch={quote(branch_name, safe='')}"
    try:
        response = await sdk._post(
            url=url, payload={}, headers=sdk._request_headers(tracker="artifact-encryption-check")
        )
        response.raise_for_status()
    except (httpx.HTTPStatusError, SdkError) as exc:
        log.warning("Could not record the encryption of an artifact", artifact_id=artifact_id, error=str(exc))


def stored_encryption(artifact: CoreArtifact) -> ArtifactEncryption:
    """Return the encryption value stored on an artifact, `plaintext` when it has none."""
    return (
        ArtifactEncryption(artifact.encryption.value.value)
        if artifact.encryption.value
        else ArtifactEncryption.PLAINTEXT
    )


async def store_artifact_encryption(
    *, db: InfrahubDatabase, artifact: CoreArtifact, found: ArtifactEncryption, user_id: str
) -> bool:
    """Store `found` on the artifact when it differs from the stored value, and return whether it was written."""
    if found == stored_encryption(artifact):
        return False
    artifact.get_attribute("encryption").value = found.value
    await artifact.save(db=db, user_id=user_id, fields=["encryption"])
    return True


async def may_store_artifact_encryption(
    *,
    db: InfrahubDatabase,
    branch: Branch,
    permission_manager: PermissionManager,
    merge_write_blocker: MergeWriteBlocker,
) -> bool:
    """Whether the caller may update artifacts on the branch and the branch accepts writes."""
    permission_decision = (
        PermissionDecisionFlag.ALLOW_DEFAULT
        if branch.name in (GLOBAL_BRANCH_NAME, registry.default_branch)
        else PermissionDecisionFlag.ALLOW_OTHER
    )
    permission = ObjectPermission(
        namespace="Core",
        name="Artifact",
        action=PermissionAction.UPDATE.value,
        decision=permission_decision,
    )
    if not permission_manager.has_permission(permission=permission):
        return False
    try:
        await BranchStatusChecker(db=db, merge_write_blocker=merge_write_blocker).check(branch=branch)
    except BranchStatusError:
        return False
    return True
