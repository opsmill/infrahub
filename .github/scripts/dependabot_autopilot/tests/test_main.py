from __future__ import annotations

from datetime import UTC, datetime

import pytest

from dependabot_autopilot.__main__ import NOT_IMPLEMENTED, ConfigError, build_parser, load_config, main, run
from dependabot_autopilot.flow import Config
from dependabot_autopilot.ports import PullRequest, PullRequestState
from dependabot_autopilot.tests.fakes import FakeGitHub, LabelsSet

ENVIRON = {"GITHUB_REPOSITORY": "opsmill/infrahub", "DEPENDABOT_AUTOPILOT_APP_LOGIN": "autopilot[bot]"}


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
