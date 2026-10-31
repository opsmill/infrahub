from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.config import ConfiguredSettings, LicenseSettings, load

if TYPE_CHECKING:
    import pytest


def test_license_key_is_unset_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INFRAHUB_LICENSE_KEY", raising=False)

    assert LicenseSettings().key is None


def test_license_key_is_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INFRAHUB_LICENSE_KEY", "signed-token")

    assert LicenseSettings().key == "signed-token"


def test_license_section_of_the_configuration_reaches_the_settings() -> None:
    configured = ConfiguredSettings(settings=load(config_data={"license": {"key": "signed-token"}}))

    assert configured.license.key == "signed-token"


def test_license_key_enables_no_enterprise_feature() -> None:
    """A key on Community must not trip the enterprise feature check that refuses to start."""
    without_key = load(config_data={"license": {"key": None}})
    with_key = load(config_data={"license": {"key": "signed-token"}})

    assert with_key.license.key == "signed-token"
    assert with_key.enterprise_features == without_key.enterprise_features
