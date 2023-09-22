from infrahub.core import get_branch
from infrahub.core.branch import Branch
from infrahub.core.query.branch import GetAllBranchInternalRelationshipQuery


async def test_GetAllBranchInternalRelationshipQuery(session, default_branch: Branch, base_dataset_02):
    branch1 = await get_branch(branch="branch1", session=session)

    query = await GetAllBranchInternalRelationshipQuery.init(session=session, branch=branch1)
    await query.execute(session=session)

    assert len(query.results)

    unique_ids = set([result.get("r").element_id for result in query.results])
    assert len(unique_ids) == len(query.results)
