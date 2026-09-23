from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import TYPE_CHECKING, Any

import pytest

from dependabot_autopilot.opportunities import (
    MAX_SUMMARY_CHARS,
    JiraTarget,
    Priority,
    dedup_label,
    effective_verdict,
    file_opportunities,
    issue_payload,
    load_fresh_report,
    priority_for,
)
from dependabot_autopilot.ports import JiraIssue
from dependabot_autopilot.report import (
    REPORT_FILENAME,
    Ecosystem,
    Impact,
    Opportunity,
    OpportunityCategory,
    PackageFinding,
    ReportError,
    Verdict,
    VerdictReport,
)
from dependabot_autopilot.tests.fakes import FakeJira, IssueCommented, IssueCreated

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

HEAD_SHA = "d40beee736f648045309f538af278dc2e34cd3ca"
PR_URL = "https://github.com/opsmill/infrahub/pull/10689"
TARGET = JiraTarget(project_key="IFC", issue_type="Task")

LIFESPAN = Opportunity(
    key="fastapi:lifespan-state",
    title="Use lifespan state",
    category=OpportunityCategory.SIMPLIFICATION,
    summary="Replace app.state globals with lifespan state.",
    code_refs=("backend/infrahub/server.py:40", "backend/infrahub/api/__init__.py:12"),
)
DEPRECATION = Opportunity(
    key="fastapi:on-event",
    title="Drop on_event handlers",
    category=OpportunityCategory.DEPRECATION_DEADLINE,
    summary="on_event is removed in 1.0.",
    code_refs=(),
)


def package(
    *, opportunities: tuple[Opportunity, ...], verdict: Verdict = Verdict.SAFE_TO_MERGE, name: str = "fastapi"
) -> PackageFinding:
    impacts = (Impact(summary="Signature changed", path="backend/x.py", line=1),) if verdict.strictness == 2 else ()
    return PackageFinding(
        name=name,
        ecosystem=Ecosystem.UV,
        from_version="0.130.0",
        to_version="0.131.0",
        verdict=verdict,
        impacts=impacts,
        opportunities=opportunities,
    )


def report(*, packages: tuple[PackageFinding, ...], verdict: Verdict = Verdict.SAFE_TO_MERGE) -> VerdictReport:
    return VerdictReport(
        pr_number=10689, head_sha=HEAD_SHA, verdict=verdict, packages=packages, report_markdown="## Report"
    )


def adf_nodes(document: Mapping[str, object]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = [json.loads(json.dumps(document))]
    while pending:
        node = pending.pop(0)
        nodes.append(node)
        pending.extend(node.get("content", []))
    return nodes


def adf_text(document: Mapping[str, object]) -> str:
    return "".join(node["text"] for node in adf_nodes(document) if node["type"] == "text")


def adf_links(document: Mapping[str, object]) -> list[str]:
    return [
        mark["attrs"]["href"]
        for node in adf_nodes(document)
        for mark in node.get("marks", [])
        if mark["type"] == "link"
    ]


def test_dedup_label_is_the_first_twelve_hex_of_the_key_hash() -> None:
    expected = "dbap-" + hashlib.sha256(b"fastapi:lifespan-state").hexdigest()[:12]

    assert dedup_label(key="fastapi:lifespan-state") == expected


def test_dedup_label_differs_per_key() -> None:
    assert dedup_label(key="fastapi:lifespan-state") != dedup_label(key="fastapi:on-event")


@pytest.mark.parametrize(
    ("category", "code_refs", "expected"),
    [
        (OpportunityCategory.SECURITY, (), Priority.HIGH),
        (OpportunityCategory.SECURITY, ("a.py:1",), Priority.HIGH),
        (OpportunityCategory.DEPRECATION_DEADLINE, (), Priority.HIGH),
        (OpportunityCategory.PERFORMANCE, ("a.py:1",), Priority.MEDIUM),
        (OpportunityCategory.SIMPLIFICATION, ("a.py:1", "b.py:2"), Priority.MEDIUM),
        (OpportunityCategory.PERFORMANCE, (), Priority.LOW),
        (OpportunityCategory.SIMPLIFICATION, (), Priority.LOW),
        (OpportunityCategory.OTHER, ("a.py:1",), Priority.LOW),
        (OpportunityCategory.OTHER, (), Priority.LOW),
    ],
)
def test_priority_rubric(category: OpportunityCategory, code_refs: tuple[str, ...], expected: Priority) -> None:
    assert priority_for(opportunity=replace(LIFESPAN, category=category, code_refs=code_refs)) is expected


def test_priority_names_match_jira_defaults() -> None:
    assert [priority.value for priority in Priority] == ["High", "Medium", "Low"]


def test_issue_payload_fields() -> None:
    draft = issue_payload(
        package=package(opportunities=(LIFESPAN,)), opportunity=LIFESPAN, pr_url=PR_URL, target=TARGET
    )

    assert draft.project_key == "IFC"
    assert draft.issue_type == "Task"
    assert draft.summary == "[fastapi] Use lifespan state"
    assert draft.labels == ("tech-debt", "dependabot-autopilot", dedup_label(key="fastapi:lifespan-state"))
    assert draft.priority == "Medium"


def test_issue_payload_carries_no_assignee() -> None:
    draft = issue_payload(
        package=package(opportunities=(LIFESPAN,)), opportunity=LIFESPAN, pr_url=PR_URL, target=TARGET
    )

    assert "assignee" not in json.dumps(draft.description)
    assert not hasattr(draft, "assignee")


def test_issue_description_is_adf_with_pr_link_and_code_refs() -> None:
    draft = issue_payload(
        package=package(opportunities=(LIFESPAN,)), opportunity=LIFESPAN, pr_url=PR_URL, target=TARGET
    )
    description = draft.description

    assert description["type"] == "doc"
    assert description["version"] == 1
    text = adf_text(description)
    assert LIFESPAN.summary in text
    assert "backend/infrahub/server.py:40" in text
    assert "backend/infrahub/api/__init__.py:12" in text
    assert "0.130.0" in text
    assert "0.131.0" in text
    assert adf_links(description) == [PR_URL]


def test_agent_text_stays_plain_text_in_the_description() -> None:
    hostile = replace(
        LIFESPAN,
        summary="[click](https://evil.example) {color:red}x{color} <script>",
        code_refs=("[x](https://evil.example):1",),
    )

    draft = issue_payload(package=package(opportunities=(hostile,)), opportunity=hostile, pr_url=PR_URL, target=TARGET)

    assert adf_links(draft.description) == [PR_URL]
    assert hostile.summary in adf_text(draft.description)
    assert all(
        node["type"] in {"doc", "paragraph", "text", "heading", "bulletList", "listItem"}
        for node in adf_nodes(draft.description)
    )


def test_summary_is_capped_and_single_line() -> None:
    long_package = package(opportunities=(LIFESPAN,), name="p" * 400)
    multiline = replace(LIFESPAN, title="Line one\nLine two\r\tend")

    draft = issue_payload(package=long_package, opportunity=multiline, pr_url=PR_URL, target=TARGET)
    short = issue_payload(
        package=package(opportunities=(multiline,)), opportunity=multiline, pr_url=PR_URL, target=TARGET
    )

    assert len(draft.summary) <= MAX_SUMMARY_CHARS == 255
    assert short.summary == "[fastapi] Line one Line two  end"


def test_long_agent_summary_is_truncated() -> None:
    verbose = replace(LIFESPAN, summary="x" * 50_000, code_refs=tuple(f"a.py:{line}" for line in range(1, 500)))

    draft = issue_payload(package=package(opportunities=(verbose,)), opportunity=verbose, pr_url=PR_URL, target=TARGET)

    assert len(json.dumps(draft.description)) < 20_000


@pytest.mark.parametrize(
    ("overall", "package_verdict", "expected"),
    [
        (Verdict.SAFE_TO_MERGE, Verdict.SAFE_TO_MERGE, Verdict.SAFE_TO_MERGE),
        (Verdict.REVIEW_REQUIRED, Verdict.SAFE_TO_MERGE, Verdict.REVIEW_REQUIRED),
        (Verdict.SAFE_TO_MERGE, Verdict.NEEDS_CODE_CHANGES, Verdict.NEEDS_CODE_CHANGES),
        (Verdict.NEEDS_CODE_CHANGES, Verdict.SAFE_TO_MERGE, Verdict.NEEDS_CODE_CHANGES),
    ],
)
def test_effective_verdict_is_the_strictest(overall: Verdict, package_verdict: Verdict, expected: Verdict) -> None:
    subject = report(
        packages=(package(opportunities=(), verdict=package_verdict), package(opportunities=(), name="other")),
        verdict=overall,
    )

    assert effective_verdict(report=subject) is expected


def test_file_creates_an_issue_when_none_matches() -> None:
    jira = FakeJira()

    outcome = file_opportunities(
        jira=jira, report=report(packages=(package(opportunities=(LIFESPAN,)),)), pr_url=PR_URL, target=TARGET
    )

    assert outcome.created == ("IFC-1",)
    assert outcome.commented == ()
    assert outcome.failures == ()
    assert outcome.skipped_reason is None
    assert jira.writes == [
        IssueCreated(
            draft=issue_payload(
                package=package(opportunities=(LIFESPAN,)), opportunity=LIFESPAN, pr_url=PR_URL, target=TARGET
            )
        )
    ]


def test_file_comments_on_the_matching_open_issue() -> None:
    jira = FakeJira()
    existing = JiraIssue(key="IFC-7", summary="[fastapi] Use lifespan state", url="u", priority="Medium")
    jira.issues["IFC-7"] = (existing, ("tech-debt", dedup_label(key=LIFESPAN.key)))

    outcome = file_opportunities(
        jira=jira, report=report(packages=(package(opportunities=(LIFESPAN,)),)), pr_url=PR_URL, target=TARGET
    )

    assert outcome.created == ()
    assert outcome.commented == ("IFC-7",)
    assert len(jira.writes) == 1
    write = jira.writes[0]
    assert isinstance(write, IssueCommented)
    assert write.issue_key == "IFC-7"
    assert adf_links(write.body) == [PR_URL]


def test_file_does_not_comment_twice_for_the_same_pull_request() -> None:
    jira = FakeJira()
    existing = JiraIssue(key="IFC-7", summary="[fastapi] Use lifespan state", url="u", priority="Medium")
    jira.issues["IFC-7"] = (existing, ("tech-debt", dedup_label(key=LIFESPAN.key)))
    subject = report(packages=(package(opportunities=(LIFESPAN,)),))

    file_opportunities(jira=jira, report=subject, pr_url=PR_URL, target=TARGET)
    rerun = file_opportunities(jira=jira, report=subject, pr_url=PR_URL, target=TARGET)

    assert rerun.created == rerun.commented == rerun.failures == ()
    assert [type(write) for write in jira.writes] == [IssueCommented]


def test_file_skips_the_comment_when_an_existing_comment_links_the_pull_request() -> None:
    jira = FakeJira()
    existing = JiraIssue(key="IFC-7", summary="[fastapi] Use lifespan state", url="u", priority="Medium")
    jira.issues["IFC-7"] = (existing, (dedup_label(key=LIFESPAN.key),))
    jira.comments["IFC-7"] = ["Unrelated note", f"Tracked from {PR_URL}/files."]

    outcome = file_opportunities(
        jira=jira, report=report(packages=(package(opportunities=(LIFESPAN,)),)), pr_url=PR_URL, target=TARGET
    )

    assert outcome.commented == ()
    assert jira.writes == []


def test_file_comments_when_existing_comments_link_only_other_pull_requests() -> None:
    jira = FakeJira()
    existing = JiraIssue(key="IFC-7", summary="[fastapi] Use lifespan state", url="u", priority="Medium")
    jira.issues["IFC-7"] = (existing, (dedup_label(key=LIFESPAN.key),))
    jira.comments["IFC-7"] = [f"Seen again on {PR_URL}0 (fastapi 0.1 → 0.2)."]

    outcome = file_opportunities(
        jira=jira, report=report(packages=(package(opportunities=(LIFESPAN,)),)), pr_url=PR_URL, target=TARGET
    )

    assert outcome.commented == ("IFC-7",)


def test_file_reports_a_failure_when_the_comments_cannot_be_read() -> None:
    jira = FakeJira()
    existing = JiraIssue(key="IFC-7", summary="[fastapi] Use lifespan state", url="u", priority="Medium")
    jira.issues["IFC-7"] = (existing, (dedup_label(key=LIFESPAN.key),))
    jira.unreadable_comments.add("IFC-7")

    outcome = file_opportunities(
        jira=jira, report=report(packages=(package(opportunities=(LIFESPAN,)),)), pr_url=PR_URL, target=TARGET
    )

    assert outcome.commented == ()
    assert len(outcome.failures) == 1
    assert jira.writes == []


def test_file_handles_each_opportunity_independently() -> None:
    jira = FakeJira()
    jira.issues["IFC-7"] = (
        JiraIssue(key="IFC-7", summary="s", url="u", priority="High"),
        (dedup_label(key=DEPRECATION.key),),
    )

    outcome = file_opportunities(
        jira=jira,
        report=report(packages=(package(opportunities=(LIFESPAN, DEPRECATION)),)),
        pr_url=PR_URL,
        target=TARGET,
    )

    assert outcome.created == ("IFC-1",)
    assert outcome.commented == ("IFC-7",)


def test_file_handles_a_repeated_key_once_per_report() -> None:
    jira = FakeJira()
    subject = report(packages=(package(opportunities=(LIFESPAN,)), package(opportunities=(LIFESPAN,), name="dup")))

    outcome = file_opportunities(jira=jira, report=subject, pr_url=PR_URL, target=TARGET)

    assert outcome.created == ("IFC-1",)
    assert len(jira.writes) == 1


@pytest.mark.parametrize(
    ("overall", "package_verdict"),
    [
        (Verdict.NEEDS_CODE_CHANGES, Verdict.NEEDS_CODE_CHANGES),
        (Verdict.SAFE_TO_MERGE, Verdict.NEEDS_CODE_CHANGES),
        (Verdict.NEEDS_CODE_CHANGES, Verdict.SAFE_TO_MERGE),
    ],
)
def test_file_skips_every_opportunity_when_code_changes_are_needed(overall: Verdict, package_verdict: Verdict) -> None:
    jira = FakeJira()
    subject = report(
        packages=(
            package(opportunities=(LIFESPAN,), verdict=package_verdict),
            package(opportunities=(DEPRECATION,), name="other"),
        ),
        verdict=overall,
    )

    outcome = file_opportunities(jira=jira, report=subject, pr_url=PR_URL, target=TARGET)

    assert outcome.skipped_reason is not None
    assert outcome.created == outcome.commented == outcome.failures == ()
    assert jira.writes == []


def test_file_files_when_review_is_required() -> None:
    jira = FakeJira()

    outcome = file_opportunities(
        jira=jira,
        report=report(packages=(package(opportunities=(LIFESPAN,)),), verdict=Verdict.REVIEW_REQUIRED),
        pr_url=PR_URL,
        target=TARGET,
    )

    assert outcome.created == ("IFC-1",)


def test_file_reports_jira_errors_without_raising() -> None:
    jira = FakeJira(fail=True)

    outcome = file_opportunities(
        jira=jira,
        report=report(packages=(package(opportunities=(LIFESPAN, DEPRECATION)),)),
        pr_url=PR_URL,
        target=TARGET,
    )

    assert outcome.created == outcome.commented == ()
    assert len(outcome.failures) == 2
    assert all("Jira unavailable" in failure for failure in outcome.failures)
    assert LIFESPAN.key in outcome.failures[0]


def test_file_with_no_opportunities_writes_nothing() -> None:
    jira = FakeJira()

    outcome = file_opportunities(
        jira=jira, report=report(packages=(package(opportunities=()),)), pr_url=PR_URL, target=TARGET
    )

    assert outcome.created == outcome.commented == outcome.failures == ()
    assert outcome.skipped_reason is None
    assert jira.writes == []


def write_verdict(directory: Path, *, head_sha: str = HEAD_SHA) -> Path:
    content = {
        "schema_version": 1,
        "pr_number": 10689,
        "head_sha": head_sha,
        "verdict": "safe-to-merge",
        "report_markdown": "## Report",
        "packages": [
            {
                "name": "fastapi",
                "ecosystem": "uv",
                "from_version": "0.130.0",
                "to_version": "0.131.0",
                "verdict": "safe-to-merge",
                "impacts": [],
                "opportunities": [],
            }
        ],
    }
    (directory / REPORT_FILENAME).write_text(json.dumps(content), encoding="utf-8")
    return directory


def test_fresh_report_loads(tmp_path: Path) -> None:
    loaded = load_fresh_report(directory=write_verdict(tmp_path), run_head_sha=HEAD_SHA, pr_number=10689)

    assert loaded.head_sha == HEAD_SHA


def test_report_for_another_commit_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ReportError, match="claims"):
        load_fresh_report(directory=write_verdict(tmp_path), run_head_sha="0" * 40, pr_number=10689)


def test_report_for_another_pull_request_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ReportError, match="pull request"):
        load_fresh_report(directory=write_verdict(tmp_path), run_head_sha=HEAD_SHA, pr_number=1)


def test_missing_report_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ReportError, match="missing"):
        load_fresh_report(directory=tmp_path, run_head_sha=HEAD_SHA, pr_number=10689)
