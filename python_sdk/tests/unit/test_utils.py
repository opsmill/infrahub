import uuid

from infrahub_client.utils import is_valid_uuid


def test_is_valid_uuid():
    assert is_valid_uuid(uuid.uuid4()) is True
    assert is_valid_uuid(uuid.UUID("ba0aecd9-546a-4d77-9187-23e17a20633e")) is True
    assert is_valid_uuid("ba0aecd9-546a-4d77-9187-23e17a20633e") is True

    assert is_valid_uuid("xxx-546a-4d77-9187-23e17a20633e") is False
    assert is_valid_uuid(222) is False
    assert is_valid_uuid(False) is False
    assert is_valid_uuid("Not a valid UUID") is False
    assert is_valid_uuid(uuid.UUID) is False
