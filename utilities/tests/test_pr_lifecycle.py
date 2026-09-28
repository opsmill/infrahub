from __future__ import annotations

# Ruff's pytest recommendations conflict with this standalone stdlib unittest suite.
# ruff: noqa: PT009, PT027
import contextlib
import io
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from utilities.pr_lifecycle import JsonValue, main, observe


class RecordingTransport:
    def __init__(self, *, identity: JsonValue = None) -> None:
        self.paths: list[str] = []
        self.identity = identity

    def get_json(self, *, path: str) -> JsonValue:
        self.paths.append(path)
        return self.identity


def fixed_clock() -> datetime:
    return datetime(2026, 9, 28, 12, tzinfo=UTC)


class TestCliSkeleton(unittest.TestCase):
    def test_observe_default_reports_incomplete_without_writes(self) -> None:
        transport = RecordingTransport(identity={"full_name": "opsmill/infrahub"})
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "report.json"
            result = main(
                ["--repository", "opsmill/infrahub", "--report", str(report_path)],
                transport=transport,
                clock=fixed_clock,
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(result, 1)
        self.assertEqual(transport.paths, ["/repos/opsmill/infrahub"])
        self.assertEqual(
            report,
            {
                "version": 1,
                "repository": "opsmill/infrahub",
                "mode": "observe",
                "observed_at": "2026-09-28T12:00:00+00:00",
                "complete": False,
                "closure_ready": False,
                "errors": ["Inventory collection is not implemented"],
            },
        )

    def test_repository_guard_precedes_transport(self) -> None:
        transport = RecordingTransport()
        with self.assertRaisesRegex(ValueError, "Repository must be opsmill/infrahub"):
            observe(repository="other/repository", transport=transport, clock=fixed_clock)
        self.assertEqual(transport.paths, [])

    def test_mismatched_server_identity_is_rejected(self) -> None:
        transport = RecordingTransport(identity={"full_name": "other/repository"})
        with self.assertRaisesRegex(ValueError, "GitHub repository identity does not match"):
            observe(repository="opsmill/infrahub", transport=transport, clock=fixed_clock)
        self.assertEqual(transport.paths, ["/repos/opsmill/infrahub"])

    def test_apply_mode_is_rejected_before_transport(self) -> None:
        transport = RecordingTransport()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            main(["--repository", "opsmill/infrahub", "--mode", "apply"], transport=transport)
        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(transport.paths, [])

    def test_naive_clock_is_rejected_before_transport(self) -> None:
        transport = RecordingTransport()
        with self.assertRaisesRegex(ValueError, "Clock must return a timezone-aware timestamp"):
            observe(
                repository="opsmill/infrahub",
                transport=transport,
                clock=lambda: fixed_clock().replace(tzinfo=None),
            )
        self.assertEqual(transport.paths, [])

    def test_fixture_files_are_valid_json(self) -> None:
        fixture_dir = Path(__file__).parent / "fixtures" / "pr_lifecycle"
        fixtures = sorted(fixture_dir.glob("*.json"))
        self.assertEqual([path.name for path in fixtures], ["activity.json", "mergeability.json", "reviews.json"])
        for path in fixtures:
            with self.subTest(fixture=path.name):
                self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), dict)


if __name__ == "__main__":
    unittest.main()
