import pytest

try:
    from pydantic import v1 as pydantic  # type: ignore[attr-defined]
except ImportError:
    import pydantic  # type: ignore[no-redef]

from infrahub_sdk.config import Config


def test_combine_authentications():
    with pytest.raises(pydantic.error_wrappers.ValidationError) as exc:
        Config(api_token="testing", username="test", password="testpassword")

    assert "Unable to combine password with token based authentication" in str(exc.value)


def test_missing_password():
    with pytest.raises(pydantic.error_wrappers.ValidationError) as exc:
        Config(username="test")

    assert "Both 'username' and 'password' needs to be set" in str(exc.value)


def test_password_authentication():
    config = Config(username="test", password="test-password")
    assert config.password_authentication


def test_not_password_authentication():
    config = Config()
    assert not config.password_authentication
