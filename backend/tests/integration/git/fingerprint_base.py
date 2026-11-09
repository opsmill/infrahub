from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.git import InfrahubRepository
from infrahub.git.repository import get_initialized_repo
from tests.constants import TestKind
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase


class FingerprintImportTestBase(TestInfrahubApp):
    """Shared setup for import-and-store fingerprint scenarios over the car-dealership fixture.

    A repository is created and imported through the standard flow; helpers advance the
    source repository by a commit and re-import so change scenarios exercise the real path.
    """

    @pytest.fixture(scope="class")
    def file_repo(self, git_repos_source_dir_module_scope: Path) -> FileRepo:
        return FileRepo(name="car-dealership", sources_directory=git_repos_source_dir_module_scope)

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        file_repo: FileRepo,
    ) -> None:
        await load_schema(db, schema=CAR_SCHEMA)
        john = await Node.init(schema=TestKind.PERSON, db=db)
        await john.new(db=db, name="John", height=175, age=25)
        await john.save(db=db)
        people = await Node.init(schema=InfrahubKind.STANDARDGROUP, db=db)
        await people.new(db=db, name="people", members=[john])
        await people.save(db=db)

    @pytest.fixture(scope="class")
    async def repository_id(
        self,
        initial_dataset: None,
        git_repos_source_dir_module_scope: Path,
        client: InfrahubClient,
    ) -> str:
        client_repository = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={"name": "car-dealership", "location": f"{git_repos_source_dir_module_scope}/car-dealership"},
        )
        await client_repository.save()
        return client_repository.id

    async def _initialized_repo(self, client: InfrahubClient, repository_id: str) -> InfrahubRepository:
        repo = await get_initialized_repo(
            client=client,
            repository_id=repository_id,
            name="car-dealership",
            repository_kind=InfrahubKind.REPOSITORY,
        )
        assert isinstance(repo, InfrahubRepository)
        return repo

    async def _reimport_current_commit(self, client: InfrahubClient, repository_id: str) -> None:
        repo = await self._initialized_repo(client=client, repository_id=repository_id)
        commit = repo.get_commit_value(branch_name="main")
        await repo.import_objects_from_files(infrahub_branch_name="main", commit=commit)  # type: ignore[call-overload]

    async def _commit_edit_and_reimport(
        self, client: InfrahubClient, repository_id: str, file_repo: FileRepo, edits: dict[str, str]
    ) -> str:
        source = Path(file_repo.path)
        for relative_path, content in edits.items():
            target = source / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        file_repo.repo.git.add(".")
        file_repo.repo.index.commit("edit")

        repo = await self._initialized_repo(client=client, repository_id=repository_id)
        new_commit = await repo.pull(branch_name="main")
        assert isinstance(new_commit, str)
        await repo.import_objects_from_files(infrahub_branch_name="main", commit=new_commit)  # type: ignore[call-overload]
        return new_commit
