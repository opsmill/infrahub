from datetime import UTC, datetime, timedelta, timezone

from infrahub.graphql.resolvers.resolver import _transform_metadata_day_filters


class TestMetadataDayFilterTransformation:
    """Unit tests for _transform_metadata_day_filters function."""

    def test_transform_created_at_midnight_to_day_range(self) -> None:
        """Test that created_at with midnight time is transformed into day range."""
        midnight = datetime(2025, 2, 3, 0, 0, 0, tzinfo=UTC)
        filters = {"node_metadata__created_at": midnight}

        result = _transform_metadata_day_filters(filters)

        # __after should be one microsecond before midnight to include objects at exactly midnight
        expected_after = midnight - timedelta(microseconds=1)
        assert "node_metadata__created_at" not in result
        assert result["node_metadata__created_at__after"] == expected_after
        assert result["node_metadata__created_at__before"] == midnight + timedelta(days=1)

    def test_transform_updated_at_midnight_to_day_range(self) -> None:
        """Test that updated_at with midnight time is transformed into day range."""
        midnight = datetime(2025, 2, 3, 0, 0, 0, tzinfo=UTC)
        filters = {"node_metadata__updated_at": midnight}

        result = _transform_metadata_day_filters(filters)

        # __after should be one microsecond before midnight to include objects at exactly midnight
        expected_after = midnight - timedelta(microseconds=1)
        assert "node_metadata__updated_at" not in result
        assert result["node_metadata__updated_at__after"] == expected_after
        assert result["node_metadata__updated_at__before"] == midnight + timedelta(days=1)

    def test_non_midnight_time_not_transformed(self) -> None:
        """Test that non-midnight datetime is not transformed."""
        non_midnight = datetime(2025, 2, 3, 14, 30, 0, tzinfo=UTC)
        filters = {"node_metadata__created_at": non_midnight}

        result = _transform_metadata_day_filters(filters)

        assert result["node_metadata__created_at"] == non_midnight
        assert "node_metadata__created_at__after" not in result
        assert "node_metadata__created_at__before" not in result

    def test_midnight_with_microseconds_not_transformed(self) -> None:
        """Test that midnight with microseconds is not transformed."""
        almost_midnight = datetime(2025, 2, 3, 0, 0, 0, 1, tzinfo=UTC)
        filters = {"node_metadata__created_at": almost_midnight}

        result = _transform_metadata_day_filters(filters)

        assert result["node_metadata__created_at"] == almost_midnight
        assert "node_metadata__created_at__after" not in result

    def test_midnight_with_timezone_offset_still_transforms(self) -> None:
        """Test that midnight with timezone offset still triggers transformation."""
        # Midnight in UTC+5:30 timezone
        tz_offset = timezone(timedelta(hours=5, minutes=30))
        midnight_offset = datetime(2025, 2, 3, 0, 0, 0, tzinfo=tz_offset)
        filters = {"node_metadata__created_at": midnight_offset}

        result = _transform_metadata_day_filters(filters)

        expected_after = midnight_offset - timedelta(microseconds=1)
        assert "node_metadata__created_at" not in result
        assert result["node_metadata__created_at__after"] == expected_after
        assert result["node_metadata__created_at__before"] == midnight_offset + timedelta(days=1)

    def test_preserves_other_filters(self) -> None:
        """Test that other filters are preserved unchanged."""
        midnight = datetime(2025, 2, 3, 0, 0, 0, tzinfo=UTC)
        filters = {
            "node_metadata__created_at": midnight,
            "name__value": "test",
            "ids": ["id1", "id2"],
        }

        result = _transform_metadata_day_filters(filters)

        assert result["name__value"] == "test"
        assert result["ids"] == ["id1", "id2"]

    def test_transforms_both_created_and_updated_at(self) -> None:
        """Test that both created_at and updated_at are transformed when both are midnight."""
        midnight1 = datetime(2025, 2, 3, 0, 0, 0, tzinfo=UTC)
        midnight2 = datetime(2025, 2, 5, 0, 0, 0, tzinfo=UTC)
        filters = {
            "node_metadata__created_at": midnight1,
            "node_metadata__updated_at": midnight2,
        }

        result = _transform_metadata_day_filters(filters)

        assert "node_metadata__created_at" not in result
        assert "node_metadata__updated_at" not in result
        assert result["node_metadata__created_at__after"] == midnight1 - timedelta(microseconds=1)
        assert result["node_metadata__created_at__before"] == midnight1 + timedelta(days=1)
        assert result["node_metadata__updated_at__after"] == midnight2 - timedelta(microseconds=1)
        assert result["node_metadata__updated_at__before"] == midnight2 + timedelta(days=1)

    def test_empty_filters_returns_empty(self) -> None:
        """Test that empty filters returns empty dict."""
        result = _transform_metadata_day_filters({})
        assert result == {}

    def test_non_datetime_value_not_transformed(self) -> None:
        """Test that non-datetime values are not transformed."""
        filters = {"node_metadata__created_at": "2025-02-03T00:00:00Z"}

        result = _transform_metadata_day_filters(filters)

        assert result["node_metadata__created_at"] == "2025-02-03T00:00:00Z"

    def test_non_utc_timezone_midnight_preserves_timezone_in_filters(self) -> None:
        """Test that midnight in non-UTC timezone produces correct __after and __before with preserved timezone."""
        # Create midnight in US Eastern timezone (UTC-5)
        eastern_tz = timezone(timedelta(hours=-5))
        midnight_eastern = datetime(2025, 3, 15, 0, 0, 0, tzinfo=eastern_tz)
        filters = {"node_metadata__created_at": midnight_eastern}

        result = _transform_metadata_day_filters(filters)

        # Verify original filter is removed
        assert "node_metadata__created_at" not in result

        # Verify __after is one microsecond before midnight in the same timezone
        after_value = result["node_metadata__created_at__after"]
        assert after_value.year == 2025
        assert after_value.month == 3
        assert after_value.day == 14  # Previous day
        assert after_value.hour == 23
        assert after_value.minute == 59
        assert after_value.second == 59
        assert after_value.microsecond == 999999
        assert after_value.tzinfo == eastern_tz  # Timezone preserved

        # Verify __before is midnight of the next day in the same timezone
        before_value = result["node_metadata__created_at__before"]
        assert before_value.year == 2025
        assert before_value.month == 3
        assert before_value.day == 16  # Next day
        assert before_value.hour == 0
        assert before_value.minute == 0
        assert before_value.second == 0
        assert before_value.microsecond == 0
        assert before_value.tzinfo == eastern_tz  # Timezone preserved
