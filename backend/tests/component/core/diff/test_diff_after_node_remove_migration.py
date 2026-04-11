"""Test that the diff includes nodes deleted by a NodeRemoveMigration.

Reproduces a scenario where:
1. A node is created on the default branch
2. A branch is created
3. A different object is changed on the branch (so the diff has content)
4. A NodeRemoveMigration runs on the branch, deleting the node
5. The diff is updated
6. The deleted node should appear in the diff as REMOVED
"""

from unittest.mock import AsyncMock

import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction, SchemaPathType
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.node_remove import NodeRemoveMigration
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry


class TestDiffAfterNodeRemoveMigration:
    @pytest.fixture(autouse=True)
    async def _setup_core_schema(self, register_core_models_schema: SchemaBranch) -> None:
        return

    async def test_deleted_node_appears_in_diff(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_schema: SchemaBranch,
    ) -> None:
        # Step 1: Create a person on the default branch
        person = await Node.init(db=db, schema="TestPerson")
        await person.new(db=db, name="BluePerson", height=180)
        await person.save(db=db, user_id="test-user")

        # Step 2: Create a branch
        branch = await create_branch(db=db, branch_name="test-branch")

        # Step 3: Make an unrelated change on the branch (so the diff has content)
        # Update the person's height on the branch — but use a DIFFERENT person
        other_person = await Node.init(db=db, schema="TestPerson", branch=branch)
        await other_person.new(db=db, name="OtherPerson", height=160)
        await other_person.save(db=db, user_id="branch-user")

        # Step 4: Generate the initial diff
        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
        diff_coordinator.data_check_synchronizer = AsyncMock(spec=DiffDataCheckSynchronizer)
        diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=default_branch)

        enriched_diff_metadata = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=branch
        )

        # Verify person is NOT in the diff yet (it was created on main, not changed on branch)
        enriched_diff = await diff_repository.get_one(
            diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
        )
        person_in_diff = [n for n in enriched_diff.nodes if n.uuid == person.id]
        assert len(person_in_diff) == 0, "Person should not be in the diff before migration"

        # Step 5: Run NodeRemoveMigration on the branch to delete TestPerson nodes
        person_schema = car_person_schema.get(name="TestPerson")
        migration = NodeRemoveMigration(
            previous_node_schema=person_schema,
            new_node_schema=None,
            schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestPerson"),
        )
        migration_at = Timestamp()
        result = await migration.execute(
            migration_input=MigrationInput(db=db, at=migration_at, user_id="migration-user"),
            branch=branch,
        )
        assert result.success, f"Migration failed: {result.errors}"

        # Verify person is deleted on the branch
        person_on_branch = await NodeManager.get_one(db=db, branch=branch, id=person.id)
        assert person_on_branch is None, "Person should be deleted on the branch after migration"

        # Step 6: Update the diff again
        enriched_diff_metadata = await diff_coordinator.update_branch_diff(
            base_branch=default_branch, diff_branch=branch
        )

        # Step 7: Verify the deleted person appears in the updated diff
        enriched_diff = await diff_repository.get_one(
            diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
        )
        person_in_diff = [n for n in enriched_diff.nodes if n.uuid == person.id]
        assert len(person_in_diff) == 1, (
            f"Person should appear in the diff after being deleted by migration. "
            f"Diff node UUIDs: {[n.uuid for n in enriched_diff.nodes]}"
        )
        assert person_in_diff[0].action is DiffAction.REMOVED
