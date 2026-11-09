from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.protocols import CoreArtifactDefinition, CoreGraphQLQuery

from tests.integration.git.fingerprint_base import FingerprintImportTestBase

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from tests.helpers.file_repo import FileRepo

# The person_with_cars query drives the person_with_cars transform, which the
# "Ownership report" artifact definition composes over. The edit adds a scalar field
# (keeping the selections the artifact template renders) so the stored text changes
# without breaking regeneration.
PERSON_WITH_CARS_QUERY_EDITED = """
query PersonWithTheirCars($name: String!) {
  TestingPerson(name__value: $name) {
    edges {
      node {
        id
        __typename
        name {
          value
        }
        height {
          value
        }
        age {
          value
        }
        cars {
          edges {
            node {
              id
              __typename
              name {
                value
              }
            }
          }
        }
      }
    }
  }
}
"""


class TestFingerprintSnapshot(FingerprintImportTestBase):
    async def test_query_edit_propagates_to_dependent_artifact_definition_same_import(
        self, repository_id: str, client: InfrahubClient, file_repo: FileRepo
    ) -> None:
        """Editing a query updates the dependent artifact-definition fingerprint in the same import.

        A one-import lag would leave the artifact definition composing the previously-stored
        query fingerprint; the in-import registry rules that out.
        """
        query_before = (await client.get(kind=CoreGraphQLQuery, name__value="person_with_cars")).fingerprint.value
        artifact_before = (
            await client.get(kind=CoreArtifactDefinition, name__value="Ownership report")
        ).fingerprint.value

        await self._commit_edit_and_reimport(
            client=client,
            repository_id=repository_id,
            file_repo=file_repo,
            edits={"templates/person_with_cars.gql": PERSON_WITH_CARS_QUERY_EDITED},
        )

        query_after = (await client.get(kind=CoreGraphQLQuery, name__value="person_with_cars")).fingerprint.value
        artifact_after = (
            await client.get(kind=CoreArtifactDefinition, name__value="Ownership report")
        ).fingerprint.value

        assert query_before != query_after
        assert artifact_before != artifact_after
