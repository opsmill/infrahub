from __future__ import annotations

import logging
from dataclasses import dataclass

import pytest
import ujson

from infrahub.webhook.log_formatter import WebhookLogFormatter

LOG_FORMATTER_LOGGER = "infrahub.webhook.log_formatter"

ATTEMPTS = 4
RETRY_DELAY_SECONDS = 120.0
PAYLOAD_LIMIT = 2048


@pytest.fixture
def formatter() -> WebhookLogFormatter:
    return WebhookLogFormatter(
        attempts=ATTEMPTS, retry_delay_seconds=RETRY_DELAY_SECONDS, payload_log_limit=PAYLOAD_LIMIT
    )


@dataclass
class AttemptPhraseCase:
    name: str
    attempt: int | None
    expected: str


@pytest.mark.parametrize(
    "case",
    [
        AttemptPhraseCase(name="first_attempt", attempt=1, expected="attempt 1/4"),
        AttemptPhraseCase(name="last_attempt", attempt=ATTEMPTS, expected="attempt 4/4"),
        AttemptPhraseCase(name="no_flow_run", attempt=None, expected="outside a flow run"),
    ],
    ids=lambda case: case.name,
)
def test_attempt_phrase(formatter: WebhookLogFormatter, case: AttemptPhraseCase) -> None:
    assert formatter.attempt_phrase(case.attempt) == case.expected


def test_outgoing_request_lays_out_target_headers_and_payload_over_labeled_lines(
    formatter: WebhookLogFormatter,
) -> None:
    message = formatter.outgoing_request(
        webhook_name="notify",
        url="https://example.test/hook",
        headers={"Accept": "application/json", "X-Token": "***"},
        payload={"event": "created", "data": {"name": "device-01"}},
        attempt=1,
    )

    assert message == (
        "Webhook 'notify' attempt 1/4\n"
        "POST https://example.test/hook\n"
        "Headers:\n"
        "  Accept: application/json\n"
        "  X-Token: ***\n"
        "Payload:\n"
        "  {\n"
        '    "event": "created",\n'
        '    "data": {\n'
        '      "name": "device-01"\n'
        "    }\n"
        "  }"
    )


def test_outgoing_request_notes_when_there_are_no_headers(formatter: WebhookLogFormatter) -> None:
    message = formatter.outgoing_request(
        webhook_name="notify", url="https://example.test/hook", headers={}, payload={}, attempt=1
    )

    assert message == (
        "Webhook 'notify' attempt 1/4\nPOST https://example.test/hook\nHeaders:\n  (none)\nPayload:\n  {}"
    )


def test_outgoing_request_keeps_the_headers_in_the_order_given(formatter: WebhookLogFormatter) -> None:
    message = formatter.outgoing_request(
        webhook_name="notify",
        url="https://example.test/hook",
        headers={"webhook-id": "msg_1", "webhook-timestamp": "1783928359", "webhook-signature": "***"},
        payload={},
        attempt=2,
    )

    assert "Headers:\n  webhook-id: msg_1\n  webhook-timestamp: 1783928359\n  webhook-signature: ***\n" in message


def test_outgoing_request_truncates_the_inline_payload_and_marks_the_overflow(
    formatter: WebhookLogFormatter,
) -> None:
    payload = {"blob": "x" * (PAYLOAD_LIMIT * 2)}

    message = formatter.outgoing_request(
        webhook_name="notify", url="https://example.test/hook", headers={}, payload=payload, attempt=1
    )

    payload_section = message.split("Payload:\n", 1)[1]
    # The inline payload is capped at the limit (plus the overflow marker), each line indented by two spaces.
    unindented = "\n".join(line[2:] for line in payload_section.splitlines())
    assert unindented.startswith('{\n  "blob": "' + "x" * 100)
    assert unindented.endswith("characters; enable debug logging for the full payload)")
    assert "… (+" in unindented


def test_outgoing_request_does_not_truncate_a_payload_at_the_limit(formatter: WebhookLogFormatter) -> None:
    small = WebhookLogFormatter(attempts=ATTEMPTS, retry_delay_seconds=RETRY_DELAY_SECONDS, payload_log_limit=100)
    message = small.outgoing_request(
        webhook_name="notify", url="https://example.test/hook", headers={}, payload={"k": "v"}, attempt=1
    )

    assert message.endswith('Payload:\n  {\n    "k": "v"\n  }')


def test_inline_payload_stays_within_the_limit_including_indentation(formatter: WebhookLogFormatter) -> None:
    payload = {"blob": "x" * (PAYLOAD_LIMIT * 2)}

    message = formatter.outgoing_request(
        webhook_name="notify", url="https://example.test/hook", headers={}, payload=payload, attempt=1
    )

    payload_section = message.split("Payload:\n", 1)[1]
    inline = payload_section.split("… (+", 1)[0]  # the shown payload, before the overflow marker
    assert len(inline) <= PAYLOAD_LIMIT


class _Unserializable:
    def __repr__(self) -> str:
        return "<unserializable>"


def test_outgoing_request_falls_back_to_plain_repr_when_payload_is_not_json_serializable(
    formatter: WebhookLogFormatter, caplog: pytest.LogCaptureFixture
) -> None:
    payload = _Unserializable()
    # The serializer's own error text is library-specific; capture it from the same call so the
    # rest of the warning can be asserted exactly.
    with pytest.raises((TypeError, ValueError)) as exc_info:
        ujson.dumps(payload, indent=2)
    serialization_error = str(exc_info.value)

    with caplog.at_level(logging.WARNING, logger=LOG_FORMATTER_LOGGER):
        message = formatter.outgoing_request(
            webhook_name="notify", url="https://example.test/hook", headers={}, payload=payload, attempt=1
        )

    assert message == (
        "Webhook 'notify' attempt 1/4\nPOST https://example.test/hook\nHeaders:\n  (none)\nPayload:\n  <unserializable>"
    )
    warnings = [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING]
    assert warnings == [
        f"Webhook payload of type '_Unserializable' could not be serialized to JSON for logging "
        f"({serialization_error}); falling back to its plain representation"
    ]


def test_full_payload_is_untruncated_and_indented(formatter: WebhookLogFormatter) -> None:
    payload = {"blob": "y" * (PAYLOAD_LIMIT * 2)}

    message = formatter.full_payload(webhook_name="notify", payload=payload, attempt=3)

    assert message.startswith("Webhook 'notify' attempt 3/4 full payload:\n")
    assert "… (+" not in message
    assert ("y" * (PAYLOAD_LIMIT * 2)) in message


def test_delivery_succeeded(formatter: WebhookLogFormatter) -> None:
    message = formatter.delivery_succeeded(
        url="https://example.test/hook", status_code=200, attempt=1, elapsed_ms=142.7
    )

    assert message == "Webhook delivered to https://example.test/hook attempt 1/4, HTTP 200 in 143 ms"


@dataclass
class FailureCase:
    name: str
    attempt: int | None
    expected_tail: str


@pytest.mark.parametrize(
    "case",
    [
        FailureCase(
            name="mid_run_announces_next_retry",
            attempt=2,
            expected_tail=" Retrying in 120s (attempt 3/4).",
        ),
        FailureCase(
            name="last_attempt_reports_no_retries_remaining",
            attempt=ATTEMPTS,
            expected_tail=" No retries remaining.",
        ),
        FailureCase(
            name="outside_flow_run_has_no_retry_note",
            attempt=None,
            expected_tail="",
        ),
    ],
    ids=lambda case: case.name,
)
def test_delivery_failed_reports_class_reason_remediation_and_retry_note(
    formatter: WebhookLogFormatter, case: FailureCase
) -> None:
    message = formatter.delivery_failed(
        status_class="HTTP_SERVER_ERROR",
        message="The target responded with HTTP 503.",
        remediation="The target returned a server error; retry, or check the target.",
        attempt=case.attempt,
        elapsed_ms=88.0,
    )

    location = "outside a flow run" if case.attempt is None else f"attempt {case.attempt}/4"
    assert message == (
        f"Webhook delivery failed [HTTP_SERVER_ERROR] {location} after 88 ms: "
        "The target responded with HTTP 503. "
        f"The target returned a server error; retry, or check the target.{case.expected_tail}"
    )
