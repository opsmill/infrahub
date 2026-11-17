import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.schema import SchemaRoot, internal_schema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from tests.helpers.attribute_rows import load_asset_schema


@pytest.fixture
async def asset_schema(
    db: InfrahubDatabase, default_branch: Branch, register_internal_models_schema: SchemaBranch
) -> None:
    await load_asset_schema(db=db, default_branch=default_branch)


@pytest.fixture(scope="class")
async def asset_schema_class(db: InfrahubDatabase, default_branch_scope_class: Branch) -> Branch:
    """Class-scoped equivalent of asset_schema; returns the default branch it seeded."""
    registry.schema.register_schema(schema=SchemaRoot(**internal_schema), branch=default_branch_scope_class.name)
    await load_asset_schema(db=db, default_branch=default_branch_scope_class)
    return default_branch_scope_class
