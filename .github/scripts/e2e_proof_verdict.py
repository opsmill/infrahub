"""Classify a proof-run junit report against the bug pipeline's RED/GREEN phase contract.

Usage: e2e_proof_verdict.py --phase {red,green} --junit <path>

Prints ``verdict=<...>`` and ``reason=<one line>`` on stdout and exits 0 only when
the phase contract is satisfied (RED needs exactly one testcase failing on an
assertion, GREEN needs exactly one passing testcase); any infrastructure error,
skip, or unexpected testcase count is inconclusive.
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

RED_CONFIRMED = "red_confirmed"
GREEN_CONFIRMED = "green_confirmed"
DOES_NOT_REPRODUCE = "does_not_reproduce"
INCONCLUSIVE = "inconclusive"

SATISFYING_VERDICT = {"red": RED_CONFIRMED, "green": GREEN_CONFIRMED}

REASON_EXCERPT_LIMIT = 160


def _one_line(text: str) -> str:
    return " ".join(text.split())[:REASON_EXCERPT_LIMIT]


def _load_cases(junit_path: Path) -> tuple[list[ET.Element], str | None]:
    if not junit_path.is_file():
        return [], "junit report missing"
    try:
        root = ET.parse(junit_path).getroot()
    except ET.ParseError:
        return [], "junit report is not valid XML"
    return list(root.iter("testcase")), None


def _structural_problem(cases: list[ET.Element]) -> str | None:
    if not cases:
        return "no test collected"
    errors = [case for case in cases if case.find("error") is not None]
    if errors:
        return f"{len(errors)} error(s) during setup/teardown -- infrastructure, not the bug"
    if len(cases) != 1:
        return f"expected exactly one testcase, found {len(cases)}"
    if cases[0].find("skipped") is not None:
        return "the test was skipped, not executed"
    return None


def _evaluate_red(failure: ET.Element | None) -> tuple[str, str]:
    if failure is None:
        return DOES_NOT_REPRODUCE, "test passed without the fix applied -- it does not reproduce the bug"
    # The space keeps a message/text boundary from fabricating the keyword.
    combined = (failure.get("message") or "") + " " + (failure.text or "")
    excerpt = _one_line(combined)
    if "AssertionError" in combined:
        return RED_CONFIRMED, f"test failed on its assertion: {excerpt}"
    return INCONCLUSIVE, f"test failed but not on an assertion: {excerpt}"


def _evaluate_green(failure: ET.Element | None) -> tuple[str, str]:
    if failure is None:
        return GREEN_CONFIRMED, "reproduction test passes with the fix applied"
    excerpt = _one_line((failure.get("message") or "") + " " + (failure.text or ""))
    return INCONCLUSIVE, f"test still fails with the fix applied: {excerpt}"


def evaluate(phase: str, junit_path: Path) -> tuple[str, str]:
    """Return ``(verdict, reason)`` for the given phase and junit report path."""
    cases, load_problem = _load_cases(junit_path)
    if load_problem:
        return INCONCLUSIVE, load_problem
    structural_problem = _structural_problem(cases)
    if structural_problem:
        return INCONCLUSIVE, structural_problem
    failure = cases[0].find("failure")
    if phase == "red":
        return _evaluate_red(failure)
    return _evaluate_green(failure)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point; returns the process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("red", "green"), required=True)
    parser.add_argument("--junit", type=Path, required=True)
    args = parser.parse_args(argv)

    verdict, reason = evaluate(args.phase, args.junit)
    print(f"verdict={verdict}")
    print(f"reason={reason}")
    return 0 if verdict == SATISFYING_VERDICT[args.phase] else 1


if __name__ == "__main__":
    sys.exit(main())
