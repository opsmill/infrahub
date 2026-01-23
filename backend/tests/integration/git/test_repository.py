from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from git import GitCommandError

from infrahub.core.constants import InfrahubKind, RepositoryOperationalStatus
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.exceptions import CommitNotFoundError, RepositoryError
from infrahub.git.repository import get_initialized_repo
from tests.constants import TestKind
from tests.helpers.file_repo import FileRepo, MultipleStagesFileRepo
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp
from tests.integration.git.utils import check_repo_correctly_created

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreCheckDefinition, CoreRepository
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices


class TestCreateRepository(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        git_repos_source_dir_module_scope: Path,
    ) -> None:
        await load_schema(db, schema=CAR_SCHEMA)
        FileRepo(name="car-dealership", sources_directory=git_repos_source_dir_module_scope)
        john = await Node.init(schema=TestKind.PERSON, db=db)
        await john.new(db=db, name="John", height=175, age=25)
        await john.save(db=db)
        people = await Node.init(schema=InfrahubKind.STANDARDGROUP, db=db)
        await people.new(db=db, name="people", members=[john])
        await people.save(db=db)

    async def test_create_repository(
        self,
        db: InfrahubDatabase,
        initial_dataset: None,
        git_repos_source_dir_module_scope: Path,
        client: InfrahubClient,
        default_branch: Branch,
    ) -> None:
        """Validate that we can create a repository, that it gets updated with the commit id and that objects are created."""
        client_repository = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={"name": "car-dealership", "location": f"{git_repos_source_dir_module_scope}/car-dealership"},
        )
        await client_repository.save()

        repository: CoreRepository = await NodeManager.get_one(
            db=db,
            id=client_repository.id,
            kind=InfrahubKind.REPOSITORY,
            raise_on_error=True,
        )
        check_definition: CoreCheckDefinition = await NodeManager.get_one_by_default_filter(
            db=db,
            id="car_description_check",
            kind=InfrahubKind.CHECKDEFINITION,
            raise_on_error=True,
        )
        assert repository.commit.value
        assert repository.internal_status.value == "active", f"{repository.internal_status.value=}"
        assert repository.operational_status.value == "online"
        assert check_definition.file_path.value == "checks/car_overview.py"

        await check_repo_correctly_created(repo_id=client_repository.id, db=db, branch_name=default_branch.name)

    @pytest.mark.parametrize(
        ("stderr", "expected_operational_status"),
        [
            ("Repository not found", RepositoryOperationalStatus.ERROR_CONNECTION),
            ("error: pathspec", RepositoryOperationalStatus.ERROR),
            ("SSL certificate problem", RepositoryOperationalStatus.ERROR_CONNECTION),
            ("authentication failed for", RepositoryOperationalStatus.ERROR_CRED),
            ("Need to specify how to reconcile", RepositoryOperationalStatus.ERROR),
            ("fatal: could not read Username for | terminal prompts disable", RepositoryOperationalStatus.ERROR_CRED),
        ],
    )
    async def test_repository_operational_status(
        self,
        db: InfrahubDatabase,
        initial_dataset: None,
        git_repos_source_dir_module_scope: Path,
        client: InfrahubClient,
        stderr: str,
        expected_operational_status: RepositoryOperationalStatus,
        service: InfrahubServices,
    ) -> None:
        """Validate that we can create a repository, that it gets updated with the commit id and that objects are created."""
        client_repository = await client.get(kind=InfrahubKind.REPOSITORY, name__value="car-dealership")
        repository: CoreRepository = await NodeManager.get_one(
            db=db, id=client_repository.id, kind=InfrahubKind.REPOSITORY, raise_on_error=True
        )

        assert repository.commit.value

        infrahub_repo = await get_initialized_repo(
            client=client,
            repository_id=repository.id,
            name=repository.name.value,
            repository_kind=InfrahubKind.REPOSITORY,
        )

        with patch("git.remote.Remote.fetch", side_effect=GitCommandError("fetch", stderr=stderr)):
            try:
                await infrahub_repo.fetch()
            except RepositoryError:
                r: CoreRepository = await NodeManager.get_one(
                    db=db, id=client_repository.id, kind=InfrahubKind.REPOSITORY, raise_on_error=True
                )
                assert r.operational_status.value == expected_operational_status.value


class TestRepositoryChangedFiles(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        tmp_path_module_scope: Path,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        git_repos_source_dir_module_scope: Path,
    ) -> None:
        source_dir = tmp_path_module_scope / "sources"
        source_dir.mkdir()
        file_repo = MultipleStagesFileRepo(name="changed-files", sources_directory=source_dir)

        obj = await Node.init(schema=InfrahubKind.REPOSITORY, db=db)
        await obj.new(
            db=db,
            name=file_repo.name,
            description="test repository",
            location=file_repo.path,
            commit=file_repo.repo.commit("main").hexsha,
        )
        await obj.save(db=db)

    async def test_get_changed_files(
        self,
        db: InfrahubDatabase,
        initial_dataset: None,
        git_repos_source_dir_module_scope: Path,
        client: InfrahubClient,
        service: InfrahubServices,
    ) -> None:
        """Validate that we can create a repository, that it gets updated with the commit id and that objects are created."""
        client_repository = await client.get(kind=InfrahubKind.REPOSITORY, name__value="changed-files")
        repository: CoreRepository = await NodeManager.get_one(
            db=db, id=client_repository.id, kind=InfrahubKind.REPOSITORY, raise_on_error=True
        )

        assert repository.commit.value

        infrahub_repo = await get_initialized_repo(
            client=client,
            repository_id=repository.id,
            name=repository.name.value,
            repository_kind=InfrahubKind.REPOSITORY,
        )

        # Have commits from oldest to youngest
        commits = list(reversed(list(infrahub_repo.get_git_repo_main().iter_commits())))
        assert len(commits) == 3

        diff_1_to_2 = infrahub_repo.get_changed_files(first_commit=commits[0].hexsha, second_commit=commits[1].hexsha)
        assert diff_1_to_2.modified == ["test.gql"]

        diff_2_to_3 = infrahub_repo.get_changed_files(first_commit=commits[1].hexsha, second_commit=commits[2].hexsha)
        assert diff_2_to_3.added == ["README.md"]

        diff_1_to_3 = infrahub_repo.get_changed_files(first_commit=commits[0].hexsha, second_commit=commits[2].hexsha)
        assert diff_1_to_3.added == ["README.md"]
        assert diff_1_to_3.modified == ["test.gql"]

        diff_1_to_head = infrahub_repo.get_changed_files(first_commit=commits[0].hexsha)
        assert diff_1_to_head.added == ["README.md"]
        assert diff_1_to_head.modified == ["test.gql"]

        with pytest.raises(CommitNotFoundError, match="Commit foo not found with GitRepository"):
            infrahub_repo.get_changed_files(first_commit="foo")
