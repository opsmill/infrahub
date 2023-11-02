from uuid import UUID

from infrahub_sdk.utils import is_valid_uuid
from infrahub_sdk.uuidt import UUIDT


def test_uuidt():
    uuid1 = str(UUIDT())
    uuid2 = str(UUIDT())
    uuid3 = str(UUIDT())

    assert isinstance(UUIDT.new(), UUID)

    assert is_valid_uuid(uuid1) is True
    assert is_valid_uuid(uuid2) is True
    assert is_valid_uuid(uuid3) is True

    assert uuid1 != uuid2
    assert sorted([uuid3, uuid2, uuid1]) == [uuid1, uuid2, uuid3]


def test_uuidt_short():
    short1 = UUIDT().short()
    short2 = UUIDT().short()
    assert isinstance(short1, str)
    assert len(short1) == 8
    assert short1 != short2
