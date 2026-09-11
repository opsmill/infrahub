from __future__ import annotations

from typing import TYPE_CHECKING

import e2e_proof_verdict

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

PASSING_CASE = '<testcase classname="tests.e2e.test_bug" name="test_bug_repro" time="12.3" />'

ASSERTION_FAILURE_CASE = (
    '<testcase classname="tests.e2e.test_bug" name="test_bug_repro" time="12.3">'
    '<failure message="AssertionError: expected the chip to be visible">'
    "Traceback: assert chip.is_visible()\nAssertionError: expected the chip to be visible"
    "</failure></testcase>"
)

ASSERTION_IN_TEXT_ONLY_CASE = (
    '<testcase classname="tests.e2e.test_bug" name="test_bug_repro" time="12.3">'
    '<failure message="assert False">'
    "def test_bug_repro():\n&gt;    assert chip.is_visible()\nE    AssertionError"
    "</failure></testcase>"
)

TIMEOUT_FAILURE_CASE = (
    '<testcase classname="tests.e2e.test_bug" name="test_bug_repro" time="60.0">'
    '<failure message="playwright._impl._errors.TimeoutError: Timeout 30000ms exceeded.">'
    "TimeoutError: Timeout 30000ms exceeded while waiting for selector"
    "</failure></testcase>"
)

SETUP_ERROR_CASE = (
    '<testcase classname="tests.e2e.test_bug" name="test_bug_repro" time="0.1">'
    '<error message="failed on setup with ContainerStartException">'
    "compose boot failed"
    "</error></testcase>"
)


def _write_junit(tmp_path: Path, *cases: str) -> Path:
    junit = tmp_path / "playwright-junit.xml"
    junit.write_text(
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<testsuites><testsuite name="pytest" tests="{len(cases)}">{"".join(cases)}</testsuite></testsuites>'
    )
    return junit


def _run(phase: str, junit: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    exit_code = e2e_proof_verdict.main(["--phase", phase, "--junit", str(junit)])
    out_lines = capsys.readouterr().out.splitlines()
    verdict = out_lines[0].removeprefix("verdict=")
    reason = out_lines[1].removeprefix("reason=")
    return exit_code, verdict, reason


def test_red_assertion_failure_is_confirmed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    junit = _write_junit(tmp_path, ASSERTION_FAILURE_CASE)
    exit_code, verdict, reason = _run("red", junit, capsys)
    assert exit_code == 0
    assert verdict == "red_confirmed"
    assert "assertion" in reason


def test_red_assertion_only_in_failure_text_is_confirmed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    junit = _write_junit(tmp_path, ASSERTION_IN_TEXT_ONLY_CASE)
    exit_code, verdict, _ = _run("red", junit, capsys)
    assert exit_code == 0
    assert verdict == "red_confirmed"


def test_red_setup_error_is_inconclusive(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    junit = _write_junit(tmp_path, SETUP_ERROR_CASE)
    exit_code, verdict, reason = _run("red", junit, capsys)
    assert exit_code == 1
    assert verdict == "inconclusive"
    assert "infrastructure" in reason


def test_red_pass_does_not_reproduce(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    junit = _write_junit(tmp_path, PASSING_CASE)
    exit_code, verdict, _ = _run("red", junit, capsys)
    assert exit_code == 1
    assert verdict == "does_not_reproduce"


def test_red_non_assertion_failure_is_inconclusive(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    junit = _write_junit(tmp_path, TIMEOUT_FAILURE_CASE)
    exit_code, verdict, reason = _run("red", junit, capsys)
    assert exit_code == 1
    assert verdict == "inconclusive"
    assert "not on an assertion" in reason


def test_green_pass_is_confirmed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    junit = _write_junit(tmp_path, PASSING_CASE)
    exit_code, verdict, _ = _run("green", junit, capsys)
    assert exit_code == 0
    assert verdict == "green_confirmed"


def test_green_failure_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    junit = _write_junit(tmp_path, ASSERTION_FAILURE_CASE)
    exit_code, verdict, _ = _run("green", junit, capsys)
    assert exit_code == 1
    assert verdict == "inconclusive"


def test_zero_testcases_is_inconclusive(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    junit = _write_junit(tmp_path)
    exit_code, verdict, reason = _run("red", junit, capsys)
    assert exit_code == 1
    assert verdict == "inconclusive"
    assert reason == "no test collected"


def test_two_testcases_is_inconclusive(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    junit = _write_junit(tmp_path, ASSERTION_FAILURE_CASE, PASSING_CASE)
    exit_code, verdict, reason = _run("red", junit, capsys)
    assert exit_code == 1
    assert verdict == "inconclusive"
    assert "exactly one testcase" in reason


def test_missing_report_is_inconclusive(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code, verdict, reason = _run("green", tmp_path / "absent.xml", capsys)
    assert exit_code == 1
    assert verdict == "inconclusive"
    assert reason == "junit report missing"


def test_skipped_testcase_is_inconclusive(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    skipped = (
        '<testcase classname="tests.e2e.test_bug" name="test_bug_repro" time="0.0">'
        '<skipped message="shard not selected" /></testcase>'
    )
    junit = _write_junit(tmp_path, skipped)
    exit_code, verdict, _ = _run("green", junit, capsys)
    assert exit_code == 1
    assert verdict == "inconclusive"


def test_stdout_is_exactly_the_two_contract_lines(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    junit = _write_junit(tmp_path, ASSERTION_FAILURE_CASE)
    e2e_proof_verdict.main(["--phase", "red", "--junit", str(junit)])
    out_lines = capsys.readouterr().out.splitlines()
    assert len(out_lines) == 2
    assert out_lines[0].startswith("verdict=")
    assert out_lines[1].startswith("reason=")


ASSERTION_IN_MESSAGE_ONLY_CASE = (
    '<testcase classname="tests.e2e.test_bug" name="test_bug_repro" time="12.3">'
    '<failure message="AssertionError: expected the chip to be visible">'
    "Traceback with no keyword of its own"
    "</failure></testcase>"
)

BOUNDARY_CONCATENATION_CASE = (
    '<testcase classname="tests.e2e.test_bug" name="test_bug_repro" time="12.3">'
    '<failure message="fatal: unexpected Assertion">'
    "Error: browser crashed before the check ran"
    "</failure></testcase>"
)


def test_red_assertion_only_in_message_is_confirmed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    junit = _write_junit(tmp_path, ASSERTION_IN_MESSAGE_ONLY_CASE)
    exit_code, verdict, _ = _run("red", junit, capsys)
    assert exit_code == 0
    assert verdict == "red_confirmed"


def test_message_text_boundary_does_not_fabricate_an_assertion(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    junit = _write_junit(tmp_path, BOUNDARY_CONCATENATION_CASE)
    exit_code, verdict, reason = _run("red", junit, capsys)
    assert exit_code == 1
    assert verdict == "inconclusive"
    assert "not on an assertion" in reason


def test_truncated_xml_is_inconclusive(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    junit = tmp_path / "playwright-junit.xml"
    junit.write_text('<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest"><testcase')
    exit_code, verdict, reason = _run("red", junit, capsys)
    assert exit_code == 1
    assert verdict == "inconclusive"
    assert reason == "junit report is not valid XML"


def test_error_alongside_passing_case_is_inconclusive(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    junit = _write_junit(tmp_path, SETUP_ERROR_CASE, PASSING_CASE)
    exit_code, verdict, reason = _run("red", junit, capsys)
    assert exit_code == 1
    assert verdict == "inconclusive"
    assert "infrastructure" in reason
