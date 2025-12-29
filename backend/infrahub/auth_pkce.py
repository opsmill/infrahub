"""PKCE (RFC 7636) utilities for OAuth2/OIDC authentication.

This module provides functions to generate code verifiers and compute
code challenges for the Proof Key for Code Exchange (PKCE) extension.
"""

from __future__ import annotations

import base64
import hashlib
import secrets


def generate_code_verifier() -> str:
    """Generate a cryptographically random code verifier.

    The code verifier is a high-entropy cryptographic random string using
    the unreserved characters [A-Z] / [a-z] / [0-9] / "-" / "." / "_" / "~",
    with a minimum length of 43 characters and a maximum length of 128
    characters.

    Returns:
        A 43-character URL-safe string (256 bits of entropy).
    """
    return secrets.token_urlsafe(32)


def compute_code_challenge(code_verifier: str) -> str:
    """Compute S256 code challenge from verifier.

    Implements the S256 code challenge method as defined in RFC 7636:
    code_challenge = BASE64URL(SHA256(code_verifier))

    Args:
        code_verifier: The code verifier string.

    Returns:
        Base64URL-encoded SHA256 hash without padding.
    """
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
