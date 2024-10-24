from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.lock import InfrahubLockRegistry
from infrahub.message_bus.messages import RequestArtifactDefinitionGenerate
from infrahub.services import services
from tests.constants import TestKind
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.core.protocols import CoreCheckDefinition, CoreReadOnlyRepository
    from infrahub.database import InfrahubDatabase
    from tests.conftest import TestHelper


class TestCreateReadOnlyRepository(TestInfrahubApp):
    def setup_method(self):
        lock_patcher = patch("infrahub.message_bus.operations.git.repository.lock")
        self.mock_infra_lock = lock_patcher.start()
        self.mock_infra_lock.registry = AsyncMock(spec=InfrahubLockRegistry)

    def teardown_method(self):
        patch.stopall()

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

    async def test_step01_create_repository(
        self,
        db: InfrahubDatabase,
        initial_dataset: None,
        git_repos_source_dir_module_scope: Path,
        client: InfrahubClient,
        set_service_client,
    ) -> None:
        branch = await client.branch.create(branch_name="ro_repository", sync_with_git=False)

        client_repository = await client.create(
            kind=InfrahubKind.READONLYREPOSITORY,
            branch=branch.name,
            data={
                "name": "car-dealership",
                "location": f"{git_repos_source_dir_module_scope}/car-dealership",
                "ref": "main",
            },
        )
        await client_repository.save()

        repository: CoreReadOnlyRepository = await NodeManager.get_one_by_id_or_default_filter(
            db=db, id=client_repository.id, kind=InfrahubKind.READONLYREPOSITORY, branch=branch.name
        )

        check_definition = await NodeManager.get_one_by_id_or_default_filter(
            db=db, id="car_description_check", kind=InfrahubKind.CHECKDEFINITION, branch=branch.name
        )

        assert repository.commit.value
        assert check_definition.file_path.value == "checks/car_overview.py"

    async def test_step02_validate_generated_artifacts(
        self, db: InfrahubDatabase, client: InfrahubClient, set_service_client
    ):
        artifacts = await client.all(kind=InfrahubKind.ARTIFACT, branch="ro_repository")
        assert artifacts
        assert artifacts[0].name.value == "Ownership report"

    async def test_step03_merge_branch(
        self, db: InfrahubDatabase, client: InfrahubClient, helper: TestHelper, set_service_client
    ):
        await client.branch.merge(branch_name="ro_repository")

        check_definition: CoreCheckDefinition = await NodeManager.get_one_by_id_or_default_filter(
            db=db, id="car_description_check", kind=InfrahubKind.CHECKDEFINITION
        )
        assert check_definition.file_path.value == "checks/car_overview.py"

        artifact_definitions = await client.all(kind=InfrahubKind.ARTIFACTDEFINITION)

        for artifact_definition in artifact_definitions:
            await services.service.send(
                message=RequestArtifactDefinitionGenerate(artifact_definition=artifact_definition.id, branch="main")
            )

        artifacts = await client.all(kind=InfrahubKind.ARTIFACT)
        assert artifacts
        assert artifacts[0].name.value == "Ownership report"
