from infrahub_sdk.client import InfrahubClient

from infrahub.core.migrations.graph.m074_check_optional_hfid_uniqueness import Migration074
from infrahub.core.migrations.shared import MigrationInput
from infrahub.database import InfrahubDatabase
from tests.helpers.test_app import TestInfrahubApp

# `disable_schema_strict_mode` is provided by backend/tests/conftest.py.


class TestMigration074(TestInfrahubApp):
    """Verify that m074 reports optional attributes (no default_value) used in hfid/uniqueness."""

    async def _load_violating_schema(self, client: InfrahubClient) -> None:
        violating_schema: dict = {
            "version": "1.0",
            "generics": [
                {
                    "name": "Gadget",
                    "namespace": "Testing",
                    "human_friendly_id": ["name__value", "serial__value"],
                    "uniqueness_constraints": [["serial__value"]],
                    "attributes": [
                        {"name": "name", "kind": "Text"},
                        {"name": "serial", "kind": "Text", "optional": True},
                    ],
                }
            ],
            "nodes": [
                {
                    "name": "Widget",
                    "namespace": "Testing",
                    "inherit_from": ["TestingGadget"],
                }
            ],
        }
        response = await client.schema.load(schemas=[violating_schema])
        assert len(response.errors) == 0, response.errors

    async def test_migration_clean_and_with_violations(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        disable_schema_strict_mode: None,
    ) -> None:
        # Baseline: the default schema has no violations, so the migration reports nothing.
        # The migration intentionally runs and reports regardless of strict mode (so operators who
        # set INFRAHUB_SCHEMA_STRICT_MODE=false to bypass the validator still get a diagnostic), so
        # the baseline run does not need strict mode explicitly enabled.
        migration = Migration074()
        baseline_result = await migration.execute(migration_input=MigrationInput(db=db))
        assert not baseline_result.errors, f"Expected no errors on baseline schema, got: {baseline_result.errors}"

        # Simulate a pre-existing deployment by loading a violating schema. The disable_schema_strict_mode
        # fixture has turned strict mode off so this load is accepted.
        await self._load_violating_schema(client=client)

        # Run the migration — it should report the violation regardless of strict mode.
        execution_result = await migration.execute(migration_input=MigrationInput(db=db))

        assert execution_result.errors, "Migration should return errors when violations exist"
        header = execution_result.errors[0]
        assert "INFRAHUB_SCHEMA_STRICT_MODE=false" in header, (
            "Migration header should explain how to bypass the validator"
        )

        violation_reports = execution_result.errors[1:]
        matching = [msg for msg in violation_reports if "'serial'" in msg and "TestingGadget" in msg]
        assert matching, f"Expected a violation for 'serial' of TestingGadget, got: {violation_reports}"
