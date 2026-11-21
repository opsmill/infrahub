from __future__ import annotations

from infrahub.core.template_fingerprint.decision import decide_fingerprint_changes
from infrahub.core.template_fingerprint.models import (
    FingerprintDecision,
    FingerprintKey,
    RecordedFingerprint,
    SchemaFingerprints,
    TemplateFamily,
)

FAMILY = TemplateFamily.DISPLAY_LABEL_JINJA2
DEFAULT = "main"


def _recorded(branch: str, kind: str, fingerprint: str) -> RecordedFingerprint:
    return RecordedFingerprint(key=FingerprintKey(family=FAMILY, branch=branch, kind=kind), fingerprint=fingerprint)


def _decide(
    by_branch: dict[str, dict[str, str]],
    recorded: list[RecordedFingerprint],
    event_branch: str | None,
    branch_deleted: bool = False,
) -> FingerprintDecision:
    return decide_fingerprint_changes(
        family=FAMILY,
        event_branch=event_branch,
        branch_deleted=branch_deleted,
        default_branch=DEFAULT,
        schema=SchemaFingerprints(family=FAMILY, by_branch=by_branch),
        recorded=recorded,
    )


def test_record_of_branch_out_of_scope_is_deleted() -> None:
    decision = _decide(
        by_branch={DEFAULT: {"TestCar": "h1"}},
        recorded=[_recorded(DEFAULT, "TestCar", "h1"), _recorded("gone", "TestCar", "h1")],
        event_branch=DEFAULT,
    )

    assert decision == FingerprintDecision(
        to_recompute=[],
        to_record=[],
        to_delete=[FingerprintKey(family=FAMILY, branch="gone", kind="TestCar")],
        skipped_identical=[],
    )


def test_record_of_kind_without_template_on_in_scope_branch_is_deleted() -> None:
    decision = _decide(
        by_branch={DEFAULT: {"TestCar": "h1"}, "b1": {"TestCar": "h1"}},
        recorded=[_recorded("b1", "TestCar", "h1"), _recorded("b1", "TestPerson", "h2")],
        event_branch=DEFAULT,
    )

    assert decision.to_delete == [FingerprintKey(family=FAMILY, branch="b1", kind="TestPerson")]


def test_branch_deleted_records_and_recomputes_nothing() -> None:
    decision = _decide(
        by_branch={DEFAULT: {"TestCar": "h1"}, "b1": {"TestCar": "h2"}},
        recorded=[],
        event_branch="b1",
        branch_deleted=True,
    )

    assert decision == FingerprintDecision(to_recompute=[], to_record=[], to_delete=[], skipped_identical=[])


def test_no_event_branch_records_and_recomputes_nothing() -> None:
    decision = _decide(by_branch={DEFAULT: {"TestCar": "h1"}}, recorded=[], event_branch=None)

    assert decision == FingerprintDecision(to_recompute=[], to_record=[], to_delete=[], skipped_identical=[])


def test_event_branch_out_of_scope_records_and_recomputes_nothing_but_still_deletes() -> None:
    decision = _decide(
        by_branch={DEFAULT: {"TestCar": "h1"}},
        recorded=[_recorded("b1", "TestCar", "h2")],
        event_branch="b1",
    )

    assert decision == FingerprintDecision(
        to_recompute=[],
        to_record=[],
        to_delete=[FingerprintKey(family=FAMILY, branch="b1", kind="TestCar")],
        skipped_identical=[],
    )


def test_recorded_equal_to_schema_does_nothing() -> None:
    decision = _decide(
        by_branch={DEFAULT: {"TestCar": "h1"}, "b1": {"TestCar": "h2"}},
        recorded=[_recorded(DEFAULT, "TestCar", "h1"), _recorded("b1", "TestCar", "h2")],
        event_branch="b1",
    )

    assert decision == FingerprintDecision(to_recompute=[], to_record=[], to_delete=[], skipped_identical=[])


def test_default_branch_missing_record_recomputes_and_records() -> None:
    decision = _decide(by_branch={DEFAULT: {"TestCar": "h1"}}, recorded=[], event_branch=DEFAULT)

    assert decision == FingerprintDecision(
        to_recompute=["TestCar"],
        to_record=[_recorded(DEFAULT, "TestCar", "h1")],
        to_delete=[],
        skipped_identical=[],
    )


def test_default_branch_different_record_recomputes_and_records() -> None:
    decision = _decide(
        by_branch={DEFAULT: {"TestCar": "h-new"}},
        recorded=[_recorded(DEFAULT, "TestCar", "h-old")],
        event_branch=DEFAULT,
    )

    assert decision == FingerprintDecision(
        to_recompute=["TestCar"],
        to_record=[_recorded(DEFAULT, "TestCar", "h-new")],
        to_delete=[],
        skipped_identical=[],
    )


def test_other_branch_template_identical_to_default_is_skipped_and_recorded() -> None:
    decision = _decide(
        by_branch={DEFAULT: {"TestCar": "h1"}, "b1": {"TestCar": "h1"}},
        recorded=[_recorded(DEFAULT, "TestCar", "h1")],
        event_branch="b1",
    )

    assert decision == FingerprintDecision(
        to_recompute=[],
        to_record=[_recorded("b1", "TestCar", "h1")],
        to_delete=[],
        skipped_identical=["TestCar"],
    )


def test_other_branch_template_different_from_default_recomputes_and_records() -> None:
    decision = _decide(
        by_branch={DEFAULT: {"TestCar": "h1"}, "b1": {"TestCar": "h2"}},
        recorded=[_recorded(DEFAULT, "TestCar", "h1"), _recorded("b1", "TestCar", "h1")],
        event_branch="b1",
    )

    assert decision == FingerprintDecision(
        to_recompute=["TestCar"],
        to_record=[_recorded("b1", "TestCar", "h2")],
        to_delete=[],
        skipped_identical=[],
    )


def test_other_branch_kind_missing_on_default_recomputes_and_records() -> None:
    decision = _decide(
        by_branch={DEFAULT: {"TestCar": "h1"}, "b1": {"TestCar": "h1", "TestBike": "h3"}},
        recorded=[_recorded("b1", "TestCar", "h1")],
        event_branch="b1",
    )

    assert decision == FingerprintDecision(
        to_recompute=["TestBike"],
        to_record=[_recorded("b1", "TestBike", "h3")],
        to_delete=[],
        skipped_identical=[],
    )


def test_records_of_other_branches_are_never_written() -> None:
    decision = _decide(
        by_branch={DEFAULT: {"TestCar": "h1"}, "b1": {"TestCar": "h2"}, "b2": {"TestCar": "h3"}},
        recorded=[],
        event_branch="b1",
    )

    assert decision == FingerprintDecision(
        to_recompute=["TestCar"],
        to_record=[_recorded("b1", "TestCar", "h2")],
        to_delete=[],
        skipped_identical=[],
    )
