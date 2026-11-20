from __future__ import annotations

import copy
import json
from typing import TYPE_CHECKING, Any

import pytest

from dependabot_autopilot.report import (
    MAX_REPORT_BYTES,
    REPORT_FILENAME,
    Ecosystem,
    Impact,
    Opportunity,
    OpportunityCategory,
    PackageFinding,
    ReportError,
    Verdict,
    VerdictReport,
    load_report,
    sanitize_report_markdown,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

HEAD_SHA = "d40beee736f648045309f538af278dc2e34cd3ca"


def valid_report() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "pr_number": 10689,
        "head_sha": HEAD_SHA,
        "verdict": "needs-code-changes",
        "report_markdown": "## Report\n\nAll good.",
        "packages": [
            {
                "name": "fastapi",
                "ecosystem": "uv",
                "from_version": "0.130.0",
                "to_version": "0.131.0",
                "verdict": "needs-code-changes",
                "impacts": [{"summary": "Signature changed", "path": "backend/infrahub/server.py", "line": 12}],
                "opportunities": [
                    {
                        "key": "fastapi:lifespan-state",
                        "title": "Use lifespan state",
                        "category": "simplification",
                        "summary": "Replace app.state globals",
                        "code_refs": ["backend/infrahub/server.py:40"],
                    }
                ],
            },
            {
                "name": "actions/checkout",
                "ecosystem": "github-actions",
                "from_version": "v5",
                "to_version": "v6",
                "verdict": "safe-to-merge",
                "impacts": [],
                "opportunities": [],
            },
        ],
    }


def write_report(directory: Path, content: dict[str, Any]) -> Path:
    (directory / REPORT_FILENAME).write_text(json.dumps(content), encoding="utf-8")
    return directory


def test_valid_report_parses(tmp_path: Path) -> None:
    report = load_report(directory=write_report(directory=tmp_path, content=valid_report()))

    assert report == VerdictReport(
        pr_number=10689,
        head_sha=HEAD_SHA,
        verdict=Verdict.NEEDS_CODE_CHANGES,
        report_markdown="## Report\n\nAll good.",
        packages=(
            PackageFinding(
                name="fastapi",
                ecosystem=Ecosystem.UV,
                from_version="0.130.0",
                to_version="0.131.0",
                verdict=Verdict.NEEDS_CODE_CHANGES,
                impacts=(Impact(summary="Signature changed", path="backend/infrahub/server.py", line=12),),
                opportunities=(
                    Opportunity(
                        key="fastapi:lifespan-state",
                        title="Use lifespan state",
                        category=OpportunityCategory.SIMPLIFICATION,
                        summary="Replace app.state globals",
                        code_refs=("backend/infrahub/server.py:40",),
                    ),
                ),
            ),
            PackageFinding(
                name="actions/checkout",
                ecosystem=Ecosystem.GITHUB_ACTIONS,
                from_version="v5",
                to_version="v6",
                verdict=Verdict.SAFE_TO_MERGE,
                impacts=(),
                opportunities=(),
            ),
        ),
    )


type Mutation = Callable[[dict[str, Any]], object]


def _top(field: str, value: object) -> Mutation:
    return lambda report: report.update({field: value})


def _drop_top(field: str) -> Mutation:
    return lambda report: report.pop(field)


def _package(field: str, value: object) -> Mutation:
    return lambda report: report["packages"][0].update({field: value})


def _drop_package(field: str) -> Mutation:
    return lambda report: report["packages"][0].pop(field)


def _impact(field: str, value: object) -> Mutation:
    return lambda report: report["packages"][0]["impacts"][0].update({field: value})


def _opportunity(field: str, value: object) -> Mutation:
    return lambda report: report["packages"][0]["opportunities"][0].update({field: value})


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(_top(field="schema_version", value=2), id="schema-version-2"),
        pytest.param(_top(field="schema_version", value=True), id="schema-version-bool"),
        pytest.param(_drop_top(field="schema_version"), id="schema-version-missing"),
        pytest.param(_top(field="pr_number", value=0), id="pr-number-zero"),
        pytest.param(_top(field="pr_number", value="10689"), id="pr-number-string"),
        pytest.param(_top(field="head_sha", value=HEAD_SHA.upper()), id="head-sha-uppercase"),
        pytest.param(_top(field="head_sha", value=HEAD_SHA[:39]), id="head-sha-short"),
        pytest.param(_top(field="verdict", value="looks-fine"), id="unknown-verdict"),
        pytest.param(_top(field="packages", value=[]), id="empty-packages"),
        pytest.param(_top(field="packages", value={}), id="packages-not-a-list"),
        pytest.param(_top(field="report_markdown", value=""), id="empty-report-markdown"),
        pytest.param(_top(field="report_markdown", value="x" * 60_001), id="report-markdown-too-long"),
        pytest.param(_top(field="extra", value=1), id="unknown-top-level-field"),
        pytest.param(_package(field="impacts", value=[]), id="needs-code-changes-without-impacts"),
        pytest.param(_package(field="ecosystem", value="pip"), id="unknown-ecosystem"),
        pytest.param(_package(field="verdict", value="maybe"), id="unknown-package-verdict"),
        pytest.param(_package(field="name", value=""), id="empty-package-name"),
        pytest.param(_package(field="extra", value=1), id="unknown-package-field"),
        pytest.param(_drop_package(field="opportunities"), id="package-opportunities-missing"),
        pytest.param(_impact(field="line", value=0), id="impact-line-zero"),
        pytest.param(_impact(field="path", value=""), id="impact-empty-path"),
        pytest.param(_opportunity(field="key", value="FastAPI:x"), id="key-uppercase"),
        pytest.param(_opportunity(field="key", value="fastapi"), id="key-without-colon"),
        pytest.param(_opportunity(field="title", value="t" * 121), id="title-too-long"),
        pytest.param(_opportunity(field="category", value="style"), id="unknown-category"),
        pytest.param(_opportunity(field="code_refs", value=["server.py"]), id="bad-code-ref"),
    ],
)
def test_schema_violation_is_rejected(tmp_path: Path, mutate: Mutation) -> None:
    content = copy.deepcopy(valid_report())
    mutate(content)

    with pytest.raises(ReportError):
        load_report(directory=write_report(directory=tmp_path, content=content))


def test_report_at_the_limits_is_accepted(tmp_path: Path) -> None:
    content = valid_report()
    content["report_markdown"] = "x" * 60_000
    content["packages"][0]["opportunities"][0]["title"] = "t" * 120

    report = load_report(directory=write_report(directory=tmp_path, content=content))

    assert len(report.report_markdown) == 60_000


def test_file_over_size_limit_is_rejected(tmp_path: Path) -> None:
    content = valid_report()
    content["padding"] = " " * MAX_REPORT_BYTES
    write_report(directory=tmp_path, content=content)

    with pytest.raises(ReportError, match="256"):
        load_report(directory=tmp_path)


def test_missing_file_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "other.json").write_text(json.dumps(valid_report()), encoding="utf-8")

    with pytest.raises(ReportError):
        load_report(directory=tmp_path)


def test_invalid_json_is_rejected(tmp_path: Path) -> None:
    (tmp_path / REPORT_FILENAME).write_text("{not json", encoding="utf-8")

    with pytest.raises(ReportError):
        load_report(directory=tmp_path)


def test_symlinked_report_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "elsewhere.json"
    target.write_text(json.dumps(valid_report()), encoding="utf-8")
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    (artifact / REPORT_FILENAME).symlink_to(target)

    with pytest.raises(ReportError):
        load_report(directory=artifact)


@pytest.mark.parametrize(
    ("text", "mention"),
    [
        pytest.param("ping @octocat please", "@octocat", id="user"),
        pytest.param("cc @opsmill/backend", "@opsmill/backend", id="team"),
        pytest.param("@start of line", "@start", id="line-start"),
    ],
)
def test_sanitize_neutralizes_mentions(text: str, mention: str) -> None:
    sanitized = sanitize_report_markdown(text=text)

    assert mention not in sanitized
    assert mention.replace("@", "@\u200b", 1) in sanitized


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("before <!-- dependabot-autopilot --> after", id="forged-marker"),
        pytest.param("a <!--\nmulti\nline\n--> b", id="multi-line"),
        pytest.param("a <!<!-- x -->-- dependabot-autopilot --> b", id="nested-reassembly"),
        pytest.param("a <!-- never closed", id="unterminated"),
    ],
)
def test_sanitize_strips_html_comments(text: str) -> None:
    sanitized = sanitize_report_markdown(text=text)

    assert "<!--" not in sanitized
    assert "dependabot-autopilot -->" not in sanitized


def test_sanitize_wraps_in_labelled_details_block() -> None:
    sanitized = sanitize_report_markdown(text="## Findings\n\nNothing.")

    assert sanitized.startswith("<details>\n<summary>")
    assert "agent output" in sanitized.split("\n")[1].lower()
    assert "## Findings\n\nNothing." in sanitized
    assert sanitized.endswith("</details>")
