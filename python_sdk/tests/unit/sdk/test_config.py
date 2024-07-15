import pytest
from pydantic import ValidationError

from infrahub_sdk.config import Config


def test_combine_authentications():
    with pytest.raises(ValidationError) as exc:
        Config(api_token="testing", username="test", password="testpassword")

    assert "Unable to combine password with token based authentication" in str(exc.value)


def test_missing_password():
    with pytest.raises(ValidationError) as exc:
        Config(username="test")

    assert "Both 'username' and 'password' needs to be set" in str(exc.value)


def test_password_authentication():
    config = Config(username="test", password="test-password")
    assert config.password_authentication


def test_not_password_authentication():
    config = Config()
    assert not config.password_authentication


def test_config_address():
    address = "http://localhost:8000"

    config = Config(address=address + "/")
    assert config.address == address

    config = Config(address=address + "//")
    assert config.address == address

    config = Config(address=address)
    assert config.address == address
