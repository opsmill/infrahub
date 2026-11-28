#!/usr/bin/env python3
"""Print the result of a Spec Kit workflow run, for the command that started it.

Usage: workflow_result.py [RUN_ID]    (default: the most recent run of the project)

It prints the status of the run, how many times each agent phase started, the
verdict line that each phase ended with, the coverage of the critique and of
the review, and the reason of a run that stopped.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

RUNS = Path(".specify/workflows/runs")
WORKFLOWS = Path(".specify/workflows")
# A line such as `ALIGNMENT: ALIGNED` or `STATUS: DONE | SPEC_DIR: ...`.
VERDICT = re.compile(r"^[A-Z][A-Z_]*: \S")
# What a stop step of a workflow prints before it ends the run.
STOP = re.compile(r"\b(?:BLOCKED|INCOMPLETE): [^'\"]*")
# For each quality gate: the verdict line that holds its mode, the modes that
# give a full check, and how to get a full check.
GATES = {
    "critique": (
        re.compile(r"CRITIQUE_VERDICT: .*\bCRITIQUE: ([a-z/]+)"),
        ("extension",),
        "install the critique extension: specify bundle install opsmill-sdd",
    ),
    "review": (
        re.compile(r"STATUS: .*\bREVIEW: ([a-z/]+)"),
        ("plugin", "command"),
        (
            "install the review plugin in Claude Code: "
            "/plugin install pr-review-toolkit@claude-plugins-official"
        ),
    ),
}
REDUCED = {
    "fallback": "REDUCED (fallback): a built-in {gate} of reduced depth ran",
    "none": "NONE: no {gate} ran",
}
# The critique phase reports `fallback` or `none` also when the extension is
# installed but could not run, for example because Claude Code refused a tool.
NOT_RUN = (
    "the {gate} extension is installed but did not run; "
    "the output of the {gate} phase says why, often a tool that Claude Code refused"
)


def installed(gate: str) -> bool:
    """Whether the extension of a quality gate is installed in the project."""
    if gate != "critique":
        return False
    registry = Path(".specify/extensions/.registry")
    return Path(".specify/extensions/critique").is_dir() or (
        registry.exists() and '"critique"' in registry.read_text()
    )


def last_line(text: object) -> str:
    lines = str(text or "").strip().splitlines()
    return lines[-1].strip() if lines else ""


def state_of(run_id: str | None) -> tuple[Path, dict]:
    states = (
        [RUNS / run_id / "state.json"] if run_id else list(RUNS.glob("*/state.json"))
    )
    states = [path for path in states if path.exists()]
    if not states:
        sys.exit(f"no workflow run found in {RUNS}")
    path = max(states, key=lambda path: path.stat().st_mtime)
    return path.parent, json.loads(path.read_text())


def phases(run: Path) -> Counter:
    """How many times each agent phase started, nested workflows included."""
    started: Counter = Counter()
    log = run / "log.jsonl"
    if not log.exists():
        return started
    for line in log.read_text().splitlines():
        event = json.loads(line)
        if event.get("event") == "step_started" and event.get("type") == "command":
            # A step of a repeated pass is named `design:critique:1`.
            names = [
                part
                for part in str(event.get("step_id", "")).split(":")
                if not part.isdigit()
            ]
            started[names[-1] if names else "?"] += 1
    return started


def verdicts(state: dict) -> list[str]:
    """The verdict line of each step, and of each output of a nested workflow."""
    lines = []
    for name, result in state.get("step_results", {}).items():
        output = result.get("output") or {}
        for key, value in output.items():
            if key in ("stderr", "error") or not isinstance(value, str):
                continue
            line = last_line(value)
            if VERDICT.match(line):
                lines.append(f"{name}{'' if key == 'stdout' else '.' + key} -> {line}")
    return lines


def coverage(lines: list[str]) -> list[str]:
    """One line per quality gate that ran, from the last verdict that names its mode."""
    report = []
    for gate, (pattern, full, remedy) in GATES.items():
        modes = [match.group(1) for match in map(pattern.search, lines) if match]
        if not modes or modes[-1] == "n/a":
            continue
        mode = modes[-1]
        if mode in full:
            report.append(f"coverage: {gate} full ({mode})")
        else:
            reduced = REDUCED.get(mode, f"REDUCED ({mode})").format(gate=gate)
            if installed(gate):
                remedy = NOT_RUN.format(gate=gate)
            report.append(f"coverage: {gate} {reduced}; {remedy}")
    return report


def stop_reasons(state: dict) -> list[str]:
    """Why the run stopped: what the stop step printed, or what its workflow file says it prints."""
    recorded = [
        match.group(0).strip()
        for result in state.get("step_results", {}).values()
        for match in STOP.finditer(
            str((result.get("output") or {}).get("stderr") or "")
        )
    ]
    step = state.get("current_step_id")
    if recorded or state.get("status") != "failed" or not step:
        return recorded
    # A nested workflow keeps the output of its steps to itself.
    for workflow in WORKFLOWS.glob("*/workflow.yml"):
        text = workflow.read_text()
        found = re.search(rf"^\s*- id: {re.escape(step)}\s*$", text, re.MULTILINE)
        if found:
            block = re.split(
                r"^\s*- id: ", text[found.end() :], maxsplit=1, flags=re.MULTILINE
            )[0]
            return [match.group(0).strip() for match in STOP.finditer(block)]
    return []


def main() -> int:
    run, state = state_of(sys.argv[1] if len(sys.argv) > 1 else None)
    print(
        f"run {state.get('run_id')} | workflow {state.get('workflow_id')} | {state.get('status')}"
    )
    started = phases(run)
    if started:
        print(
            "phases started: "
            + ", ".join(f"{name} x{count}" for name, count in started.items())
        )
    lines = verdicts(state)
    for line in lines:
        print(line)
    for line in coverage(lines):
        print(line)
    reasons = stop_reasons(state)
    for reason in reasons:
        print(reason if len(reasons) == 1 else f"possible reason: {reason}")
    if state.get("status") == "failed":
        print(f"failed at step {state.get('current_step_id')}: {state.get('error')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
