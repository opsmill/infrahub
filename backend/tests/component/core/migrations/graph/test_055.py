import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.migrations.graph.m055_remove_webhook_validate_certificates_default import (
    Migration055,
    Migration055Query01,
)
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.schema.definitions.core.webhook import core_webhook
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.utils import count_relationships
from infrahub.database import InfrahubDatabase


def _create_webhook_schema_with_default() -> GenericSchema:
    """Create a modified CoreWebhook schema with default_value=True on validate_certificates."""
    # Create a copy of the core_webhook generic
    webhook_copy = core_webhook.model_copy(deep=True)

    # Find and modify the validate_certificates attribute to have default_value=True
    for attr in webhook_copy.attributes:
        if attr.name == "validate_certificates":
            attr.default_value = True
            break

    return webhook_copy


async def _load_webhook_schema_from_db(db: InfrahubDatabase, branch: Branch) -> GenericSchema:
    """Load the CoreWebhook schema from the database."""
    schema_branch = await registry.schema.load_schema_from_db(db=db, branch=branch)
    return schema_branch.get_generic(name="CoreWebhook")


@pytest.fixture
async def migration_055_data(
    db: InfrahubDatabase,
    reset_registry: None,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    # Create a modified CoreWebhook generic with default_value=True on validate_certificates
    modified_webhook = _create_webhook_schema_with_default()

    # Get the current schema branch and add the modified webhook
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    schema_branch.set(name=modified_webhook.kind, schema=modified_webhook)

    # Load CoreWebhook and its relationship peers to the database
    await registry.schema.load_schema_to_db(
        schema=schema_branch,
        db=db,
        branch=default_branch,
        limit=["CoreWebhook", "CoreKeyValue"],
    )


async def test_migration_055_query(
    db: InfrahubDatabase,
    reset_registry: None,
    default_branch: Branch,
    migration_055_data: None,
) -> None:
    nbr_rels_before = await count_relationships(db=db)

    # Verify initial state: Webhook's validate_certificates has default_value=True
    webhook_schema_before = await _load_webhook_schema_from_db(db, default_branch)
    assert webhook_schema_before.get_attribute("validate_certificates").default_value is True

    # Execute the migration query
    query = await Migration055Query01.init(db=db)
    await query.execute(db=db)
    assert query.num_of_results == 1

    # Execute again - should be idempotent (no more results)
    query = await Migration055Query01.init(db=db)
    await query.execute(db=db)
    assert query.num_of_results == 0

    nbr_rels_after = await count_relationships(db=db)
    # One new HAS_VALUE relationship should have been created
    assert nbr_rels_after == nbr_rels_before + 1

    # Verify the Webhook's validate_certificates attribute now has NULL as default_value
    webhook_schema_after = await _load_webhook_schema_from_db(db, default_branch)
    assert webhook_schema_after.get_attribute("validate_certificates").default_value is None


async def test_migration_055(
    db: InfrahubDatabase,
    reset_registry: None,
    default_branch: Branch,
    migration_055_data: None,
) -> None:
    nbr_rels_before = await count_relationships(db=db)

    # Verify initial state: Webhook's validate_certificates has default_value=True
    webhook_schema_before = await _load_webhook_schema_from_db(db, default_branch)
    assert webhook_schema_before.get_attribute("validate_certificates").default_value is True

    migration = Migration055()
    execution_result = await migration.execute(migration_input=MigrationInput(db=db))
    assert not execution_result.errors

    validation_result = await migration.validate_migration(db=db)
    assert not validation_result.errors

    nbr_rels_after = await count_relationships(db=db)
    assert nbr_rels_after == nbr_rels_before + 1

    # Verify the Webhook's validate_certificates attribute now has NULL as default_value
    webhook_schema_after = await _load_webhook_schema_from_db(db, default_branch)
    assert webhook_schema_after.get_attribute("validate_certificates").default_value is None
