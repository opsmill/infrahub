from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from infrahub.core.node.standard import StandardNode


class TemplateFamily(StrEnum):
    """Derived-value families whose template fingerprints are recorded.

    The values equal the trigger type values of the same families, so an automation name prefix maps
    to a family directly.
    """

    DISPLAY_LABEL_JINJA2 = "display_label_jinja2"
    HUMAN_FRIENDLY_ID = "human_friendly_id"


@dataclass(frozen=True)
class FingerprintKey:
    family: TemplateFamily
    branch: str
    kind: str


@dataclass(frozen=True)
class RecordedFingerprint:
    key: FingerprintKey
    fingerprint: str


@dataclass(frozen=True)
class SchemaFingerprints:
    """Fingerprints of one family computed from the schema, by branch then by kind."""

    family: TemplateFamily
    by_branch: dict[str, dict[str, str]]

    def as_records(self) -> list[RecordedFingerprint]:
        return [
            RecordedFingerprint(
                key=FingerprintKey(family=self.family, branch=branch, kind=kind), fingerprint=fingerprint
            )
            for branch, fingerprints in self.by_branch.items()
            for kind, fingerprint in fingerprints.items()
        ]


@dataclass(frozen=True)
class FingerprintDecision:
    to_recompute: list[str]
    to_record: list[RecordedFingerprint]
    to_delete: list[FingerprintKey]
    skipped_identical: list[str]


class TemplateFingerprint(StandardNode):
    """Fingerprint of the template last applied to the stored values of one kind on one branch.

    The branch is a plain property: the vertex is not branch-aware and an update overwrites it.
    """

    family: str
    branch: str
    kind: str
    fingerprint: str
