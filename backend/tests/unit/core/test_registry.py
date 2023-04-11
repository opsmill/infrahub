from infrahub.core import get_branch, get_branch_from_registry
from infrahub.core.branch import Branch


async def test_get_branch_from_registry(session, default_branch):
    br1 = get_branch_from_registry()
    assert br1.name == default_branch.name

    br2 = get_branch_from_registry(default_branch.name)
    assert br2.name == default_branch.name


async def test_get_branch_not_in_registry(session, default_branch):
    branch1 = Branch(name="branch1", status="OPEN")
    await branch1.save(session=session)

    br1 = await get_branch(branch=branch1.name, session=session)
    assert br1.name == branch1.name
