"""Tests for PKCE (RFC 7636) utility functions."""

import base64
import hashlib
import re

from infrahub.auth_pkce import compute_code_challenge, generate_code_verifier


def test_generate_code_verifier_length() -> None:
    """Code verifier should be 43 characters (256 bits of entropy from token_urlsafe(32))."""
    verifier = generate_code_verifier()
    assert len(verifier) == 43


def test_generate_code_verifier_valid_characters() -> None:
    """Code verifier should only contain URL-safe base64 characters."""
    verifier = generate_code_verifier()
    # URL-safe base64 uses A-Z, a-z, 0-9, -, _
    assert re.match(r"^[A-Za-z0-9_-]+$", verifier)


def test_generate_code_verifier_uniqueness() -> None:
    """Each call should generate a unique verifier."""
    verifiers = {generate_code_verifier() for _ in range(100)}
    assert len(verifiers) == 100


def test_compute_code_challenge_s256_computation() -> None:
    """Code challenge should be BASE64URL(SHA256(code_verifier)) without padding."""
    verifier = "test_verifier_string"
    challenge = compute_code_challenge(verifier)

    # Manually compute expected challenge
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    expected = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

    assert challenge == expected


def test_compute_code_challenge_no_padding() -> None:
    """Code challenge should not have base64 padding characters."""
    verifier = generate_code_verifier()
    challenge = compute_code_challenge(verifier)
    assert "=" not in challenge


def test_compute_code_challenge_rfc_7636_appendix_b_test_vector() -> None:
    """Test against RFC 7636 Appendix B test vector.

    From RFC 7636:
    code_verifier = dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk
    code_challenge = E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM
    """
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    challenge = compute_code_challenge(verifier)
    expected = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    assert challenge == expected


def test_compute_code_challenge_deterministic() -> None:
    """Same verifier should always produce the same challenge."""
    verifier = generate_code_verifier()
    challenge1 = compute_code_challenge(verifier)
    challenge2 = compute_code_challenge(verifier)
    assert challenge1 == challenge2
