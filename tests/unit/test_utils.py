from infrahub.utils import duplicates


def test_duplicates():

    assert duplicates([2, 4, 6, 8, 4, 6, 12]) == [4, 6]
    assert duplicates(["first", "second", "first", "third", "first", "last"]) == ["first"]
    assert duplicates([2, 8, 4, 6, 12]) == []
