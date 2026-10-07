import pytest

from infrahub.core.branch import Branch
from infrahub.core.initialization import initialize_registry
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from tests.helpers.schema import load_schema

from .helpers import TICKET_WITH_SEQUENCE


@pytest.fixture(scope="class")
async def main_branch(
    db: InfrahubDatabase,
    default_branch_scope_class: Branch,
    register_core_models_schema_scope_class: SchemaBranch,
) -> Branch:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET_WITH_SEQUENCE]))
    await initialize_registry(db=db)
    default_branch_scope_class.update_schema_hash()
    return default_branch_scope_class
