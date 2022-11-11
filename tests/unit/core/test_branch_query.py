from infrahub.core import get_branch, registry
from infrahub.core.timestamp import Timestamp
from infrahub.core.query.diff import DiffRelationshipQuery, DiffRelationshipPropertyQuery


def test_DiffRelationshipQuery(base_dataset_02):

    branch1 = get_branch("branch1")

    # Execute the query with default timestamp from the creation of the branch to now
    query = DiffRelationshipQuery(branch=branch1).execute()
    assert query.diff_from == Timestamp(base_dataset_02["time_m40"])
    assert query.diff_to > Timestamp(base_dataset_02["time0"])

    results = list(query.get_results())
    assert len(results) == 1

    # Execute the query to calculate the diff since time0
    query = DiffRelationshipQuery(branch=branch1, diff_from=Timestamp(base_dataset_02["time0"])).execute()
    assert query.diff_from == Timestamp(base_dataset_02["time0"])
    assert query.diff_to > Timestamp(base_dataset_02["time0"])

    results = list(query.get_results())
    assert len(results) == 0


def test_DiffRelationshipPropertyQuery(base_dataset_02):

    branch1 = get_branch("branch1")

    # Execute the query with default timestamp from the creation of the branch to now
    # 4 changes are expected
    query = DiffRelationshipPropertyQuery(branch=branch1).execute()
    assert query.diff_from == Timestamp(base_dataset_02["time_m40"])
    assert query.diff_to > Timestamp(base_dataset_02["time0"])

    results = list(query.get_results())
    assert len(results) == 4

    # Execute the query to calculate the diff since time0
    # No change are expected
    query = DiffRelationshipPropertyQuery(branch=branch1, diff_from=Timestamp(base_dataset_02["time0"])).execute()
    assert query.diff_from == Timestamp(base_dataset_02["time0"])
    assert query.diff_to > Timestamp(base_dataset_02["time0"])

    results = list(query.get_results())
    assert len(results) == 0

    # Execute the query to calculate the diff between time_m35 and time_m25
    # Only 1 change is expected r1/IS_PROTECTED at m30
    query = DiffRelationshipPropertyQuery(
        branch=branch1, diff_from=Timestamp(base_dataset_02["time_m35"]), diff_to=Timestamp(base_dataset_02["time_m25"])
    ).execute()
    results = list(query.get_results())
    assert len(results) == 1

    # Execute the query to calculate the diff between time_m25 and time_m10
    # Only 3 changes is expected : creation of r2 at m20 and modification of r1/IS_VISIBLE
    query = DiffRelationshipPropertyQuery(
        branch=branch1, diff_from=Timestamp(base_dataset_02["time_m25"]), diff_to=Timestamp(base_dataset_02["time_m10"])
    ).execute()
    results = list(query.get_results())
    assert len(results) == 3
