from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.protocols import CoreArtifactDefinition

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from tests.constants import TestKind
from tests.integration.git.fingerprint_base import FingerprintImportTestBase

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase


class TestFingerprintArtifactDefinition(FingerprintImportTestBase):
    async def test_import_sets_non_null_fingerprint(self, repository_id: str, client: InfrahubClient) -> None:
        artifact_defs = await client.all(kind=CoreArtifactDefinition)
        assert artifact_defs
        for artifact_def in artifact_defs:
            assert artifact_def.fingerprint.value

    async def test_reimport_leaves_fingerprint_unchanged(self, repository_id: str, client: InfrahubClient) -> None:
        before = (await client.get(kind=CoreArtifactDefinition, name__value="name report")).fingerprint.value
        await self._reimport_current_commit(client=client, repository_id=repository_id)
        after = (await client.get(kind=CoreArtifactDefinition, name__value="name report")).fingerprint.value
        assert before == after

    async def test_group_membership_churn_leaves_fingerprint_unchanged(
        self, repository_id: str, client: InfrahubClient, db: InfrahubDatabase
    ) -> None:
        before = (await client.get(kind=CoreArtifactDefinition, name__value="name report")).fingerprint.value

        # Adding a member to the target group is membership churn: the group identity is
        # unchanged, so the fingerprint must not move.
        newcomer = await Node.init(schema=TestKind.PERSON, db=db)
        await newcomer.new(db=db, name="Jane", height=165, age=30)
        await newcomer.save(db=db)
        people = await client.get(kind=InfrahubKind.STANDARDGROUP, name__value="people")
        await people.members.fetch()
        people.members.add(newcomer.id)
        await people.save()

        await self._reimport_current_commit(client=client, repository_id=repository_id)

        after = (await client.get(kind=CoreArtifactDefinition, name__value="name report")).fingerprint.value
        assert before == after
