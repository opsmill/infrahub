from infrahub.core import get_branch
from infrahub.core.branch.branch import Branch
from infrahub.core.query.branch import GetAllBranchInternalRelationshipQuery
from infrahub.database import InfrahubDatabase


async def test_GetAllBranchInternalRelationshipQuery(db: InfrahubDatabase, default_branch: Branch, base_dataset_02):
    branch1 = await get_branch(branch="branch1", db=db)

    query = await GetAllBranchInternalRelationshipQuery.init(db=db, branch=branch1)
    await query.execute(db=db)

    assert len(query.results)

    unique_ids = set([result.get("r").element_id for result in query.results])
    assert len(unique_ids) == len(query.results)
