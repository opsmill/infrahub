import pytest
from infrahub_sdk.client import InfrahubClient

from infrahub import config
from infrahub.core.migrations.graph.m031_check_number_attributes import Migration031
from infrahub.core.migrations.shared import MigrationInput
from tests.helpers.test_app import TestInfrahubApp

schema_number_parameters = {
    "version": "1.0",
    "nodes": [
        {
            "name": "Application",
            "namespace": "Random",
            "include_in_menu": True,
            "attributes": [
                {
                    "name": "size",
                    "kind": "Number",
                    "parameters": {"min_value": 10, "max_value": 4094, "excluded_values": "12,14-16"},
                    "optional": False,
                }
            ],
        },
    ],
}


class TestMigration031(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def load_schema(self, client: InfrahubClient) -> None:
        response = await client.schema.load(schemas=[schema_number_parameters])
        assert len(response.errors) == 0, response.errors

    async def test_migration_031(self, db, client: InfrahubClient, load_schema, branch) -> None:
        strict_mode_original_value = config.SETTINGS.main.schema_strict_mode

        # Set strict mode to allow creating invalid attribute
        config.SETTINGS.main.schema_strict_mode = False
        node_size = 10_000
        node = await client.create(kind="RandomApplication", size=node_size, branch=branch.name)
        await node.save()

        # Run the migration without strict mode, nothing should happen
        migration = Migration031(db=db)
        execution_result = await migration.execute(migration_input=MigrationInput(db=db))
        assert not execution_result.errors
        validation_result = await migration.validate_migration(db=db)
        assert not validation_result.errors

        # Run the migration with strict mode, invalid node should show up
        config.SETTINGS.main.schema_strict_mode = True
        execution_result = await migration.execute(migration_input=MigrationInput(db=db))
        assert len(execution_result.errors) == 2
        assert (
            execution_result.errors[0]
            == "Following nodes attributes values must be updated to not violate corresponding min_value, "
            "max_value or excluded_values schema constraints"
        )
        assert (
            execution_result.errors[1]
            == f"Node {node.id} on branch {branch.name} has an invalid Number attribute size: {node_size}"
        )

        # Make sure we can update the node value to a valid value without strict mode
        config.SETTINGS.main.schema_strict_mode = False
        node.size = 1_000
        await node.save()

        # Run the migration with strict mode to make sure it doesn't raise an error now that the node has been fixed
        config.SETTINGS.main.schema_strict_mode = True
        migration = Migration031(db=db)
        execution_result = await migration.execute(migration_input=MigrationInput(db=db))
        assert not execution_result.errors

        config.SETTINGS.main.schema_strict_mode = strict_mode_original_value
