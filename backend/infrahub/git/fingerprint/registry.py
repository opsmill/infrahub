"""Per-import in-memory snapshot of freshly-computed fingerprints."""

from __future__ import annotations

from enum import StrEnum


class FingerprintKind(StrEnum):
    QUERY = "query"
    TRANSFORMATION = "transformation"
    ARTIFACT_DEFINITION = "artifact_definition"
    GENERATOR_DEFINITION = "generator_definition"


class FingerprintRegistry:
    """A `{(kind, name): fingerprint}` snapshot populated in dependency order within one import.

    Higher layers read the value computed earlier in the same import, so a dependent
    fingerprint never lags a previously-stored graph value by an import.
    """

    def __init__(self) -> None:
        self._store: dict[tuple[FingerprintKind, str], str] = {}

    def register(self, *, kind: FingerprintKind, name: str, fingerprint: str) -> None:
        self._store[kind, name] = fingerprint

    def get(self, *, kind: FingerprintKind, name: str) -> str | None:
        return self._store.get((kind, name))
