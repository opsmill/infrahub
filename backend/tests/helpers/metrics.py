"""Helpers for asserting on the Prometheus metrics the code under test records."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prometheus_client import Histogram


def bucket_bounds(histogram: Histogram, labels: dict[str, str] | None = None) -> list[str]:
    """Return the finite `le` bounds of one labelled series of the histogram, in exposition order.

    A histogram with label names exposes no bucket until a series is observed, so pass the labels of
    a series the test has already observed.
    """
    expected_labels = labels or {}
    return [
        sample.labels["le"]
        for metric in histogram.collect()
        for sample in metric.samples
        if sample.name.endswith("_bucket")
        and sample.labels["le"] != "+Inf"
        and all(sample.labels.get(key) == value for key, value in expected_labels.items())
    ]
