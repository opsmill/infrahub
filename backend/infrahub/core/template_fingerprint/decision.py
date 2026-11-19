from __future__ import annotations

from infrahub.core.template_fingerprint.models import (
    FingerprintDecision,
    FingerprintKey,
    RecordedFingerprint,
    SchemaFingerprints,
    TemplateFamily,
)


def decide_fingerprint_changes(
    family: TemplateFamily,
    event_branch: str | None,
    branch_deleted: bool,
    default_branch: str,
    schema: SchemaFingerprints,
    recorded: list[RecordedFingerprint],
) -> FingerprintDecision:
    """Compare the schema fingerprints with the recorded ones and decide what to recompute, record and delete.

    Deletions cover every branch; recompute and recording cover the event branch only, so a flow never
    writes the records of a branch whose own schema update has not been processed yet.
    """
    to_delete = [
        record.key for record in recorded if record.key.kind not in schema.by_branch.get(record.key.branch, {})
    ]

    if branch_deleted or event_branch is None or event_branch not in schema.by_branch:
        return FingerprintDecision(to_recompute=[], to_record=[], to_delete=to_delete, skipped_identical=[])

    recorded_on_event_branch = {
        record.key.kind: record.fingerprint for record in recorded if record.key.branch == event_branch
    }
    default_fingerprints = schema.by_branch.get(default_branch, {})

    to_recompute: list[str] = []
    to_record: list[RecordedFingerprint] = []
    skipped_identical: list[str] = []
    for kind, fingerprint in sorted(schema.by_branch[event_branch].items()):
        if recorded_on_event_branch.get(kind) == fingerprint:
            continue

        to_record.append(
            RecordedFingerprint(
                key=FingerprintKey(family=family, branch=event_branch, kind=kind), fingerprint=fingerprint
            )
        )
        if event_branch != default_branch and default_fingerprints.get(kind) == fingerprint:
            skipped_identical.append(kind)
        else:
            to_recompute.append(kind)

    return FingerprintDecision(
        to_recompute=to_recompute, to_record=to_record, to_delete=to_delete, skipped_identical=skipped_identical
    )
