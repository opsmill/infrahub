from __future__ import annotations

from dataclasses import dataclass

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from infrahub.config import SecuritySettings
from infrahub.exceptions import StorageEncryptionError, StorageIntegrityError
from infrahub.storage_encryption.crypto import StorageKey, is_envelope, open_envelope, seal, storage_key_from_settings

SECRET = "unit-test-secret-key-0123456789abcdef"
OTHER_SECRET = "another-unit-test-secret-key-987654321"
# HKDF-SHA256 outputs for SECRET, computed independently with the standard library's hmac module.
SECRET_FINGERPRINT = "f738ccd905f9f711"
SECRET_AES_KEY = bytes.fromhex("8d4e6ae57874b37888a9db691c612d9d4c13f8353abd0a4abe37b8ce15fe70ea")
OTHER_SECRET_FINGERPRINT = "93f08e3c4074b541"
IDENTIFIER = "18a3f2e4-5c3d-4b1e-a0f7-3c9d2b6e8f01"
CONTENT = b"interface Ethernet1\n  description uplink\n"


def test_key_is_derived_from_the_secret() -> None:
    assert StorageKey.derive(SECRET).fingerprint == SECRET_FINGERPRINT
    assert StorageKey.derive(OTHER_SECRET).fingerprint == OTHER_SECRET_FINGERPRINT


def test_key_representation_shows_only_the_fingerprint() -> None:
    assert repr(StorageKey.derive(SECRET)) == f"StorageKey(fingerprint='{SECRET_FINGERPRINT}')"


def test_envelope_layout_decrypts_with_the_derived_key() -> None:
    envelope = seal(identifier=IDENTIFIER, content=CONTENT, key=StorageKey.derive(SECRET))

    header, ciphertext = envelope[:25], envelope[25:]
    assert header[:5] == b"IHSE\x01"
    assert header[5:13].hex() == SECRET_FINGERPRINT
    assert AESGCM(SECRET_AES_KEY).decrypt(header[13:25], ciphertext, header + IDENTIFIER.encode()) == CONTENT
    assert CONTENT not in envelope
    assert open_envelope(identifier=IDENTIFIER, content=envelope, key=StorageKey.derive(SECRET)) == CONTENT


def _flip(data: bytes, offset: int) -> bytes:
    return data[:offset] + bytes([data[offset] ^ 0x01]) + data[offset + 1 :]


ENVELOPE = seal(identifier=IDENTIFIER, content=CONTENT, key=StorageKey.derive(SECRET))


@dataclass
class RefusedEnvelopeCase:
    name: str
    content: bytes
    identifier: str
    reason: str


REFUSED_ENVELOPE_CASES = [
    RefusedEnvelopeCase(
        name="sealed_with_another_key",
        content=seal(identifier=IDENTIFIER, content=CONTENT, key=StorageKey.derive(OTHER_SECRET)),
        identifier=IDENTIFIER,
        reason="unknown_key",
    ),
    RefusedEnvelopeCase(
        name="fingerprint_changed", content=_flip(ENVELOPE, 6), identifier=IDENTIFIER, reason="unknown_key"
    ),
    RefusedEnvelopeCase(name="nonce_changed", content=_flip(ENVELOPE, 15), identifier=IDENTIFIER, reason="tampered"),
    RefusedEnvelopeCase(
        name="ciphertext_changed", content=_flip(ENVELOPE, 30), identifier=IDENTIFIER, reason="tampered"
    ),
    RefusedEnvelopeCase(
        name="tag_changed", content=_flip(ENVELOPE, len(ENVELOPE) - 1), identifier=IDENTIFIER, reason="tampered"
    ),
    RefusedEnvelopeCase(name="truncated", content=ENVELOPE[:-1], identifier=IDENTIFIER, reason="tampered"),
    RefusedEnvelopeCase(name="bytes_appended", content=ENVELOPE + b"\n", identifier=IDENTIFIER, reason="tampered"),
    RefusedEnvelopeCase(
        name="copied_to_another_identifier",
        content=ENVELOPE,
        identifier="c0ffee00-5c3d-4b1e-a0f7-3c9d2b6e8f01",
        reason="tampered",
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in REFUSED_ENVELOPE_CASES])
def test_envelope_that_does_not_authenticate_is_refused(case: RefusedEnvelopeCase) -> None:
    with pytest.raises(StorageIntegrityError) as excinfo:
        open_envelope(identifier=case.identifier, content=case.content, key=StorageKey.derive(SECRET))

    assert (excinfo.value.identifier, excinfo.value.reason) == (case.identifier, case.reason)
    assert excinfo.value.message == (
        f"The stored content {case.identifier} failed its integrity check and was not served."
    )


def test_only_a_complete_envelope_of_a_known_version_is_recognized() -> None:
    assert is_envelope(ENVELOPE)
    assert not is_envelope(CONTENT)
    assert not is_envelope(ENVELOPE[:40])
    assert not is_envelope(_flip(ENVELOPE, 4))


def test_key_comes_from_an_explicitly_set_secret() -> None:
    assert storage_key_from_settings(settings=SecuritySettings(secret_key=SECRET)).fingerprint == SECRET_FINGERPRINT


def test_generated_secret_is_refused() -> None:
    with pytest.raises(
        StorageEncryptionError,
        match=(
            r"^Storage encryption requires INFRAHUB_SECURITY_SECRET_KEY to be set, with the same value on every "
            r"API server; without it each process generates its own random secret$"
        ),
    ):
        storage_key_from_settings(settings=SecuritySettings())


@dataclass
class UnfitSecretCase:
    name: str
    secret: str
    message: str


UNFIT_SECRET_CASES = [
    UnfitSecretCase(
        name="published_example",
        secret="327f747f-efac-42be-9e73-999f08f86b92",
        message=(
            r"^INFRAHUB_SECURITY_SECRET_KEY still has the value published in Infrahub's example deployment files; "
            r"set a unique random secret before using storage encryption$"
        ),
    ),
    UnfitSecretCase(
        name="published_example_with_trailing_quote",
        secret='327f747f-efac-42be-9e73-999f08f86b92"',
        message=r"^INFRAHUB_SECURITY_SECRET_KEY still has the value published in Infrahub's example deployment files",
    ),
    UnfitSecretCase(
        name="too_short",
        secret="0123456789abcdef0123456789abcde",
        message=(
            r"^INFRAHUB_SECURITY_SECRET_KEY must be at least 32 characters long to be used for storage encryption$"
        ),
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in UNFIT_SECRET_CASES])
def test_unfit_secret_is_refused(case: UnfitSecretCase) -> None:
    with pytest.raises(StorageEncryptionError, match=case.message):
        storage_key_from_settings(settings=SecuritySettings(secret_key=case.secret))
