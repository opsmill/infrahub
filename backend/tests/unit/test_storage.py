from __future__ import annotations

from typing import Any

import boto3
import pytest

from infrahub.config import S3StorageSettings, StorageDriver, StorageSettings
from infrahub.storage import InfrahubObjectStorage, InfrahubS3ObjectStorage


class _StubS3Resource:
    """Minimal stand-in for a boto3 S3 service resource."""

    def Bucket(self, name: str) -> object:  # noqa: N802 - match boto3 method name
        return object()


@pytest.fixture
def captured_resource_kwargs(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Patch boto3.resource and capture the kwargs the storage layer passes to it."""
    captured: dict[str, Any] = {}

    def _spy(*args: Any, **kwargs: Any) -> _StubS3Resource:
        captured.update(kwargs)
        return _StubS3Resource()

    monkeypatch.setattr(boto3, "resource", _spy)
    return captured


def _build_storage(**creds: Any) -> None:
    InfrahubS3ObjectStorage(
        AWS_S3_BUCKET_NAME="mocked",
        AWS_S3_ENDPOINT_URL="s3.amazonaws.com",
        **creds,
    )


def test_static_credentials_are_forwarded_verbatim(captured_resource_kwargs: dict[str, Any]) -> None:
    _build_storage(AWS_ACCESS_KEY_ID="some_id", AWS_SECRET_ACCESS_KEY="secret_key")

    assert captured_resource_kwargs["aws_access_key_id"] == "some_id"
    assert captured_resource_kwargs["aws_secret_access_key"] == "secret_key"


def test_blank_credentials_fall_back_to_credential_chain(captured_resource_kwargs: dict[str, Any]) -> None:
    _build_storage(AWS_ACCESS_KEY_ID="", AWS_SECRET_ACCESS_KEY="")

    assert captured_resource_kwargs["aws_access_key_id"] is None
    assert captured_resource_kwargs["aws_secret_access_key"] is None


@pytest.mark.parametrize(
    ("access_key", "secret_key"),
    [
        ("some_id", ""),
        ("", "secret_key"),
    ],
)
def test_partial_credentials_raise(access_key: str, secret_key: str) -> None:
    with pytest.raises(ValueError, match="both AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY"):
        _build_storage(AWS_ACCESS_KEY_ID=access_key, AWS_SECRET_ACCESS_KEY=secret_key)


def test_whitespace_only_credentials_are_treated_as_blank(captured_resource_kwargs: dict[str, Any]) -> None:
    _build_storage(AWS_ACCESS_KEY_ID="   ", AWS_SECRET_ACCESS_KEY="   ")

    assert captured_resource_kwargs["aws_access_key_id"] is None
    assert captured_resource_kwargs["aws_secret_access_key"] is None


def test_ca_bundle_is_forwarded_to_boto3(captured_resource_kwargs: dict[str, Any]) -> None:
    _build_storage(
        AWS_ACCESS_KEY_ID="some_id", AWS_SECRET_ACCESS_KEY="secret_key", AWS_CA_BUNDLE="/etc/infrahub/ca.pem"
    )

    assert captured_resource_kwargs["verify"] == "/etc/infrahub/ca.pem"


def test_without_ca_bundle_boto3_keeps_its_default_trust_store(captured_resource_kwargs: dict[str, Any]) -> None:
    _build_storage(AWS_ACCESS_KEY_ID="some_id", AWS_SECRET_ACCESS_KEY="secret_key")

    assert captured_resource_kwargs["verify"] is None


def test_endpoint_with_protocol_is_rejected(captured_resource_kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="should not contain the protocol"):
        InfrahubS3ObjectStorage(
            AWS_S3_BUCKET_NAME="mocked",
            AWS_S3_ENDPOINT_URL="https://s3.amazonaws.com",
            AWS_ACCESS_KEY_ID="some_id",
            AWS_SECRET_ACCESS_KEY="secret_key",
        )


def test_storage_settings_ca_file_reaches_the_driver(captured_resource_kwargs: dict[str, Any]) -> None:
    settings = StorageSettings(
        driver=StorageDriver.InfrahubS3ObjectStorage,
        # Keys are the environment variable names, the way operators set them.
        s3=S3StorageSettings.model_validate(
            {
                "AWS_S3_BUCKET_NAME": "mocked",
                "AWS_S3_ENDPOINT_URL": "s3.internal.example.com",
                "AWS_ACCESS_KEY_ID": "some_id",
                "AWS_SECRET_ACCESS_KEY": "secret_key",
                "INFRAHUB_STORAGE_TLS_CA_FILE": "/etc/infrahub/ca.pem",
            }
        ),
    )

    InfrahubObjectStorage(settings=settings)

    assert captured_resource_kwargs["verify"] == "/etc/infrahub/ca.pem"
    assert captured_resource_kwargs["endpoint_url"] == "https://s3.internal.example.com"
