from infrahub.core import get_branch, get_branch_from_registry, registry
from infrahub.core.branch.branch import Branch
from infrahub.core.schema import SchemaRoot, internal_schema
from infrahub.core.schema_manager import SchemaManager
from infrahub.database import InfrahubDatabase


async def test_get_branch_from_registry(db: InfrahubDatabase, default_branch: Branch):
    br1 = get_branch_from_registry()
    assert br1.name == default_branch.name

    br2 = get_branch_from_registry(default_branch.name)
    assert br2.name == default_branch.name


async def test_get_branch_not_in_registry(db: InfrahubDatabase, default_branch: Branch):
    # initialize internal registry
    registry.schema = SchemaManager()
    schema = SchemaRoot(**internal_schema)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)
    default_branch.update_schema_hash()

    branch1 = Branch(name="branch1", status="OPEN")
    branch1.update_schema_hash()
    await branch1.save(db=db)

    br1 = await get_branch(branch=branch1.name, db=db)
    assert br1.name == branch1.name
