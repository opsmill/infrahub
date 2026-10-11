from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub import config
from infrahub.artifacts.high_cost import checks_in_sequences, skipped_check_message
from infrahub.core.constants import ValidatorConclusion

if TYPE_CHECKING:
    import pytest


async def _check(name: str, conclusion: ValidatorConclusion, runs: list[str]) -> ValidatorConclusion:
    runs.append(name)
    return conclusion


async def test_checks_run_one_after_the_other_in_each_sequence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config.SETTINGS.graphql_cost, "high_cost_renders_at_once", 2)
    runs: list[str] = []
    checks = [_check(name=f"check-{index}", conclusion=ValidatorConclusion.SUCCESS, runs=runs) for index in range(5)]

    sequences = checks_in_sequences(checks=checks)

    assert len(sequences) == 2
    assert await sequences[0] == ValidatorConclusion.SUCCESS
    assert runs == ["check-0", "check-2", "check-4"]
    assert await sequences[1] == ValidatorConclusion.SUCCESS
    assert runs == ["check-0", "check-2", "check-4", "check-1", "check-3"]


async def test_a_sequence_with_a_failed_check_fails_and_runs_every_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config.SETTINGS.graphql_cost, "high_cost_renders_at_once", 1)
    runs: list[str] = []
    checks = [
        _check(name="first", conclusion=ValidatorConclusion.FAILURE, runs=runs),
        _check(name="second", conclusion=ValidatorConclusion.SUCCESS, runs=runs),
    ]

    sequences = checks_in_sequences(checks=checks)

    assert len(sequences) == 1
    assert await sequences[0] == ValidatorConclusion.FAILURE
    assert runs == ["first", "second"]


def test_no_sequence_without_checks() -> None:
    assert checks_in_sequences(checks=[]) == []


def test_skipped_check_message_gives_the_estimate_and_the_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config.SETTINGS.graphql_cost, "high_cost_database_rows", 250_000)

    assert skipped_check_message(query_name="cabling_plan", worst_case_database_rows=991_262) == (
        "Not rendered: one run of the query cabling_plan is estimated at 991,262 worst-case database rows for "
        "this target, and the limit is 250,000. Infrahub generates this artifact after the merge."
    )
    assert "could not be estimated for this target" in skipped_check_message(
        query_name="cabling_plan", worst_case_database_rows=None
    )
