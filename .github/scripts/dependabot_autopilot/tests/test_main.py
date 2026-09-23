from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

from dependabot_autopilot.__main__ import (
    NOT_IMPLEMENTED,
    ConfigError,
    build_parser,
    file_opportunities_command,
    load_config,
    load_jira_settings,
    main,
    run,
)
from dependabot_autopilot.flow import Config
from dependabot_autopilot.opportunities import JiraTarget
from dependabot_autopilot.ports import PullRequest, PullRequestState
from dependabot_autopilot.report import REPORT_FILENAME
from dependabot_autopilot.tests.fakes import FakeGitHub, FakeJira, IssueCreated, LabelsSet

if TYPE_CHECKING:
    from pathlib import Path

ENVIRON = {"GITHUB_REPOSITORY": "opsmill/infrahub", "DEPENDABOT_AUTOPILOT_APP_LOGIN": "autopilot[bot]"}


HEAD_SHA = "d40beee736f648045309f538af278dc2e34cd3ca"
JIRA_TOKEN = "s3cret"  # noqa: S105
JIRA_ENVIRON = {
    "GITHUB_REPOSITORY": "opsmill/infrahub",
    "GITHUB_SERVER_URL": "https://github.com",
    "JIRA_BASE_URL": "https://opsmill.atlassian.net",
    "JIRA_USER_EMAIL": "bot@opsmill.com",
    "JIRA_API_TOKEN": JIRA_TOKEN,
    "DEPENDABOT_AUTOPILOT_JIRA_PROJECT": "IFC",
}


def test_file_opportunities_is_no_longer_a_stub() -> None:
    assert NOT_IMPLEMENTED == ("digest",)


@pytest.mark.parametrize("command", NOT_IMPLEMENTED)
def test_stub_subcommand_exits_zero(command: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(argv=[command], environ={}) == 0
    assert capsys.readouterr().out == f"{command}: not implemented\n"


def test_unknown_subcommand_is_rejected() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(argv=["unknown"], environ=ENVIRON)
    assert exc_info.value.code == 2


def test_missing_configuration_fails(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(argv=["invalidate", "--pr", "1"], environ={"GITHUB_REPOSITORY": "opsmill/infrahub"}) == 2
    assert "DEPENDABOT_AUTOPILOT_APP_LOGIN" in capsys.readouterr().err


def test_report_requires_its_run_sha(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(argv=["evaluate", "--pr", "1", "--report", "/tmp/verdict"], environ=ENVIRON) == 2  # noqa: S108
    assert "--report-sha" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("value", "expected"),
    [("on", True), (" on\n", True), ("off", False), ("ON", False), ("true", False), (None, False)],
)
def test_merge_switch_is_on_only_for_on(value: str | None, expected: bool) -> None:
    environ = ENVIRON if value is None else {**ENVIRON, "DEPENDABOT_AUTOPILOT_MERGE": value}

    assert load_config(environ=environ).merge_enabled is expected


def test_configuration_is_read_from_the_environment() -> None:
    environ = {**ENVIRON, "DEPENDABOT_AUTOPILOT_FALLBACK_REVIEWER": "devops"}

    assert load_config(environ=environ) == Config(
        repo="opsmill/infrahub", app_login="autopilot[bot]", merge_enabled=False, fallback_reviewer="devops"
    )


def test_missing_repository_is_a_configuration_error() -> None:
    with pytest.raises(ConfigError, match="GITHUB_REPOSITORY"):
        load_config(environ={"DEPENDABOT_AUTOPILOT_APP_LOGIN": "autopilot[bot]"})


def test_escalate_command_labels_the_pull_request() -> None:
    github = FakeGitHub(acting_login="autopilot[bot]")
    github.pull_requests[3] = PullRequest(
        number=3,
        html_url="https://github.com/opsmill/infrahub/pull/3",
        author_login="dependabot[bot]",
        base_ref="stable",
        head_sha="d40beee736f648045309f538af278dc2e34cd3ca",
        head_repo_full_name="opsmill/infrahub",
        state=PullRequestState.OPEN,
        merged=False,
        labels=(),
        head_committed_at=datetime(2026, 9, 23, tzinfo=UTC),
    )
    args = build_parser().parse_args(args=["escalate", "--pr", "3", "--run-url", "https://example.com/run"])

    exit_code = run(args=args, github=github, config=load_config(environ=ENVIRON), now=datetime.now(tz=UTC))

    assert exit_code == 0
    assert LabelsSet(pr_number=3, labels=("autopilot/review-required",)) in github.writes


def write_verdict(directory: Path, *, verdict: str = "safe-to-merge", pr_number: int = 10689) -> Path:
    impacts: list[dict[str, Any]] = (
        [{"summary": "Signature changed", "path": "backend/x.py", "line": 1}] if verdict == "needs-code-changes" else []
    )
    content = {
        "schema_version": 1,
        "pr_number": pr_number,
        "head_sha": HEAD_SHA,
        "verdict": verdict,
        "report_markdown": "## Report",
        "packages": [
            {
                "name": "fastapi",
                "ecosystem": "uv",
                "from_version": "0.130.0",
                "to_version": "0.131.0",
                "verdict": verdict,
                "impacts": impacts,
                "opportunities": [
                    {
                        "key": "fastapi:lifespan-state",
                        "title": "Use lifespan state",
                        "category": "simplification",
                        "summary": "Replace app.state globals",
                        "code_refs": ["backend/infrahub/server.py:40"],
                    }
                ],
            }
        ],
    }
    (directory / REPORT_FILENAME).write_text(json.dumps(content), encoding="utf-8")
    return directory


def file_args(directory: Path, *, sha: str = HEAD_SHA, pr: int = 10689) -> list[str]:
    return ["file-opportunities", "--pr", str(pr), "--report", str(directory), "--report-sha", sha]


def test_jira_settings_are_read_from_the_environment() -> None:
    settings = load_jira_settings(environ=JIRA_ENVIRON)

    assert settings.base_url == "https://opsmill.atlassian.net"
    assert settings.email == "bot@opsmill.com"
    assert settings.token == JIRA_TOKEN
    assert settings.target == JiraTarget(project_key="IFC", issue_type="Task")
    assert settings.pr_url(number=5) == "https://github.com/opsmill/infrahub/pull/5"


def test_jira_issue_type_can_be_overridden() -> None:
    settings = load_jira_settings(environ={**JIRA_ENVIRON, "DEPENDABOT_AUTOPILOT_JIRA_ISSUE_TYPE": "Tech Debt"})

    assert settings.target.issue_type == "Tech Debt"


@pytest.mark.parametrize(
    "name",
    ["JIRA_BASE_URL", "JIRA_USER_EMAIL", "JIRA_API_TOKEN", "DEPENDABOT_AUTOPILOT_JIRA_PROJECT", "GITHUB_REPOSITORY"],
)
def test_missing_jira_setting_is_a_configuration_error(name: str) -> None:
    with pytest.raises(ConfigError, match=name):
        load_jira_settings(environ={**JIRA_ENVIRON, name: ""})


def test_file_opportunities_creates_the_item(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    jira = FakeJira()
    args = build_parser().parse_args(args=file_args(write_verdict(tmp_path)))

    assert file_opportunities_command(args=args, environ=JIRA_ENVIRON, jira=jira) == 0

    (write,) = jira.writes
    assert isinstance(write, IssueCreated)
    assert write.draft.project_key == "IFC"
    assert "https://github.com/opsmill/infrahub/pull/10689" in json.dumps(write.draft.description)
    assert "created IFC-1" in capsys.readouterr().out


def test_file_opportunities_without_jira_configuration_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(argv=file_args(write_verdict(tmp_path)), environ={"GITHUB_REPOSITORY": "opsmill/infrahub"})

    assert exit_code == 0
    assert "JIRA_BASE_URL" in capsys.readouterr().out


def test_file_opportunities_with_an_invalid_base_url_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    environ = {**JIRA_ENVIRON, "JIRA_BASE_URL": "http://opsmill.atlassian.net"}

    assert main(argv=file_args(write_verdict(tmp_path)), environ=environ) == 0
    assert "https" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("sha", "pr"),
    [("0" * 40, 10689), (HEAD_SHA, 1)],
)
def test_file_opportunities_skips_a_report_for_another_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], sha: str, pr: int
) -> None:
    jira = FakeJira()
    args = build_parser().parse_args(args=file_args(write_verdict(tmp_path), sha=sha, pr=pr))

    assert file_opportunities_command(args=args, environ=JIRA_ENVIRON, jira=jira) == 0
    assert jira.writes == []
    assert "skipped" in capsys.readouterr().out


def test_file_opportunities_skips_a_missing_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    jira = FakeJira()
    args = build_parser().parse_args(args=file_args(tmp_path))

    assert file_opportunities_command(args=args, environ=JIRA_ENVIRON, jira=jira) == 0
    assert jira.writes == []
    assert "skipped" in capsys.readouterr().out


def test_file_opportunities_skips_needs_code_changes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    jira = FakeJira()
    args = build_parser().parse_args(args=file_args(write_verdict(tmp_path, verdict="needs-code-changes")))

    assert file_opportunities_command(args=args, environ=JIRA_ENVIRON, jira=jira) == 0
    assert jira.writes == []
    assert "needs-code-changes" in capsys.readouterr().out


def test_file_opportunities_reports_jira_failures_as_warnings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = build_parser().parse_args(args=file_args(write_verdict(tmp_path)))

    assert file_opportunities_command(args=args, environ=JIRA_ENVIRON, jira=FakeJira(fail=True)) == 0
    assert "::warning::fastapi:lifespan-state: Jira unavailable" in capsys.readouterr().out
