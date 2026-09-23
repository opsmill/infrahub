"""Turn the report's opportunities into deduplicated Jira tech-debt items."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from dependabot_autopilot.ports import JiraError, JiraIssueDraft
from dependabot_autopilot.report import (
    Opportunity,
    OpportunityCategory,
    PackageFinding,
    ReportError,
    Verdict,
    VerdictReport,
    load_report,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from dependabot_autopilot.ports import JiraPort

DEDUP_PREFIX = "dbap-"
ISSUE_LABELS = ("tech-debt", "dependabot-autopilot")
MAX_SUMMARY_CHARS = 255
MAX_DESCRIPTION_TEXT_CHARS = 4_000
MAX_PACKAGE_TEXT_CHARS = 200
MAX_CODE_REFS = 50
MAX_CODE_REF_CHARS = 300
_ELLIPSIS = "…"

type AdfNode = dict[str, object]


class Priority(StrEnum):
    """Jira's default priority names."""

    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


@dataclass(frozen=True)
class JiraTarget:
    project_key: str
    issue_type: str


@dataclass(frozen=True)
class FilingOutcome:
    created: tuple[str, ...] = ()
    commented: tuple[str, ...] = ()
    failures: tuple[str, ...] = ()
    """One `<opportunity key>: <error>` line per opportunity Jira refused."""
    skipped_reason: str | None = None


def dedup_label(*, key: str) -> str:
    return DEDUP_PREFIX + hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def priority_for(*, opportunity: Opportunity) -> Priority:
    match opportunity.category:
        case OpportunityCategory.SECURITY | OpportunityCategory.DEPRECATION_DEADLINE:
            return Priority.HIGH
        case OpportunityCategory.PERFORMANCE | OpportunityCategory.SIMPLIFICATION if opportunity.code_refs:
            return Priority.MEDIUM
        case _:
            return Priority.LOW


def effective_verdict(*, report: VerdictReport) -> Verdict:
    verdicts = [report.verdict, *(package.verdict for package in report.packages)]
    return max(verdicts, key=lambda verdict: verdict.strictness)


def load_fresh_report(*, directory: Path, run_head_sha: str, pr_number: int) -> VerdictReport:
    """Load the report and check it belongs to the analysed commit and pull request.

    Raises:
        ReportError: When the report is invalid or was produced for another commit or pull request.

    """
    report = load_report(directory=directory)
    if report.head_sha != run_head_sha:
        raise ReportError(f"the report claims {report.head_sha[:12]} but the analysis run was for {run_head_sha[:12]}")
    if report.pr_number != pr_number:
        raise ReportError(f"the report claims pull request #{report.pr_number} but the run was for #{pr_number}")
    return report


def issue_payload(
    *, package: PackageFinding, opportunity: Opportunity, pr_url: str, target: JiraTarget
) -> JiraIssueDraft:
    """Build the Jira issue for an opportunity; agent-written text only ever lands in plain ADF text nodes."""
    summary = _truncate(text=_single_line(text=f"[{package.name}] {opportunity.title}"), limit=MAX_SUMMARY_CHARS)
    return JiraIssueDraft(
        project_key=target.project_key,
        issue_type=target.issue_type,
        summary=summary,
        labels=(*ISSUE_LABELS, dedup_label(key=opportunity.key)),
        priority=priority_for(opportunity=opportunity),
        description=_document(
            blocks=[
                _paragraph(_text(_truncate(text=opportunity.summary, limit=MAX_DESCRIPTION_TEXT_CHARS))),
                _paragraph(_text("Package: "), _text(_package_line(package=package))),
                _paragraph(_text("Surfaced by "), _link(url=pr_url)),
                _heading(text="Code references"),
                *_code_refs(code_refs=opportunity.code_refs),
            ]
        ),
    )


def file_opportunities(*, jira: JiraPort, report: VerdictReport, pr_url: str, target: JiraTarget) -> FilingOutcome:
    """Create or comment one Jira item per distinct opportunity; Jira failures are returned, never raised."""
    if effective_verdict(report=report) is Verdict.NEEDS_CODE_CHANGES:
        return FilingOutcome(
            skipped_reason="the effective verdict is needs-code-changes; the blocked pull request is the tracker"
        )
    created: list[str] = []
    commented: list[str] = []
    failures: list[str] = []
    seen: set[str] = set()
    for package, opportunity in _opportunities(report=report):
        label = dedup_label(key=opportunity.key)
        if label in seen:
            continue
        seen.add(label)
        try:
            matches = jira.search_open_by_label(label=label)
            if matches:
                jira.add_comment(issue_key=matches[0].key, body=_seen_again_comment(package=package, pr_url=pr_url))
                commented.append(matches[0].key)
            else:
                issue = jira.create_issue(
                    draft=issue_payload(package=package, opportunity=opportunity, pr_url=pr_url, target=target)
                )
                created.append(issue.key)
        except JiraError as exc:
            failures.append(f"{opportunity.key}: {exc}")
    return FilingOutcome(created=tuple(created), commented=tuple(commented), failures=tuple(failures))


def _opportunities(*, report: VerdictReport) -> Iterable[tuple[PackageFinding, Opportunity]]:
    for package in report.packages:
        for opportunity in package.opportunities:
            yield package, opportunity


def _seen_again_comment(*, package: PackageFinding, pr_url: str) -> AdfNode:
    return _document(
        blocks=[_paragraph(_text("Seen again on "), _link(url=pr_url), _text(f" ({_package_line(package=package)})."))]
    )


def _package_line(*, package: PackageFinding) -> str:
    line = f"{package.name} {package.from_version} → {package.to_version}"
    return _truncate(text=_single_line(text=line), limit=MAX_PACKAGE_TEXT_CHARS)


def _code_refs(*, code_refs: tuple[str, ...]) -> list[AdfNode]:
    if not code_refs:
        return [_paragraph(_text("No code references were cited."))]
    items = [
        {"type": "listItem", "content": [_paragraph(_text(_truncate(text=ref, limit=MAX_CODE_REF_CHARS), code=True))]}
        for ref in code_refs[:MAX_CODE_REFS]
    ]
    blocks: list[AdfNode] = [{"type": "bulletList", "content": items}]
    if len(code_refs) > MAX_CODE_REFS:
        blocks.append(_paragraph(_text(f"{len(code_refs) - MAX_CODE_REFS} more references omitted.")))
    return blocks


def _document(*, blocks: list[AdfNode]) -> AdfNode:
    return {"type": "doc", "version": 1, "content": blocks}


def _paragraph(*inline: AdfNode) -> AdfNode:
    return {"type": "paragraph", "content": list(inline)}


def _heading(*, text: str) -> AdfNode:
    return {"type": "heading", "attrs": {"level": 3}, "content": [_text(text)]}


def _text(text: str, *, code: bool = False) -> AdfNode:
    node: AdfNode = {"type": "text", "text": text}
    if code:
        node["marks"] = [{"type": "code"}]
    return node


def _link(*, url: str) -> AdfNode:
    return {"type": "text", "text": url, "marks": [{"type": "link", "attrs": {"href": url}}]}


def _single_line(*, text: str) -> str:
    return "".join(character if character.isprintable() else " " for character in text)


def _truncate(*, text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + _ELLIPSIS
