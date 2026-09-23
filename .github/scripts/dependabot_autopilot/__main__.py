from __future__ import annotations

import argparse
import sys

SUBCOMMANDS = ("invalidate", "evaluate", "sweep", "file-opportunities", "digest")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dependabot_autopilot")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in SUBCOMMANDS:
        subparsers.add_parser(name)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(args=argv)
    print(f"{args.command}: not implemented")
    return 0


if __name__ == "__main__":
    sys.exit(main())
