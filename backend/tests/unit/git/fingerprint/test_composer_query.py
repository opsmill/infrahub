from __future__ import annotations

from infrahub.git.fingerprint.composer import QueryFingerprintInput
from infrahub.git.fingerprint.registry import FingerprintKind
from tests.unit.git.fingerprint.conftest import build_composer


def test_identical_query_text_produces_identical_digest() -> None:
    first = build_composer().compose_query(QueryFingerprintInput(name="q", query_text="query { a }"))
    second = build_composer().compose_query(QueryFingerprintInput(name="q", query_text="query { a }"))
    assert first == second


def test_different_query_text_produces_different_digest() -> None:
    first = build_composer().compose_query(QueryFingerprintInput(name="q", query_text="query { a }"))
    second = build_composer().compose_query(QueryFingerprintInput(name="q", query_text="query { b }"))
    assert first != second


def test_edit_then_revert_is_net_zero() -> None:
    original = build_composer().compose_query(QueryFingerprintInput(name="q", query_text="query { a }"))
    build_composer().compose_query(QueryFingerprintInput(name="q", query_text="query { edited }"))
    reverted = build_composer().compose_query(QueryFingerprintInput(name="q", query_text="query { a }"))
    assert original == reverted


def test_compose_query_registers_result() -> None:
    composer = build_composer()
    digest = composer.compose_query(QueryFingerprintInput(name="q", query_text="query { a }"))
    assert composer.registry.get(kind=FingerprintKind.QUERY, name="q") == digest
