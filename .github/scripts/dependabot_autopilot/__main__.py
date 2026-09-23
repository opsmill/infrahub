from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from dependabot_autopilot.adapters import GhCliGitHub
from dependabot_autopilot.flow import Config, SuppliedReport, escalate, evaluate, invalidate, sweep

if TYPE_CHECKING:
    from collections.abc import Mapping

    from dependabot_autopilot.ports import GitHubPort

SUBCOMMANDS = ("invalidate", "evaluate", "sweep", "escalate", "file-opportunities", "digest")
NOT_IMPLEMENTED = ("file-opportunities", "digest")


class ConfigError(Exception):
    """A required environment variable is missing."""


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
    for name in NOT_IMPLEMENTED:
        subparsers.add_parser(name)
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
    if args.command in NOT_IMPLEMENTED:
        print(f"{args.command}: not implemented")
        return 0
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
