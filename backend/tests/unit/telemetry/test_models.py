"""Unit tests for how the telemetry payload writes its CPU shares as JSON.

The telemetry endpoint checks the payload's checksum by writing the received data
out again in JavaScript, which cannot tell 2.0 from 2, so a whole-number share has
to be sent as an integer for the checksum to match.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from infrahub.telemetry.models import TelemetryPerWorkerData


@dataclass
class JsonCase:
    name: str
    share: TelemetryPerWorkerData
    expected_json: str


JSON_CASES = [
    JsonCase(
        name="whole_number_shares_are_written_as_integers",
        share=TelemetryPerWorkerData(processor_available=1.0, processor_assigned=2.0, memory_total=3_221_225_472),
        expected_json=(
            '{"processor_available": 1, "processor_assigned": 2, "memory_total": 3221225472, "memory_available": null}'
        ),
    ),
    JsonCase(
        name="fractional_shares_keep_their_decimals",
        share=TelemetryPerWorkerData(processor_available=0.5, processor_assigned=1.33),
        expected_json=(
            '{"processor_available": 0.5, "processor_assigned": 1.33, "memory_total": null, "memory_available": null}'
        ),
    ),
    JsonCase(
        name="unknown_shares_stay_null",
        share=TelemetryPerWorkerData(),
        expected_json=(
            '{"processor_available": null, "processor_assigned": null, "memory_total": null, "memory_available": null}'
        ),
    ),
]


@pytest.mark.parametrize("case", JSON_CASES, ids=[case.name for case in JSON_CASES])
def test_cpu_shares_json_text(case: JsonCase) -> None:
    assert json.dumps(case.share.model_dump(mode="json")) == case.expected_json
