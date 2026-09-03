"""Invoke tasks that validate the wiring of the GitHub Actions CI workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from invoke import Context, Exit, task

from .utils import REPO_BASE

CI_WORKFLOW = Path(".github/workflows/ci.yml")
HUGE_RUNNER_GROUP = "huge-runners"
GATE_JOB = "huge-runner-gate"
REPORTER_JOBS: frozenset[str] = frozenset({"coverall-report"})
"""Jobs that aggregate huge-runner results: they run after the huge-runner jobs, so they cannot feed the gate."""


@dataclass(frozen=True)
class JobWiring:
    """The parts of a workflow job the gate check reasons about."""

    name: str
    """Job id, the key under ``jobs:``."""

    needs: frozenset[str]
    """Job ids listed under ``needs``."""

    runner_groups: frozenset[str]
    """Runner groups the job runs on, including those of a local reusable workflow it calls."""

    condition: str
    """The job-level ``if`` expression, empty when absent."""

    @property
    def on_huge_runners(self) -> bool:
        """Whether the job, or the reusable workflow it calls, takes a huge runner."""
        return HUGE_RUNNER_GROUP in self.runner_groups


def _load_yaml(path: Path) -> dict[str, Any]:
    import yaml  # tasks modules load on every invoke command; keep non-stdlib imports function-local

    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _runner_groups(job: dict[str, Any], repo_root: Path) -> frozenset[str]:
    runs_on = job.get("runs-on")
    if isinstance(runs_on, dict) and "group" in runs_on:
        return frozenset({str(runs_on["group"])})
    uses = job.get("uses")
    if isinstance(uses, str) and uses.startswith("./"):
        called = _load_yaml(path=repo_root / uses)
        return frozenset().union(
            *(_runner_groups(job=called_job, repo_root=repo_root) for called_job in called.get("jobs", {}).values())
        )
    return frozenset()


def load_job_wiring(workflow_path: Path, repo_root: Path) -> dict[str, JobWiring]:
    """Read the jobs of a workflow into the shape the gate check reasons about.

    Args:
        workflow_path: Workflow file, relative to ``repo_root``.
        repo_root: Repository root, used to resolve ``uses: ./.github/workflows/...`` calls.

    Returns:
        The jobs keyed by job id.

    """
    workflow = _load_yaml(path=repo_root / workflow_path)
    wiring: dict[str, JobWiring] = {}
    for name, job in workflow.get("jobs", {}).items():
        needs = job.get("needs", [])
        if isinstance(needs, str):
            needs = [needs]
        wiring[name] = JobWiring(
            name=name,
            needs=frozenset(needs),
            runner_groups=_runner_groups(job=job, repo_root=repo_root),
            condition=str(job.get("if", "")),
        )
    return wiring


def _closes_at_end(text: str) -> bool:
    """Whether ``text`` is a single parenthesised group, ``(`` first and its matching ``)`` last."""
    if not text.startswith("(") or not text.endswith(")"):
        return False
    depth = 0
    in_string = False
    for index, char in enumerate(text):
        if in_string:
            in_string = char != "'"
        elif char == "'":
            in_string = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index == len(text) - 1
    return False


def _top_level_conjuncts(expression: str) -> list[str] | None:
    """Split a GitHub Actions expression on its top-level ``&&`` operators.

    The ``${{ }}`` wrapper, parentheses enclosing a whole conjunct and all whitespace are
    dropped, so equivalent spellings of the same check compare equal.

    Args:
        expression: The ``if`` expression, possibly spanning several lines.

    Returns:
        The normalised conjuncts, or ``None`` when a top-level ``||`` makes the expression a
        disjunction that no single conjunct can guard.

    """
    expression = expression.strip()
    if expression.startswith("${{") and expression.endswith("}}"):
        expression = expression[3:-2]
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    in_string = False
    index = 0
    while index < len(expression):
        char = expression[index]
        if in_string:
            in_string = char != "'"
        elif char == "'":
            in_string = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif depth == 0 and expression.startswith("||", index):
            return None
        elif depth == 0 and expression.startswith("&&", index):
            parts.append("".join(current).strip())
            current = []
            index += 2
            continue
        current.append(char)
        index += 1
    parts.append("".join(current).strip())

    conjuncts: list[str] = []
    for part in parts:
        nested = _top_level_conjuncts(expression=part[1:-1]) if _closes_at_end(text=part) else None
        if nested is None:
            # Either a plain conjunct or a parenthesised disjunction, which stays one opaque atom.
            conjuncts.append("".join(part.split()))
        else:
            conjuncts.extend(nested)
    return conjuncts


def find_gate_violations(
    jobs: dict[str, JobWiring], gate: str = GATE_JOB, reporters: frozenset[str] = REPORTER_JOBS
) -> list[str]:
    """Check that every huge-runner job waits for the gate and that the gate waits for every other job.

    Args:
        jobs: The workflow jobs, as returned by ``load_job_wiring``.
        gate: Id of the fan-in job the huge-runner jobs depend on.
        reporters: Jobs that run after the huge-runner jobs and therefore cannot feed the gate.

    Returns:
        One message per violation, empty when the wiring is correct.

    """
    gate_job = jobs.get(gate)
    if gate_job is None:
        return [f"job '{gate}' is missing from the workflow"]

    violations: list[str] = []
    if gate_job.on_huge_runners:
        violations.append(
            f"'{gate}' must not run on {HUGE_RUNNER_GROUP}: it only fans in results, so keep it on a GitHub-hosted runner"
        )
    gate_conjuncts = _top_level_conjuncts(expression=gate_job.condition)
    if gate_conjuncts is None or not {"always()", "!cancelled()"} <= set(gate_conjuncts):
        violations.append(
            f"'{gate}' must have always() and !cancelled() as top-level conjuncts of its condition: a path-filtered "
            "job is skipped, and without always() a skipped need would skip the gate and every huge-runner job behind "
            "it, while !cancelled() keeps it from running on a cancelled workflow"
        )
    violations.extend(f"'{gate}' depends on the unknown job '{name}'" for name in sorted(gate_job.needs - jobs.keys()))

    for job in jobs.values():
        if job.name == gate:
            continue
        if job.on_huge_runners:
            if gate not in job.needs:
                violations.append(f"'{job.name}' runs on {HUGE_RUNNER_GROUP} but does not list '{gate}' in its needs")
            conjuncts = _top_level_conjuncts(expression=job.condition)
            if conjuncts is None:
                violations.append(
                    f"'{job.name}' joins its condition with a top-level ||, so one branch can run it after '{gate}' "
                    "failed; keep the whole condition a conjunction and put alternatives inside parentheses"
                )
            else:
                if f"needs.{gate}.result=='success'" not in conjuncts:
                    violations.append(
                        f"'{job.name}' must have needs.{gate}.result == 'success' as a top-level conjunct of its "
                        "condition: it is the only thing that stops a status function such as always() or failure() "
                        f"from running it after '{gate}' failed"
                    )
                if "!cancelled()" not in conjuncts:
                    violations.append(
                        f"'{job.name}' must have !cancelled() as a top-level conjunct of its condition: without a status "
                        f"function the implicit success() skips it whenever a path-filtered job upstream of '{gate}' was "
                        "skipped, even though the gate passed"
                    )
            if job.name in gate_job.needs:
                violations.append(f"'{gate}' must not depend on the {HUGE_RUNNER_GROUP} job '{job.name}'")
        elif job.name in reporters:
            if job.name in gate_job.needs:
                violations.append(
                    f"'{gate}' must not depend on '{job.name}': it reports on the huge-runner jobs and runs after them"
                )
        elif job.name not in gate_job.needs:
            violations.append(
                f"'{job.name}' is missing from the needs of '{gate}'; add it there so the huge-runner jobs wait "
                "for it, or add it to REPORTER_JOBS in tasks/ci.py if it aggregates huge-runner results"
            )
    return violations


@task(name="validate-huge-runner-gate")
def validate_huge_runner_gate(context: Context) -> None:  # noqa: ARG001
    """Verify that ci.yml routes every huge-runner job through the gate job and the gate through every cheap job.

    Raises:
        Exit: If the wiring has violations; each one is listed in the message.

    """
    violations = find_gate_violations(jobs=load_job_wiring(workflow_path=CI_WORKFLOW, repo_root=REPO_BASE))
    if violations:
        details = "\n".join(f"  - {violation}" for violation in violations)
        raise Exit(f"{CI_WORKFLOW}: huge-runner gate wiring is broken:\n{details}", code=1)
    print(f"{CI_WORKFLOW}: huge-runner gate wiring is valid")
