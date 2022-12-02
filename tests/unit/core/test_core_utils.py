

from infrahub.core.utils import delete_all_nodes



def test_delete_all_nodes():

    assert delete_all_nodes() == []
