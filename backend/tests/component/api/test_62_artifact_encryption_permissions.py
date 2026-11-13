from __future__ import annotations

import hashlib
import io
from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.storage_encryption.crypto import StorageKey, seal
from tests.helpers.artifact import create_stored_artifact, stored_artifact_encryption
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from tests.helpers.test_client import InfrahubTestClient

ARTIFACT_ID = "0b9f9a8c-0000-4000-8000-0000000000a1"
ARTIFACT = b'{"hostname": "leaf01"}'
OTHER_KEY = StorageKey.derive("another-key-for-artifact-tests-0123456789")


class TestArtifactEncryptionPermissions(TestInfrahubApp):
    async def create_artifact_with_file_sealed_by_another_key(
        self, db: InfrahubDatabase, car_person_data_generic: dict[str, Node]
    ) -> Node:
        artifact = await create_stored_artifact(
            db=db,
            car_person_data_generic=car_person_data_generic,
            storage_id=ARTIFACT_ID,
            checksum=hashlib.md5(ARTIFACT, usedforsecurity=False).hexdigest(),
        )
        registry.storage.store(
            identifier=ARTIFACT_ID,
            content=io.BytesIO(seal(identifier=ARTIFACT_ID, content=ARTIFACT, key=OTHER_KEY)),
        )
        return artifact

    async def test_user_who_cannot_update_artifacts_gets_the_result_without_storing_it(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        register_builtin_models_schema: SchemaBranch,
        car_person_data_generic: dict[str, Node],
        authentication_base: Node,
        test_client: InfrahubTestClient,
        api_unprivileged_token: str,
        admin_headers: dict[str, str],
    ) -> None:
        artifact = await self.create_artifact_with_file_sealed_by_another_key(
            db=db, car_person_data_generic=car_person_data_generic
        )
        url = f"/api/artifact/{artifact.id}/encryption"

        unprivileged = await test_client.post(url, headers={"X-INFRAHUB-KEY": api_unprivileged_token})
        stored_after_unprivileged = await stored_artifact_encryption(db=db, artifact_id=artifact.id)
        admin = await test_client.post(url, headers=admin_headers)

        assert (unprivileged.status_code, unprivileged.json()) == (
            200,
            {"encryption": "unreadable", "reason": "unknown_key", "updated": False},
        )
        assert stored_after_unprivileged == "plaintext"
        assert (admin.status_code, admin.json()) == (
            200,
            {"encryption": "unreadable", "reason": "unknown_key", "updated": True},
        )
        assert await stored_artifact_encryption(db=db, artifact_id=artifact.id) == "unreadable"
