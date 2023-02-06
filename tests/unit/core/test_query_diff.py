from infrahub.core import get_branch
from infrahub.core.query.diff import DiffRelationshipPropertiesByIDSRangeQuery


async def test_diff_relationship_properties_ids_range_query(session, default_branch, base_dataset_02):

    branch1 = await get_branch(branch="branch1", session=session)
    query = await DiffRelationshipPropertiesByIDSRangeQuery.init(
        session=session,
        branch=branch1,
        ids=["r1", "r2"],
        diff_from=base_dataset_02["time_m60"],
        diff_to=base_dataset_02["time0"],
    )
    await query.execute(session=session)

    assert len(query.results) == 6

    r1_result = query.get_results_by_id_and_prop_type(branch_name="main", rel_id="r1", type="IS_PROTECTED")

    assert len(r1_result) == 2
