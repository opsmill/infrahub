from __future__ import annotations

from infrahub.git.fingerprint.registry import FingerprintKind, FingerprintRegistry


def test_register_then_get_returns_value() -> None:
    registry = FingerprintRegistry()
    registry.register(kind=FingerprintKind.QUERY, name="q1", fingerprint="abc")
    assert registry.get(kind=FingerprintKind.QUERY, name="q1") == "abc"


def test_get_unknown_returns_none() -> None:
    registry = FingerprintRegistry()
    assert registry.get(kind=FingerprintKind.TRANSFORMATION, name="missing") is None


def test_same_name_across_kinds_is_distinct() -> None:
    registry = FingerprintRegistry()
    registry.register(kind=FingerprintKind.QUERY, name="shared", fingerprint="q")
    registry.register(kind=FingerprintKind.TRANSFORMATION, name="shared", fingerprint="t")
    assert registry.get(kind=FingerprintKind.QUERY, name="shared") == "q"
    assert registry.get(kind=FingerprintKind.TRANSFORMATION, name="shared") == "t"
