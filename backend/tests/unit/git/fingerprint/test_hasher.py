from __future__ import annotations

from infrahub.git.fingerprint.hasher import FingerprintHasher, canonical_json


def test_hash_is_deterministic() -> None:
    hasher = FingerprintHasher()
    assert hasher.hash(["a", "b", "c"]) == hasher.hash(["a", "b", "c"])


def test_hash_is_order_sensitive() -> None:
    hasher = FingerprintHasher()
    assert hasher.hash(["a", "b"]) != hasher.hash(["b", "a"])


def test_hash_term_boundaries_are_unambiguous() -> None:
    hasher = FingerprintHasher()
    # Without length-prefixing these two term lists would collide on concatenation.
    assert hasher.hash(["ab", "c"]) != hasher.hash(["a", "bc"])


def test_hash_returns_sha256_hex_digest() -> None:
    digest = FingerprintHasher().hash(["value"])
    assert len(digest) == 64
    assert int(digest, 16) >= 0


def test_canonical_json_is_key_order_independent() -> None:
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})


def test_canonical_json_has_no_insignificant_whitespace() -> None:
    assert canonical_json({"a": 1, "b": [1, 2]}) == '{"a":1,"b":[1,2]}'
