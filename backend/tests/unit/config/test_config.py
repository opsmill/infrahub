import logging

import pytest

from infrahub.config import SecurityOIDCSettings


def _make_oidc_provider(verify_signature: bool) -> SecurityOIDCSettings:
    return SecurityOIDCSettings(
        client_id="testing-client",
        discovery_url="https://oidc.example.com/.well-known/openid-configuration",
        id_token_verify_signature=verify_signature,
    )


def test_oidc_disabled_signature_verification_warns_once(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="infrahub"):
        provider = _make_oidc_provider(verify_signature=False)

    assert provider.id_token_verify_signature is False
    warnings = [record for record in caplog.records if "OIDC id_token verification is disabled" in record.message]
    assert len(warnings) == 1


def test_oidc_default_signature_verification_is_silent(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="infrahub"):
        provider = _make_oidc_provider(verify_signature=True)

    assert provider.id_token_verify_signature is True
    assert not [record for record in caplog.records if "OIDC id_token verification is disabled" in record.message]
