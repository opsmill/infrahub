from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from tests.constants import TestKind
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase


class TestCreateRepository(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_dir_module_scope: str,
        git_repos_source_dir_module_scope: str,
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
        git_repos_source_dir_module_scope: str,
        client: InfrahubClient,
    ) -> None:
        """Validate that we can create a repository, that it gets updated with the commit id and that objects are created."""
        client_repository = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={"name": "car-dealership", "location": f"{git_repos_source_dir_module_scope}/car-dealership"},
        )
        await client_repository.save()

        repository = await NodeManager.get_one_by_id_or_default_filter(
            db=db, id=client_repository.id, schema_name=InfrahubKind.REPOSITORY
        )

        check_definition = await NodeManager.get_one_by_id_or_default_filter(
            db=db, id="car_description_check", schema_name=InfrahubKind.CHECKDEFINITION
        )

        assert repository.commit.value  # type: ignore[attr-defined]
        assert check_definition.file_path.value == "checks/car_overview.py"  # type: ignore[attr-defined]
