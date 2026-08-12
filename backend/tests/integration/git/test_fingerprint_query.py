from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.protocols import CoreGraphQLQuery

from tests.integration.git.fingerprint_base import FingerprintImportTestBase

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from tests.helpers.file_repo import FileRepo

# A valid variant of the cartags query that drops the nested cars selection, so the stored
# fragment-inlined text differs while the query stays importable.
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


class TestFingerprintQuery(FingerprintImportTestBase):
    async def test_import_sets_non_null_fingerprint(self, repository_id: str, client: InfrahubClient) -> None:
        queries = await client.all(kind=CoreGraphQLQuery)
        assert queries
        for query in queries:
            assert query.fingerprint.value

    async def test_reimport_leaves_fingerprint_unchanged(self, repository_id: str, client: InfrahubClient) -> None:
        before = (await client.get(kind=CoreGraphQLQuery, name__value="cartags")).fingerprint.value
        await self._reimport_current_commit(client=client, repository_id=repository_id)
        after = (await client.get(kind=CoreGraphQLQuery, name__value="cartags")).fingerprint.value
        assert before == after

    async def test_query_text_edit_changes_fingerprint(
        self, repository_id: str, client: InfrahubClient, file_repo: FileRepo
    ) -> None:
        before = (await client.get(kind=CoreGraphQLQuery, name__value="cartags")).fingerprint.value
        await self._commit_edit_and_reimport(
            client=client,
            repository_id=repository_id,
            file_repo=file_repo,
            edits={"generators/cartags.gql": CARTAGS_QUERY_EDITED},
        )
        after = (await client.get(kind=CoreGraphQLQuery, name__value="cartags")).fingerprint.value
        assert before != after

    async def test_unrelated_file_edit_leaves_fingerprint_unchanged(
        self, repository_id: str, client: InfrahubClient, file_repo: FileRepo
    ) -> None:
        before = (await client.get(kind=CoreGraphQLQuery, name__value="car_overview")).fingerprint.value
        await self._commit_edit_and_reimport(
            client=client,
            repository_id=repository_id,
            file_repo=file_repo,
            edits={"unrelated_note.md": "a file no query depends on"},
        )
        after = (await client.get(kind=CoreGraphQLQuery, name__value="car_overview")).fingerprint.value
        assert before == after
