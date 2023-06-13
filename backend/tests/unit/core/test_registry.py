from infrahub.core import get_branch, get_branch_from_registry, registry
from infrahub.core.branch import Branch
from infrahub.core.schema import SchemaRoot, internal_schema
from infrahub.core.schema_manager import SchemaManager


async def test_get_branch_from_registry(session, default_branch):
    br1 = get_branch_from_registry()
    assert br1.name == default_branch.name

    br2 = get_branch_from_registry(default_branch.name)
    assert br2.name == default_branch.name


async def test_get_branch_not_in_registry(session, default_branch):
    # initialize internal registry
    registry.schema = SchemaManager()
    schema = SchemaRoot(**internal_schema)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)

    branch1 = Branch(name="branch1", status="OPEN")
    await branch1.save(session=session)

    br1 = await get_branch(branch=branch1.name, session=session)
    assert br1.name == branch1.name
