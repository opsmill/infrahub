from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from infrahub_sdk.protocols import CoreArtifact, CoreArtifactDefinition

from infrahub.auth import AccountSession, AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core import registry
from infrahub.core.constants import DiffAction, InfrahubKind
from infrahub.core.diff.artifacts.calculator import ArtifactDiffCalculator
from infrahub.core.diff.model.diff import ArtifactTarget, BranchDiffArtifact, BranchDiffArtifactStorage
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.git.models import RequestArtifactDefinitionGenerate
from infrahub.lock import InfrahubLockRegistry
from infrahub.workflows.catalogue import REQUEST_ARTIFACT_DEFINITION_GENERATE
from tests.constants import TestKind
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch.models import Branch
    from infrahub.core.protocols import CoreCheckDefinition, CoreReadOnlyRepository
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices
    from tests.conftest import TestHelper


class TestCreateReadOnlyRepository(TestInfrahubApp):
    def setup_method(self) -> None:
        lock_patcher = patch("infrahub.git.tasks.lock")
        self.mock_infra_lock = lock_patcher.start()
        self.mock_infra_lock.registry = AsyncMock(spec=InfrahubLockRegistry)

    def teardown_method(self) -> None:
        patch.stopall()

    @pytest.fixture(scope="class")
    async def load_car_schema(self, db: InfrahubDatabase) -> None:
        await load_schema(db=db, schema=CAR_SCHEMA)

    @pytest.fixture(scope="class")
    async def context(self, db: InfrahubDatabase) -> InfrahubContext:
        """Placeholder context for now, would be good to implement some auth and permissions here"""
        admin_account = await NodeManager.get_one_by_hfid(
            db=db, kind=InfrahubKind.ACCOUNT, hfid=["admin"], raise_on_error=True
        )

        return InfrahubContext(
            account=AccountSession(authenticated=True, account_id=admin_account.id, auth_type=AuthType.API),
            branch=BranchContext(name="main", id="d18808fe-70c8-4782-bd55-144d6980036f"),
        )

    @pytest.fixture(scope="class")
    async def person_john(self, db: InfrahubDatabase, load_car_schema: None) -> Node:
        john = await Node.init(schema=TestKind.PERSON, db=db)
        await john.new(db=db, name="John", height=175, age=25)
        await john.save(db=db)
        return john

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        git_repos_source_dir_module_scope: Path,
        load_car_schema: None,
        person_john: Node,
    ) -> None:
        FileRepo(name="car-dealership", sources_directory=git_repos_source_dir_module_scope)
        people = await Node.init(schema=InfrahubKind.STANDARDGROUP, db=db)
        await people.new(db=db, name="people", members=[person_john])
        await people.save(db=db)

    async def test_step01_create_repository(
        self,
        db: InfrahubDatabase,
        initial_dataset: None,
        git_repos_source_dir_module_scope: Path,
        client: InfrahubClient,
    ) -> None:
        branch = await client.branch.create(branch_name="ro_repository", sync_with_git=False)

        client_repository = await client.create(
            kind=InfrahubKind.READONLYREPOSITORY,
            branch=branch.name,
            name="car-dealership",
            location=f"{git_repos_source_dir_module_scope}/car-dealership",
            ref="main",
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
        self, db: InfrahubDatabase, default_branch: Branch, client: InfrahubClient, person_john: Node
    ) -> None:
        artifacts = await client.all(kind=CoreArtifact, branch="ro_repository")
        artifacts_dict = {item.name.value: item for item in artifacts}
        assert sorted(artifacts_dict.keys()) == [
            "car-converted-owner",
            "car-name",
            "car-owner",
            "car-owner-yaml",
            "car-spec-markdown",
        ]
        john_display_label = await person_john.get_display_label(db=db)

        artifact_diff_calculator = ArtifactDiffCalculator(db=db)
        branch = await registry.get_branch(db=db, branch="ro_repository")
        diffs = await artifact_diff_calculator.calculate(source_branch=branch, target_branch=default_branch)
        diffs_dict = {str(item.display_label): item for item in diffs}
        assert sorted(diffs_dict.keys()) == [
            "John - car-converted-owner",
            "John - car-name",
            "John - car-owner",
            "John - car-owner-yaml",
            "John - car-spec-markdown",
        ]
        assert diffs_dict["John - car-owner"] == BranchDiffArtifact(
            branch="ro_repository",
            id=artifacts_dict["car-owner"].id,
            display_label=f"{john_display_label} - car-owner",
            action=DiffAction.ADDED,
            target=ArtifactTarget(id=person_john.id, kind="TestingPerson", display_label=john_display_label),
            item_new=BranchDiffArtifactStorage(
                storage_id=str(artifacts_dict["car-owner"].storage_id.value),
                checksum=str(artifacts_dict["car-owner"].checksum.value),
            ),
            item_previous=None,
        )

    async def test_step03_merge_branch(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        helper: TestHelper,
        context: InfrahubContext,
        service: InfrahubServices,
    ) -> None:
        await client.branch.merge(branch_name="ro_repository")

        check_definition: CoreCheckDefinition = await NodeManager.get_one_by_id_or_default_filter(
            db=db, id="car_description_check", kind=InfrahubKind.CHECKDEFINITION
        )
        assert check_definition.file_path.value == "checks/car_overview.py"

        artifact_definitions = await client.all(kind=CoreArtifactDefinition)

        for artifact_definition in artifact_definitions:
            model = RequestArtifactDefinitionGenerate(
                branch="main",
                artifact_definition_id=artifact_definition.id,
                artifact_definition_name=artifact_definition.name.value,
            )
            await service.workflow.submit_workflow(
                REQUEST_ARTIFACT_DEFINITION_GENERATE, context=context, parameters={"model": model}
            )

        artifacts = await client.all(kind=CoreArtifact)
        assert sorted([artifact.name.value for artifact in artifacts]) == [
            "car-converted-owner",
            "car-name",
            "car-owner",
            "car-owner-yaml",
            "car-spec-markdown",
        ]

    async def test_step04_new_branch_with_artifact(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        helper: TestHelper,
        person_john: Node,
        context: InfrahubContext,
        service: InfrahubServices,
    ) -> None:
        from infrahub.core import registry
        from infrahub.core.diff.artifacts.calculator import ArtifactDiffCalculator

        await client.branch.create(branch_name="branch", sync_with_git=False)
        branch = await registry.get_branch(db=db, branch="branch")

        manufacturer = await Node.init(schema=TestKind.MANUFACTURER, db=db, branch=branch)
        await manufacturer.new(db=db, name="Car builder")
        await manufacturer.save(db=db)
        john_branch = await NodeManager.get_one(db=db, branch=branch, id=person_john.id)
        john_branch.name.value = "John2"
        await john_branch.save(db=db)
        john_display_label = await john_branch.get_display_label(db=db)

        artifact_definitions = await client.all(kind=CoreArtifactDefinition)

        for artifact_definition in artifact_definitions:
            model = RequestArtifactDefinitionGenerate(
                artifact_definition_id=artifact_definition.id,
                artifact_definition_name=artifact_definition.name.value,
                branch="branch",
            )
            await service.workflow.submit_workflow(
                REQUEST_ARTIFACT_DEFINITION_GENERATE, context=context, parameters={"model": model}
            )

        artifacts = await client.all(kind=CoreArtifact, branch="branch")
        artifacts_dict = {item.name.value: item for item in artifacts}
        assert sorted(artifacts_dict.keys()) == [
            "car-converted-owner",
            "car-name",
            "car-owner",
            "car-owner-yaml",
            "car-spec-markdown",
        ]
        artifact_main = await NodeManager.get_one(db=db, id=artifacts_dict["car-owner"].id)

        artifact_diff_calculator = ArtifactDiffCalculator(db=db)
        diffs = await artifact_diff_calculator.calculate(source_branch=branch, target_branch=default_branch)
        diffs_dict = {str(item.display_label): item for item in diffs}
        assert sorted(diffs_dict.keys()) == [
            "John2 - car-converted-owner",
            "John2 - car-name",
            "John2 - car-owner",
            "John2 - car-owner-yaml",
        ]
        assert diffs_dict["John2 - car-owner"] == BranchDiffArtifact(
            branch="branch",
            id=artifacts_dict["car-owner"].id,
            display_label=f"{john_display_label} - car-owner",
            action=DiffAction.UPDATED,
            target=ArtifactTarget(id=person_john.id, kind="TestingPerson", display_label=john_display_label),
            item_new=BranchDiffArtifactStorage(
                storage_id=str(artifacts_dict["car-owner"].storage_id.value),
                checksum=str(artifacts_dict["car-owner"].checksum.value),
            ),
            item_previous=BranchDiffArtifactStorage(
                storage_id=artifact_main.storage_id.value, checksum=artifact_main.checksum.value
            ),
        )
