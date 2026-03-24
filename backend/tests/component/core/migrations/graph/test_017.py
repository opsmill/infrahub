from infrahub.core import registry
from infrahub.core.migrations.graph import Migration017
from infrahub.core.migrations.shared import MigrationInput
from infrahub.database import InfrahubDatabase


async def test_migration_017(
    db: InfrahubDatabase,
    default_branch,
    register_internal_models_schema,
) -> None:
    """
    Test migration correctly adds CoreProfile schema node.
    """

    item = registry.schema.get(name="CoreProfile")
    # Make sure to remove CoreProfile from database if it is there
    if item.id is not None:
        _ = await registry.schema.delete_node_in_db(node=item, branch=default_branch, db=db, user_id="user-id")

    # Remove CoreProfile from registry
    schema_branch = registry.schema.get_schema_branch(default_branch.name)
    core_profile_hash = schema_branch.generics["CoreProfile"]
    # TODO: should this cache deletion be performed within schema_branch.delete?
    del schema_branch._cache[core_profile_hash]
    schema_branch.delete(name="CoreProfile")

    async with db.start_session() as dbs:
        migration = Migration017()
        execution_result = await migration.execute(migration_input=MigrationInput(db=dbs))
        assert not execution_result.errors

        validation_result = await migration.validate_migration(db=dbs)
        assert not validation_result.errors

    # Make sure CoreProfile exists now
    schema_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch.name)
    assert schema_branch.all_names == ["CoreProfile"]
