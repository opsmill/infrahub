from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable

ALLOWED_REPOSITORY = "opsmill/infrahub"

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None


class Mode(StrEnum):
    """Execution mode recorded in diagnostic reports."""

    OBSERVE = "observe"


class ReadTransport(Protocol):
    """Read GitHub JSON without exposing any mutation operation."""

    def get_json(self, *, path: str) -> JsonValue: ...


@dataclass(frozen=True)
class ObservationReport:
    version: int
    repository: str
    mode: Mode
    observed_at: str
    complete: bool
    closure_ready: bool
    errors: tuple[str, ...]


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def guard_repository(repository: str) -> None:
    if repository != ALLOWED_REPOSITORY:
        raise ValueError(f"Repository must be {ALLOWED_REPOSITORY}")


def observe(
    *, repository: str, transport: ReadTransport | None, clock: Callable[[], datetime] = utc_now
) -> ObservationReport:
    guard_repository(repository)
    now = clock()
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Clock must return a timezone-aware timestamp")
    if transport is not None:
        identity = transport.get_json(path=f"/repos/{repository}")
        if not isinstance(identity, dict):
            raise ValueError("GitHub repository identity must be an object")
        if identity.get("full_name") != repository:
            raise ValueError("GitHub repository identity does not match the requested repository")
    return ObservationReport(
        version=1,
        repository=repository,
        mode=Mode.OBSERVE,
        observed_at=now.astimezone(tz=UTC).isoformat(),
        complete=False,
        closure_ready=False,
        errors=("Inventory collection is not implemented",),
    )


def main(
    argv: list[str] | None = None,
    *,
    transport: ReadTransport | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> int:
    parser = argparse.ArgumentParser(description="Observe Infrahub pull-request lifecycle state")
    parser.add_argument("command", nargs="?", choices=("observe",), default="observe")
    parser.add_argument("--repository", required=True, choices=(ALLOWED_REPOSITORY,))
    parser.add_argument("--mode", choices=(Mode.OBSERVE,), default=Mode.OBSERVE)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(args=argv)
    report = observe(repository=args.repository, transport=transport, clock=clock)
    serialized = json.dumps(asdict(report), indent=2) + "\n"
    if args.report is not None:
        args.report.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")
    return 0 if report.complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
