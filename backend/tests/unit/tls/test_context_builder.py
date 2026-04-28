import ssl
from pathlib import Path

from infrahub.tls.context_builder import TlsContextBuilder

TEST_DATA_DIR = Path(__file__).parent.parent / "test_data"


def test_tls_context_builder__default_returns_verified() -> None:
    """Default settings should return a context that verifies certificates."""
    context = TlsContextBuilder.build()

    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED


def test_tls_context_builder__insecure_returns_unverified() -> None:
    """When insecure=True, should return an unverified context."""
    context = TlsContextBuilder.build(insecure=True)

    assert context.check_hostname is False
    assert context.verify_mode == ssl.CERT_NONE


def test_tls_context_builder__insecure_with_force_verify_returns_verified() -> None:
    """When insecure=True but force_verify=True, should return a verified context."""
    context = TlsContextBuilder.build(insecure=True, force_verify=True)

    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED


def test_tls_context_builder__ca_bundle_file_with_force_verify() -> None:
    """When insecure=True with ca_bundle file path and force_verify=True, should use the CA bundle."""
    ca_file = TEST_DATA_DIR / "ca-bundle.pem"

    # Without force_verify, should be unverified despite having a CA bundle
    context_insecure = TlsContextBuilder.build(insecure=True, ca_bundle=str(ca_file))
    assert context_insecure.verify_mode == ssl.CERT_NONE

    # With force_verify, should use the CA bundle and verify
    context_verified = TlsContextBuilder.build(insecure=True, ca_bundle=str(ca_file), force_verify=True)
    assert context_verified.verify_mode == ssl.CERT_REQUIRED
    assert context_verified.check_hostname is True


def test_tls_context_builder__ca_bundle_string_with_force_verify() -> None:
    """When insecure=True with ca_bundle as PEM string and force_verify=True, should use the CA bundle."""
    ca_file = TEST_DATA_DIR / "ca-bundle.pem"
    ca_bundle_content = ca_file.read_text()

    # Without force_verify, should be unverified despite having a CA bundle
    context_insecure = TlsContextBuilder.build(insecure=True, ca_bundle=ca_bundle_content)
    assert context_insecure.verify_mode == ssl.CERT_NONE

    # With force_verify, should use the CA bundle and verify
    context_verified = TlsContextBuilder.build(insecure=True, ca_bundle=ca_bundle_content, force_verify=True)
    assert context_verified.verify_mode == ssl.CERT_REQUIRED
    assert context_verified.check_hostname is True


def test_tls_context_builder__ca_bundle_long_string_triggers_oserror() -> None:
    """When ca_bundle is a very long string (>500 chars), OSError from Path.exists() is caught.

    This test uses a 4096-bit certificate which is long enough (1600+ chars without newlines)
    to trigger an OSError when Python tries to check if it's a valid file path. The code
    catches this OSError and correctly treats the string as PEM content.
    """
    ca_file = TEST_DATA_DIR / "ca-bundle-4096.pem"
    ca_bundle_content = ca_file.read_text()

    # Without force_verify, should be unverified despite having a CA bundle
    context_insecure = TlsContextBuilder.build(insecure=True, ca_bundle=ca_bundle_content)
    assert context_insecure.verify_mode == ssl.CERT_NONE

    # With force_verify, should use the CA bundle and verify
    context_verified = TlsContextBuilder.build(insecure=True, ca_bundle=ca_bundle_content, force_verify=True)
    assert context_verified.verify_mode == ssl.CERT_REQUIRED
    assert context_verified.check_hostname is True
