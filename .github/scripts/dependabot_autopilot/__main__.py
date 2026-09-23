from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from dependabot_autopilot.adapters import GhCliGitHub, JiraRest, SlackWebhook
from dependabot_autopilot.digest import post_digest
from dependabot_autopilot.flow import Config, SuppliedReport, escalate, evaluate, invalidate, sweep
from dependabot_autopilot.opportunities import JiraTarget, file_opportunities, load_fresh_report
from dependabot_autopilot.ports import JiraError, SlackError
from dependabot_autopilot.report import ReportError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from dependabot_autopilot.ports import GitHubPort, JiraPort, SlackPort

SUBCOMMANDS = ("invalidate", "evaluate", "sweep", "escalate", "file-opportunities", "digest")
DEFAULT_JIRA_ISSUE_TYPE = "Task"
_REQUIRED_JIRA_ENV = (
    "JIRA_BASE_URL",
    "JIRA_USER_EMAIL",
    "JIRA_API_TOKEN",
    "DEPENDABOT_AUTOPILOT_JIRA_PROJECT",
    "GITHUB_REPOSITORY",
)
_REQUIRED_DIGEST_ENV = ("JIRA_BASE_URL", "JIRA_USER_EMAIL", "JIRA_API_TOKEN", "SLACK_RELEASE_RADAR_WEBHOOK_URL")


class ConfigError(Exception):
    """A required environment variable is missing."""


@dataclass(frozen=True)
class JiraSettings:
    base_url: str
    email: str
    token: str = field(repr=False)
    target: JiraTarget
    server_url: str
    repo: str

    def pr_url(self, *, number: int) -> str:
        return f"{self.server_url}/{self.repo}/pull/{number}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dependabot_autopilot")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("invalidate").add_argument("--pr", type=int, required=True)
    evaluate_parser = subparsers.add_parser("evaluate")
    evaluate_parser.add_argument("--pr", type=int, required=True)
    evaluate_parser.add_argument("--report", type=Path, help="directory holding the downloaded verdict artifact")
    evaluate_parser.add_argument("--report-sha", help="head commit of the analysis run that produced --report")
    subparsers.add_parser("sweep").add_argument("--run-url", required=True)
    escalate_parser = subparsers.add_parser("escalate")
    escalate_parser.add_argument("--pr", type=int, required=True)
    escalate_parser.add_argument("--run-url", required=True)
    file_parser = subparsers.add_parser("file-opportunities")
    file_parser.add_argument("--pr", type=int, required=True)
    file_parser.add_argument("--report", type=Path, required=True, help="directory holding the verdict artifact")
    file_parser.add_argument("--report-sha", required=True, help="head commit of the analysis run that produced it")
    subparsers.add_parser("digest")
    return parser


def load_config(*, environ: Mapping[str, str]) -> Config:
    """Read the configuration from the environment.

    Raises:
        ConfigError: When `GITHUB_REPOSITORY` or `DEPENDABOT_AUTOPILOT_APP_LOGIN` is missing.

    """
    missing = [name for name in ("GITHUB_REPOSITORY", "DEPENDABOT_AUTOPILOT_APP_LOGIN") if not environ.get(name)]
    if missing:
        raise ConfigError(f"missing environment variables: {', '.join(missing)}")
    return Config(
        repo=environ["GITHUB_REPOSITORY"],
        app_login=environ["DEPENDABOT_AUTOPILOT_APP_LOGIN"],
        merge_enabled=environ.get("DEPENDABOT_AUTOPILOT_MERGE", "").strip() == "on",
        fallback_reviewer=environ.get("DEPENDABOT_AUTOPILOT_FALLBACK_REVIEWER", ""),
    )


def load_jira_settings(*, environ: Mapping[str, str]) -> JiraSettings:
    """Read the Jira filing configuration from the environment.

    Raises:
        ConfigError: When a Jira credential, the Jira project or `GITHUB_REPOSITORY` is missing.

    """
    missing = [name for name in _REQUIRED_JIRA_ENV if not environ.get(name, "").strip()]
    if missing:
        raise ConfigError(f"missing environment variables: {', '.join(missing)}")
    return JiraSettings(
        base_url=environ["JIRA_BASE_URL"].strip(),
        email=environ["JIRA_USER_EMAIL"].strip(),
        token=environ["JIRA_API_TOKEN"].strip(),
        target=JiraTarget(
            project_key=environ["DEPENDABOT_AUTOPILOT_JIRA_PROJECT"].strip(),
            issue_type=environ.get("DEPENDABOT_AUTOPILOT_JIRA_ISSUE_TYPE", "").strip() or DEFAULT_JIRA_ISSUE_TYPE,
        ),
        server_url=environ.get("GITHUB_SERVER_URL", "").strip().rstrip("/") or "https://github.com",
        repo=environ["GITHUB_REPOSITORY"].strip(),
    )


def file_opportunities_command(
    *, args: argparse.Namespace, environ: Mapping[str, str], jira: JiraPort | None = None
) -> int:
    """File the report's opportunities in Jira; every tracker or report problem is logged and exits 0."""
    try:
        settings = load_jira_settings(environ=environ)
        if jira is None:
            jira = JiraRest(base_url=settings.base_url, email=settings.email, token=settings.token)
    except (ConfigError, ValueError) as exc:
        _warn(message=f"file-opportunities skipped: Jira is not configured ({exc})")
        return 0
    try:
        report = load_fresh_report(directory=args.report, run_head_sha=args.report_sha, pr_number=args.pr)
    except ReportError as exc:
        _warn(message=f"file-opportunities skipped: {exc}")
        return 0
    outcome = file_opportunities(
        jira=jira, report=report, pr_url=settings.pr_url(number=args.pr), target=settings.target
    )
    if outcome.skipped_reason is not None:
        print(f"#{args.pr}: file-opportunities skipped: {outcome.skipped_reason}")
    for key in outcome.created:
        print(f"#{args.pr}: created {key}")
    for key in outcome.commented:
        print(f"#{args.pr}: commented on {key}")
    for failure in outcome.failures:
        _warn(message=failure)
    return 0


def digest_command(*, environ: Mapping[str, str], jira: JiraPort | None = None, slack: SlackPort | None = None) -> int:
    """Post the weekly digest; missing configuration is a warning, a Jira or Slack failure fails the run."""
    missing = [name for name in _REQUIRED_DIGEST_ENV if not environ.get(name, "").strip()]
    if missing:
        _warn(message=f"digest skipped: missing environment variables: {', '.join(missing)}")
        return 0
    try:
        if jira is None:
            jira = JiraRest(
                base_url=environ["JIRA_BASE_URL"].strip(),
                email=environ["JIRA_USER_EMAIL"].strip(),
                token=environ["JIRA_API_TOKEN"].strip(),
            )
        if slack is None:
            slack = SlackWebhook(url=environ["SLACK_RELEASE_RADAR_WEBHOOK_URL"].strip())
    except ValueError as exc:
        _warn(message=f"digest skipped: {exc}")
        return 0
    try:
        count = post_digest(jira=jira, slack=slack)
    except (JiraError, SlackError) as exc:
        single_line = " ".join(str(exc).splitlines())
        print(f"::error::{single_line}")
        return 1
    print(f"digest: posted {count} item{'' if count == 1 else 's'}" if count else "digest: nothing to post")
    return 0


def _warn(*, message: str) -> None:
    single_line = " ".join(message.splitlines())
    print(f"::warning::{single_line}")


def run(*, args: argparse.Namespace, github: GitHubPort, config: Config, now: datetime) -> int:
    match args.command:
        case "invalidate":
            invalidate(github=github, config=config, pr_number=args.pr)
        case "evaluate":
            supplied = None
            if args.report is not None and args.report_sha:
                supplied = SuppliedReport(directory=args.report, run_head_sha=args.report_sha)
            decision = evaluate(github=github, config=config, pr_number=args.pr, now=now, supplied=supplied)
            print(f"#{args.pr}: {'out of scope' if decision is None else decision.action}")
        case "sweep":
            return 0 if sweep(github=github, config=config, now=now, run_url=args.run_url) else 1
        case "escalate":
            escalate(github=github, config=config, pr_number=args.pr, run_url=args.run_url)
        case _:
            raise ValueError(f"unhandled command {args.command}")
    return 0


def main(argv: list[str] | None = None, environ: Mapping[str, str] | None = None) -> int:
    args = build_parser().parse_args(args=argv)
    if args.command == "digest":
        return digest_command(environ=os.environ if environ is None else environ)
    if args.command == "file-opportunities":
        return file_opportunities_command(args=args, environ=os.environ if environ is None else environ)
    if args.command == "evaluate" and (args.report is None) != (args.report_sha is None):
        print("--report and --report-sha must be given together", file=sys.stderr)
        return 2
    try:
        config = load_config(environ=os.environ if environ is None else environ)
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 2
    return run(args=args, github=GhCliGitHub(repo=config.repo), config=config, now=datetime.now(tz=UTC))


if __name__ == "__main__":
    sys.exit(main())
