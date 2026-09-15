from __future__ import annotations

import ssl
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import pytest

from infrahub import config
from infrahub.config import Settings

# The module reads stdin at import time to build the default CLI argument; pytest captures stdin.
with patch("sys.stdin"):
    from infrahub.git_credential.helper import build_client_config

TEST_DATA_DIR = Path(__file__).parent.parent / "test_data"
CA_BUNDLE = str(TEST_DATA_DIR / "ca-bundle.pem")
INTERNAL_ADDRESS = "https://infrahub-server:8000"


# Shape of the "subject" entry returned by SSLContext.get_ca_certs(): a tuple of RDNs, each a tuple of
# (attribute, value) pairs. typeshed types every entry of the certificate dict with one wide union.
SubjectType = tuple[tuple[tuple[str, str], ...], ...]


def _trusted_common_names(context: ssl.SSLContext) -> set[str]:
    names: set[str] = set()
    for cert in context.get_ca_certs():
        subject = cast("SubjectType", cert.get("subject", ()))
        for relative_dn in subject:
            for attribute, value in relative_dn:
                if attribute == "commonName":
                    names.add(value)
    return names


UseSettings = Callable[[dict[str, Any]], None]


@pytest.fixture
def use_settings(monkeypatch: pytest.MonkeyPatch) -> UseSettings:
    def _apply(settings: dict[str, Any]) -> None:
        monkeypatch.setattr(config.SETTINGS, "settings", Settings.model_validate(settings))

    return _apply


def test_client_targets_the_internal_address(use_settings: UseSettings) -> None:
    use_settings({"main": {"internal_address": INTERNAL_ADDRESS}})

    client_config = build_client_config()

    assert client_config.address == INTERNAL_ADDRESS
    assert client_config.insert_tracker is True


def test_default_settings_verify_against_the_system_store(use_settings: UseSettings) -> None:
    use_settings({"main": {"internal_address": INTERNAL_ADDRESS}})

    context = build_client_config().tls_context

    assert context.verify_mode == ssl.CERT_REQUIRED
    assert "test" not in _trusted_common_names(context)


def test_http_ca_bundle_is_trusted(use_settings: UseSettings) -> None:
    use_settings({"main": {"internal_address": INTERNAL_ADDRESS}, "http": {"tls_ca_bundle": CA_BUNDLE}})

    context = build_client_config().tls_context

    assert context.verify_mode == ssl.CERT_REQUIRED
    assert "test" in _trusted_common_names(context)


def test_global_ca_bundle_reaches_the_helper(use_settings: UseSettings) -> None:
    use_settings({"main": {"internal_address": INTERNAL_ADDRESS}, "tls": {"ca_bundle": CA_BUNDLE}})

    context = build_client_config().tls_context

    assert "test" in _trusted_common_names(context)


def test_http_insecure_skips_verification(use_settings: UseSettings) -> None:
    use_settings({"main": {"internal_address": INTERNAL_ADDRESS}, "http": {"tls_insecure": True}})

    context = build_client_config().tls_context

    assert context.verify_mode == ssl.CERT_NONE
    assert context.check_hostname is False
