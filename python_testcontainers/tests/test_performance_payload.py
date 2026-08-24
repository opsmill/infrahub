import hashlib
import json

from infrahub_testcontainers.constants import PERFORMANCE_TEST_KIND, PERFORMANCE_TEST_VERSION
from infrahub_testcontainers.measurements import BRANCH_MERGE_TIME
from infrahub_testcontainers.models import ContextUnit
from infrahub_testcontainers.performance_test import InfrahubPerformanceTest


def test_request_checksum_covers_the_payload_on_the_wire() -> None:
    """Reproduce the receiver's verification: re-encode the payload and compare checksums."""
    performance_test = InfrahubPerformanceTest(results_url="http://localhost")
    performance_test.initialize(name="test_request_checksum_covers_the_payload_on_the_wire")
    performance_test.add_context("sites", 2, ContextUnit.COUNT)
    performance_test.add_measurement(BRANCH_MERGE_TIME, value=100)

    request = json.loads(performance_test._serialize_request())  # noqa: SLF001

    assert request["kind"] == PERFORMANCE_TEST_KIND
    assert request["payload_format"] == PERFORMANCE_TEST_VERSION
    assert request["data"] == performance_test._get_payload()  # noqa: SLF001
    assert (
        request["checksum"] == hashlib.sha256(json.dumps(request["data"], separators=(",", ":")).encode()).hexdigest()
    )
