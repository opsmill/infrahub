from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from infrahub_sdk.protocols import CoreTransformJinja2, CoreTransformPython

from tests.integration.git.fingerprint_base import FingerprintImportTestBase

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from tests.helpers.file_repo import FileRepo


class TestFingerprintTransformation(FingerprintImportTestBase):
    async def test_import_sets_non_null_fingerprint(self, repository_id: str, client: InfrahubClient) -> None:
        python_transforms = await client.all(kind=CoreTransformPython)
        jinja2_transforms = await client.all(kind=CoreTransformJinja2)
        assert python_transforms
        assert jinja2_transforms
        for transform in [*python_transforms, *jinja2_transforms]:
            assert transform.fingerprint.value

    async def test_reimport_leaves_fingerprint_unchanged(self, repository_id: str, client: InfrahubClient) -> None:
        before = (await client.get(kind=CoreTransformPython, name__value="CarSpecMarkdown")).fingerprint.value
        await self._reimport_current_commit(client=client, repository_id=repository_id)
        after = (await client.get(kind=CoreTransformPython, name__value="CarSpecMarkdown")).fingerprint.value
        assert before == after

    async def test_own_source_edit_changes_fingerprint(
        self, repository_id: str, client: InfrahubClient, file_repo: FileRepo
    ) -> None:
        before = (await client.get(kind=CoreTransformPython, name__value="CarSpecMarkdown")).fingerprint.value
        await self._commit_edit_and_reimport(
            client=client,
            repository_id=repository_id,
            file_repo=file_repo,
            edits={"transforms/car_spec_markdown.py": _append_comment("transforms/car_spec_markdown.py", file_repo)},
        )
        after = (await client.get(kind=CoreTransformPython, name__value="CarSpecMarkdown")).fingerprint.value
        assert before != after

    async def test_connected_query_edit_changes_transformation_fingerprint(
        self, repository_id: str, client: InfrahubClient, file_repo: FileRepo
    ) -> None:
        before = (await client.get(kind=CoreTransformJinja2, name__value="person_with_cars")).fingerprint.value
        await self._commit_edit_and_reimport(
            client=client,
            repository_id=repository_id,
            file_repo=file_repo,
            edits={"templates/person_with_cars.gql": _PERSON_WITH_CARS_QUERY_EDITED},
        )
        after = (await client.get(kind=CoreTransformJinja2, name__value="person_with_cars")).fingerprint.value
        assert before != after


def _append_comment(relative_path: str, file_repo: FileRepo) -> str:
    current = (Path(file_repo.path) / relative_path).read_text(encoding="utf-8")
    return current + "\n# fingerprint change marker\n"


_PERSON_WITH_CARS_QUERY_EDITED = """
query PersonWithTheirCars($name: String!) {
  TestingPerson(name__value: $name) {
    edges {
      node {
        id
        __typename
        name {
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
