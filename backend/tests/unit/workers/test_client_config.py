from __future__ import annotations

import ssl
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from infrahub import config
from infrahub.config import Settings
from infrahub.workers.infrahub_async import build_worker_client_config
from tests.helpers.tls import trusted_common_names

TEST_DATA_DIR = Path(__file__).parent.parent / "test_data"
CA_BUNDLE = str(TEST_DATA_DIR / "ca-bundle.pem")
INTERNAL_ADDRESS = "https://infrahub-server:8000"

UseSettings = Callable[[dict[str, Any]], None]


@pytest.fixture
def use_settings(monkeypatch: pytest.MonkeyPatch) -> UseSettings:
    def _apply(settings: dict[str, Any]) -> None:
        monkeypatch.setattr(config.SETTINGS, "settings", Settings.model_validate(settings))

    return _apply


def test_client_targets_the_internal_address(use_settings: UseSettings) -> None:
    use_settings({"main": {"internal_address": INTERNAL_ADDRESS}})

    client_config = build_worker_client_config()

    assert client_config.address == INTERNAL_ADDRESS


def test_default_settings_verify_against_the_system_store(use_settings: UseSettings) -> None:
    use_settings({"main": {"internal_address": INTERNAL_ADDRESS}})

    context = build_worker_client_config().tls_context

    assert context.verify_mode == ssl.CERT_REQUIRED
    assert "test" not in trusted_common_names(context)


def test_http_ca_bundle_is_trusted(use_settings: UseSettings) -> None:
    use_settings({"main": {"internal_address": INTERNAL_ADDRESS}, "http": {"tls_ca_bundle": CA_BUNDLE}})

    context = build_worker_client_config().tls_context

    assert context.verify_mode == ssl.CERT_REQUIRED
    assert "test" in trusted_common_names(context)


def test_global_ca_bundle_reaches_the_worker_client(use_settings: UseSettings) -> None:
    use_settings({"main": {"internal_address": INTERNAL_ADDRESS}, "tls": {"ca_bundle": CA_BUNDLE}})

    context = build_worker_client_config().tls_context

    assert "test" in trusted_common_names(context)


def test_http_insecure_skips_verification(use_settings: UseSettings) -> None:
    use_settings({"main": {"internal_address": INTERNAL_ADDRESS}, "http": {"tls_insecure": True}})

    context = build_worker_client_config().tls_context

    assert context.verify_mode == ssl.CERT_NONE
    assert context.check_hostname is False


def test_http_insecure_wins_over_the_ca_bundle(use_settings: UseSettings) -> None:
    # `http.tls_insecure` outranks every CA setting, so an operator can drop verification for a
    # temporary problem without having to remove the bundle first.
    use_settings(
        {
            "main": {"internal_address": INTERNAL_ADDRESS},
            "http": {"tls_insecure": True, "tls_ca_bundle": CA_BUNDLE},
        }
    )

    context = build_worker_client_config().tls_context

    assert context.verify_mode == ssl.CERT_NONE
    assert context.check_hostname is False
