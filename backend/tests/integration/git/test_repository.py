from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from git import GitCommandError

from infrahub.core.constants import InfrahubKind, RepositoryObjects, RepositoryOperationalStatus
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.exceptions import RepositoryError
from infrahub.git.repository import get_initialized_repo
from tests.constants import TestKind
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

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
    ) -> None:
        """Validate that we can create a repository, that it gets updated with the commit id and that objects are created."""
        client_repository = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={"name": "car-dealership", "location": f"{git_repos_source_dir_module_scope}/car-dealership"},
        )
        await client_repository.save()

        repository: CoreRepository = await NodeManager.get_one(
            db=db, id=client_repository.id, kind=InfrahubKind.REPOSITORY, raise_on_error=True
        )

        check_definition: CoreCheckDefinition = await NodeManager.get_one_by_default_filter(
            db=db, id="car_description_check", kind=InfrahubKind.CHECKDEFINITION, raise_on_error=True
        )

        assert repository.commit.value
        assert repository.internal_status.value == "active"
        assert repository.operational_status.value == "online"
        assert check_definition.file_path.value == "checks/car_overview.py"

        person_ethan = await NodeManager.get_one_by_default_filter(
            db=db, id="Ethan Carter", kind="TestingPerson", raise_on_error=True
        )
        assert person_ethan.name.value == "Ethan Carter"
        assert person_ethan.height.value == 180

        manufacturer_mercedes = await NodeManager.get_one_by_default_filter(
            db=db, id="Mercedes", kind="TestingManufacturer", raise_on_error=True, prefetch_relationships=True
        )
        assert manufacturer_mercedes.name.value == "Mercedes"
        assert list((await manufacturer_mercedes.customers.get_peers(db=db)).values())[0].name.value == "Ethan Carter"

        repository_group = await NodeManager.get_one_by_default_filter(
            db=db,
            id=f"group-repo-{RepositoryObjects.OBJECT.value}-{repository.id}",
            kind="CoreRepositoryGroup",
            raise_on_error=True,
            prefetch_relationships=True,
        )
        assert repository_group.content.value == RepositoryObjects.OBJECT.value
        members = (await repository_group.members.get_peers(db=db)).values()
        assert len(members) == 4
        assert manufacturer_mercedes.id in {m.id for m in members}
        assert person_ethan.id in {m.id for m in members}

        # TODO Retrieve menus

        repository_group_menus = await NodeManager.get_one_by_default_filter(
            db=db,
            id=f"group-repo-{RepositoryObjects.MENU.value}-{repository.id}",
            kind="CoreRepositoryGroup",
            raise_on_error=True,
            prefetch_relationships=True,
        )

        assert repository_group_menus.content.value == RepositoryObjects.MENU.value

        _ = await NodeManager.get_one_by_hfid(
            db=db,
            hfid=["Testing", "Manufacturer"],
            kind="CoreMenu",
            raise_on_error=True,
            prefetch_relationships=True,
        )

        _ = await NodeManager.get_one_by_hfid(
            db=db, hfid=["Testing", "Person"], kind="CoreMenu", raise_on_error=True, prefetch_relationships=True
        )

    # TODO add a test with invalid yml file OR invalid order of objects in the yml file, and make sure the repository ends
    # up in error import state

    @pytest.mark.parametrize(
        "stderr,expected_operational_status",
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
            repository_id=repository.id,
            name=repository.name.value,
            service=service,
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
