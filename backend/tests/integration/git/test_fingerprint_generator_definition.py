from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.protocols import CoreGeneratorDefinition

from tests.integration.git.fingerprint_base import FingerprintImportTestBase

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from tests.helpers.file_repo import FileRepo

CARTAGS_QUERY_EDITED = """
query CarOwner($name: String!) {
  TestingPerson(name__value: $name) {
    edges {
      node {
        __typename
        id
        name {
          value
        }
      }
    }
  }
}
"""


class TestFingerprintGeneratorDefinition(FingerprintImportTestBase):
    async def test_import_sets_non_null_fingerprint(self, repository_id: str, client: InfrahubClient) -> None:
        generator_defs = await client.all(kind=CoreGeneratorDefinition)
        assert generator_defs
        for generator_def in generator_defs:
            assert generator_def.fingerprint.value

    async def test_reimport_leaves_fingerprint_unchanged(self, repository_id: str, client: InfrahubClient) -> None:
        before = (await client.get(kind=CoreGeneratorDefinition, name__value="cartags")).fingerprint.value
        await self._reimport_current_commit(client=client, repository_id=repository_id)
        after = (await client.get(kind=CoreGeneratorDefinition, name__value="cartags")).fingerprint.value
        assert before == after

    async def test_connected_query_edit_changes_fingerprint(
        self, repository_id: str, client: InfrahubClient, file_repo: FileRepo
    ) -> None:
        before = (await client.get(kind=CoreGeneratorDefinition, name__value="cartags")).fingerprint.value
        await self._commit_edit_and_reimport(
            client=client,
            repository_id=repository_id,
            file_repo=file_repo,
            edits={"generators/cartags.gql": CARTAGS_QUERY_EDITED},
        )
        after = (await client.get(kind=CoreGeneratorDefinition, name__value="cartags")).fingerprint.value
        assert before != after
