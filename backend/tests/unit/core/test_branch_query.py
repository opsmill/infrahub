from infrahub.core import get_branch
from infrahub.core.query.diff import (
    DiffRelationshipPropertyQuery,
    DiffRelationshipQuery,
)
from infrahub_client.timestamp import Timestamp


async def test_DiffRelationshipQuery(session, base_dataset_02):
    branch1 = await get_branch("branch1", session=session)

    # Execute the query with default timestamp from the creation of the branch to now
    query = await DiffRelationshipQuery.init(session=session, branch=branch1)
    await query.execute(session=session)
    assert query.diff_from == Timestamp(base_dataset_02["time_m45"])
    assert query.diff_to > Timestamp(base_dataset_02["time0"])

    results = list(query.get_results())
    assert len(results) == 1

    # Execute the query to calculate the diff since time0
    query = await DiffRelationshipQuery.init(
        session=session, branch=branch1, diff_from=Timestamp(base_dataset_02["time0"])
    )
    await query.execute(session=session)
    assert query.diff_from == Timestamp(base_dataset_02["time0"])
    assert query.diff_to > Timestamp(base_dataset_02["time0"])

    results = list(query.get_results())
    assert len(results) == 0


async def test_DiffRelationshipPropertyQuery(session, base_dataset_02):
    branch1 = await get_branch("branch1", session=session)

    # Execute the query with default timestamp from the creation of the branch to now
    # 4 changes are expected
    query = await DiffRelationshipPropertyQuery.init(session=session, branch=branch1)
    await query.execute(session=session)
    assert query.diff_from == Timestamp(base_dataset_02["time_m45"])
    assert query.diff_to > Timestamp(base_dataset_02["time0"])

    results = list(query.get_results())
    assert len(results) == 4

    # Execute the query to calculate the diff since time0
    # No change are expected
    query = await DiffRelationshipPropertyQuery.init(
        session=session, branch=branch1, diff_from=Timestamp(base_dataset_02["time0"])
    )
    await query.execute(session=session)
    assert query.diff_from == Timestamp(base_dataset_02["time0"])
    assert query.diff_to > Timestamp(base_dataset_02["time0"])

    results = list(query.get_results())
    assert len(results) == 0

    # Execute the query to calculate the diff between time_m35 and time_m25
    # Only 1 change is expected r1/IS_PROTECTED at m30
    query = await DiffRelationshipPropertyQuery.init(
        session=session,
        branch=branch1,
        diff_from=Timestamp(base_dataset_02["time_m35"]),
        diff_to=Timestamp(base_dataset_02["time_m25"]),
    )
    await query.execute(session=session)
    results = list(query.get_results())
    assert len(results) == 1

    # Execute the query to calculate the diff between time_m25 and time_m10
    # Only 3 changes is expected : creation of r2 at m20 and modification of r1/IS_VISIBLE
    query = await DiffRelationshipPropertyQuery.init(
        session=session,
        branch=branch1,
        diff_from=Timestamp(base_dataset_02["time_m25"]),
        diff_to=Timestamp(base_dataset_02["time_m10"]),
    )
    await query.execute(session=session)
    results = list(query.get_results())
    assert len(results) == 3
