from infrahub.core import get_branch_from_registry


async def test_get_branch_from_registry(session, default_branch):

    br1 = get_branch_from_registry()
    assert br1.name == default_branch.name

    br2 = get_branch_from_registry(default_branch.name)
    assert br2.name == default_branch.name
