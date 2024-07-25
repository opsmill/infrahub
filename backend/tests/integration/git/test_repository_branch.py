from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import InfrahubKind, RepositoryAdminStatus
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from tests.constants import TestKind
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.core.protocols import CoreCheckDefinition, CoreRepository
    from infrahub.database import InfrahubDatabase

BRANCH_NAME = "branch2"


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
    ) -> None:
        branch = await client.branch.create(branch_name=BRANCH_NAME)

        """Validate that we can create a repository, that it gets updated with the commit id and that objects are created."""
        client_repository = await client.create(
            kind=InfrahubKind.REPOSITORY,
            branch=branch.name,
            data={"name": "car-dealership", "location": f"{git_repos_source_dir_module_scope}/car-dealership"},
        )
        await client_repository.save()

        repository_branch: CoreRepository = await NodeManager.get_one(
            db=db, id=client_repository.id, kind=InfrahubKind.REPOSITORY, branch=branch.name, raise_on_error=True
        )

        check_definition: CoreCheckDefinition = await NodeManager.get_one_by_default_filter(
            db=db,
            id="car_description_check",
            kind=InfrahubKind.CHECKDEFINITION,
            branch=branch.name,
            raise_on_error=True,
        )

        assert repository_branch.commit.value
        assert repository_branch.admin_status.value == RepositoryAdminStatus.STAGING.value
        assert check_definition.file_path.value == "checks/car_overview.py"

        repository_main: CoreRepository = await NodeManager.get_one(
            db=db, id=client_repository.id, kind=InfrahubKind.REPOSITORY, raise_on_error=True
        )

        assert repository_main.commit.value is None
        assert repository_main.admin_status.value == RepositoryAdminStatus.INACTIVE.value

    async def test_merge_branch(
        self,
        db: InfrahubDatabase,
        initial_dataset: None,
        git_repos_source_dir_module_scope: Path,
        client: InfrahubClient,
    ) -> None:
        await client.branch.merge(branch_name=BRANCH_NAME)

        repository_branch: CoreRepository = await NodeManager.get_one_by_default_filter(
            db=db, id="car-dealership", kind=InfrahubKind.REPOSITORY, branch=BRANCH_NAME, raise_on_error=True
        )

        repository_main: CoreRepository = await NodeManager.get_one_by_default_filter(
            db=db, id="car-dealership", kind=InfrahubKind.REPOSITORY, raise_on_error=True
        )

        assert repository_main.admin_status.value == RepositoryAdminStatus.ACTIVE.value
        assert repository_main.commit.value == repository_branch.commit.value
