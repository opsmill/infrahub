"""Idempotently embed proof-run evidence into a bug-pipeline PR description.

Usage: e2e_proof_embed.py --repo <owner/repo> --pr <n> --phase {red,green}
                          --verdict <v> --reason <text> --run-url <url>
                          [--image-url <url>]

Owns the three ``E2E_PROOF:RED|GREEN|NOTE`` marker pairs in the PR body: each
section is replaced in place when present and appended once when absent, and
nothing outside the markers is modified. An unpaired BEGIN/END marker is
stripped and the section appended fresh, so a replace can never span user
content next to an orphaned marker. After PATCHing, the body is re-fetched to
verify the pipeline phase markers survived a concurrent edit; the whole
fetch-transform-PATCH cycle is redone once, then raises. The body is fetched
and patched via the ``gh`` CLI; the transform itself is a pure string function.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Sequence

CONFIRMED_VERDICTS = frozenset({"red_confirmed", "green_confirmed"})

REASON_LIMIT = 200

_MARKDOWN_ESCAPES = str.maketrans({char: f"\\{char}" for char in "`[]<>"})

_IMAGE_LABEL = {"red": "before", "green": "after"}

_NOTE_BY_PHASE = {
    "red": (
        "> [!NOTE]\n"
        "> This PR is in the reproduction (RED) phase: the new e2e test fails by design until "
        "the fix is applied, so the repository's regular `E2E-testing-*` jobs are expected to fail. "
        "The authoritative check for this phase is `bug-agent-e2e-proof`."
    ),
    "green": (
        "> [!NOTE]\n"
        "> This PR is in the fix (GREEN) phase: the fix is applied, and all jobs, including the "
        "regular `E2E-testing-*` ones, are expected to pass."
    ),
}


class ProofResult(NamedTuple):
    """One proof run's outcome, as embedded into the PR body."""

    phase: str
    verdict: str
    reason: str
    run_url: str
    image_url: str | None = None


def sanitize_reason(reason: str) -> str:
    """Collapse to one line, truncate to the display limit, and neutralize markdown."""
    collapsed = " ".join(reason.split())
    return collapsed[:REASON_LIMIT].translate(_MARKDOWN_ESCAPES)


def render_phase_section(result: ProofResult) -> str:
    icon = "✅" if result.verdict in CONFIRMED_VERDICTS else "⚠️"
    lines = [f"{icon} `{result.verdict}` -- {sanitize_reason(result.reason)} ([run]({result.run_url}))"]
    if result.image_url:
        lines += ["", f"![{_IMAGE_LABEL[result.phase]}]({result.image_url})"]
    return "\n".join(lines)


def _upsert_section(body: str, name: str, content: str) -> str:
    begin = f"<!-- E2E_PROOF:{name}:BEGIN -->"
    end = f"<!-- E2E_PROOF:{name}:END -->"
    block = f"{begin}\n{content}\n{end}"
    if body.count(begin) != body.count(end):
        # An orphaned marker would let the paired replace swallow user content,
        # so strip the markers and fall through to a fresh append.
        body = body.replace(begin, "").replace(end, "")
    else:
        pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.DOTALL)
        if pattern.search(body):
            return pattern.sub(lambda _match: block, body, count=1)
    if not body.strip():
        return block + "\n"
    return body.rstrip() + "\n\n" + block + "\n"


def apply_proof_sections(body: str, result: ProofResult) -> str:
    """Return the PR body with this phase's proof section and the NOTE section upserted."""
    updated = _upsert_section(body, result.phase.upper(), render_phase_section(result))
    return _upsert_section(updated, "NOTE", _NOTE_BY_PHASE[result.phase])


def _fetch_body(repo: str, pr: int) -> str:
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/pulls/{pr}"],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return json.loads(result.stdout).get("body") or ""


def _patch_body(repo: str, pr: int, body: str) -> None:
    subprocess.run(
        ["gh", "api", "--method", "PATCH", f"repos/{repo}/pulls/{pr}", "-f", f"body={body}"],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point; returns the process exit code.

    Raises:
        RuntimeError: When the pipeline phase markers are still missing after the retried PATCH.

    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--phase", choices=("red", "green"), required=True)
    parser.add_argument(
        "--verdict",
        choices=("red_confirmed", "green_confirmed", "does_not_reproduce", "inconclusive"),
        required=True,
    )
    parser.add_argument("--reason", required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--image-url", default=None)
    args = parser.parse_args(argv)

    result = ProofResult(
        phase=args.phase,
        verdict=args.verdict,
        reason=args.reason,
        run_url=args.run_url,
        image_url=args.image_url,
    )
    # A concurrent editor PATCHing from a stale body can overwrite this update
    # and drop the pipeline phase markers, so verify after PATCHing and redo
    # the whole cycle once before giving up.
    missing: list[str] = []
    for _attempt in range(2):
        body = _fetch_body(args.repo, args.pr)
        new_body = apply_proof_sections(body, result)
        if new_body == body:
            print(f"PR body already up to date for phase {args.phase}")
            return 0
        _patch_body(args.repo, args.pr, new_body)
        required = ["AGENT_TEST_COMPLETE"]
        if "AGENT_FIX_COMPLETE" in body:
            required.append("AGENT_FIX_COMPLETE")
        persisted = _fetch_body(args.repo, args.pr)
        missing = [marker for marker in required if marker not in persisted]
        if not missing:
            print(f"PR body updated for phase {args.phase}")
            return 0
    raise RuntimeError(f"pipeline phase markers lost after PATCH despite a retry: {', '.join(missing)}")


if __name__ == "__main__":
    sys.exit(main())
