from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.api.storage import encryption_migration
from infrahub.storage_encryption.artifact_values import ArtifactValuesResult

if TYPE_CHECKING:
    from infrahub.storage_encryption.migrate import EncryptResult


@pytest.fixture(autouse=True)
def artifact_value_requests(monkeypatch: pytest.MonkeyPatch) -> list[list[EncryptResult]]:
    """Record the results that a route hands to the artifact step, which these tests run without a database."""
    requests: list[list[EncryptResult]] = []

    async def record(*, results: list[EncryptResult], **_: object) -> ArtifactValuesResult:
        requests.append(results)
        return ArtifactValuesResult()

    monkeypatch.setattr(encryption_migration, "store_encrypted_artifact_values", record)
    return requests
