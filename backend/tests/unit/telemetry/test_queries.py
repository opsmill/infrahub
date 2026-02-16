from __future__ import annotations

from infrahub.telemetry.queries import _normalize_end_date, _normalize_start_date


class TestDateNormalization:
    def test_bare_start_date_expands_to_start_of_day(self) -> None:
        assert _normalize_start_date("2026-04-10") == "2026-04-10T00:00:00.000000+00:00"

    def test_bare_end_date_expands_to_end_of_day(self) -> None:
        # The whole point: an end_date of "2026-04-10" must include snapshots
        # collected at any time during that day, not exclude them.
        assert _normalize_end_date("2026-04-10") == "2026-04-10T23:59:59.999999+00:00"

    def test_full_iso_timestamp_passes_through_start(self) -> None:
        value = "2026-04-10T08:30:00+00:00"
        assert _normalize_start_date(value) == value

    def test_full_iso_timestamp_passes_through_end(self) -> None:
        value = "2026-04-10T08:30:00+00:00"
        assert _normalize_end_date(value) == value

    def test_end_date_includes_same_day_created_at(self) -> None:
        """Regression: a snapshot created mid-day must be <= the normalized end_date."""
        normalized = _normalize_end_date("2026-04-10")
        same_day_created_at = "2026-04-10T14:30:00.123456+00:00"
        assert same_day_created_at <= normalized
