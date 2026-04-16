import ssl
from pathlib import Path

from infrahub.config import HTTPSettings

TEST_DATA_DIR = Path(__file__).parent.parent / "test_data"


def test_http_settings_get_tls_context__default_returns_verified() -> None:
    """Default settings should return a context that verifies certificates."""
    settings = HTTPSettings()
    context = settings.get_tls_context()

    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED


def test_http_settings_get_tls_context__tls_insecure_returns_unverified() -> None:
    """When tls_insecure=True, should return an unverified context."""
    settings = HTTPSettings(tls_insecure=True)
    context = settings.get_tls_context()

    assert context.check_hostname is False
    assert context.verify_mode == ssl.CERT_NONE


def test_http_settings_get_tls_context__tls_insecure_with_force_verify_returns_verified() -> None:
    """When tls_insecure=True but force_verify=True, should return a verified context."""
    settings = HTTPSettings(tls_insecure=True)
    context = settings.get_tls_context(force_verify=True)

    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED


def test_http_settings_get_tls_context__ca_bundle_file_with_force_verify() -> None:
    """When tls_insecure=True with ca_bundle file path and force_verify=True, should use the CA bundle."""
    ca_file = TEST_DATA_DIR / "ca-bundle.pem"
    settings = HTTPSettings(tls_insecure=True, tls_ca_bundle=str(ca_file))

    # Without force_verify, should be unverified despite having a CA bundle
    context_insecure = settings.get_tls_context()
    assert context_insecure.verify_mode == ssl.CERT_NONE

    # With force_verify, should use the CA bundle and verify
    context_verified = settings.get_tls_context(force_verify=True)
    assert context_verified.verify_mode == ssl.CERT_REQUIRED
    assert context_verified.check_hostname is True


def test_http_settings_get_tls_context__ca_bundle_string_with_force_verify() -> None:
    """When tls_insecure=True with ca_bundle as PEM string and force_verify=True, should use the CA bundle."""
    ca_file = TEST_DATA_DIR / "ca-bundle.pem"
    ca_bundle_content = ca_file.read_text()
    settings = HTTPSettings(tls_insecure=True, tls_ca_bundle=ca_bundle_content)

    # Without force_verify, should be unverified despite having a CA bundle
    context_insecure = settings.get_tls_context()
    assert context_insecure.verify_mode == ssl.CERT_NONE

    # With force_verify, should use the CA bundle and verify
    context_verified = settings.get_tls_context(force_verify=True)
    assert context_verified.verify_mode == ssl.CERT_REQUIRED
    assert context_verified.check_hostname is True


def test_http_settings_get_tls_context__ca_bundle_long_string_triggers_oserror() -> None:
    """When ca_bundle is a very long string (>500 chars), OSError from Path.exists() is caught.

    This test uses a 4096-bit certificate which is long enough (1600+ chars without newlines)
    to trigger an OSError when Python tries to check if it's a valid file path. The code
    catches this OSError and correctly treats the string as PEM content.
    """
    ca_file = TEST_DATA_DIR / "ca-bundle-4096.pem"
    ca_bundle_content = ca_file.read_text()
    settings = HTTPSettings(tls_insecure=True, tls_ca_bundle=ca_bundle_content)

    # Without force_verify, should be unverified despite having a CA bundle
    context_insecure = settings.get_tls_context()
    assert context_insecure.verify_mode == ssl.CERT_NONE

    # With force_verify, should use the CA bundle and verify
    context_verified = settings.get_tls_context(force_verify=True)
    assert context_verified.verify_mode == ssl.CERT_REQUIRED
    assert context_verified.check_hostname is True
