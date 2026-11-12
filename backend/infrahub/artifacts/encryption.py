from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

import httpx
from infrahub_sdk.exceptions import Error as SdkError

from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

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
