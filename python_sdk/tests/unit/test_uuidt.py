from infrahub_client.uuidt import UUIDT


def test_uuidt():
    uuid1 = str(UUIDT.new())
    uuid2 = str(UUIDT.new())
    uuid3 = str(UUIDT.new())

    assert len(uuid1) == 28
    assert uuid1 != uuid2
    assert sorted([uuid3, uuid2, uuid1]) == [uuid1, uuid2, uuid3]
