from infrahub.utils import get_fixtures_dir, merge_overlapping_intervals


def test_get_fixtures_dir():
    assert get_fixtures_dir().exists()


def test_merge_overlapping_intervals():
    # Test with no intervals
    assert merge_overlapping_intervals([]) == []

    # Test with single interval
    assert merge_overlapping_intervals([(1, 5)]) == [(1, 5)]

    # Test with non-overlapping intervals
    assert merge_overlapping_intervals([(1, 5), (7, 10)]) == [(1, 5), (7, 10)]

    # Test with overlapping intervals
    assert merge_overlapping_intervals([(1, 5), (3, 7)]) == [(1, 7)]
    assert merge_overlapping_intervals([(1, 5), (3, 7), (6, 10)]) == [(1, 10)]

    # Test with contained intervals
    assert merge_overlapping_intervals([(1, 10), (3, 7)]) == [(1, 10)]

    # Test with touching intervals
    assert merge_overlapping_intervals([(1, 5), (5, 10)]) == [(1, 10)]

    # Test with multiple overlapping intervals
    assert merge_overlapping_intervals([(1, 5), (3, 7), (6, 10), (8, 12)]) == [(1, 12)]

    # Test with intervals that need multiple merges
    assert merge_overlapping_intervals([(1, 3), (2, 4), (3, 5), (4, 6)]) == [(1, 6)]

    # Test with intervals that create gaps
    assert merge_overlapping_intervals([(1, 3), (5, 7), (9, 11)]) == [(1, 3), (5, 7), (9, 11)]

    # Test with single-point intervals
    assert merge_overlapping_intervals([(1, 1), (1, 5), (3, 3)]) == [(1, 5)]
    assert merge_overlapping_intervals([(1, 1), (1, 1)]) == [(1, 1)]

    # Test with intervals that extend beyond others
    assert merge_overlapping_intervals([(1, 5), (0, 10)]) == [(0, 10)]

    # Test with intervals that create complex patterns
    assert merge_overlapping_intervals([(1, 3), (2, 4), (5, 7), (6, 8), (9, 11)]) == [(1, 4), (5, 8), (9, 11)]
