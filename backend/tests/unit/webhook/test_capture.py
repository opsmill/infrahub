from infrahub.webhook.capture import CapturedHttp, build_http_capture
from infrahub.webhook.classifier import ClassifiedFailure, StatusClass
from infrahub.webhook.constants import RESPONSE_BODY_CAPTURE_LIMIT


def test_success_capture_has_request_and_response_and_no_error() -> None:
    capture = build_http_capture(
        url="http://target/hook",
        redacted_headers={"Content-Type": "application/json", "webhook-signature": "***"},
        status_code=200,
        body='{"ok": true}',
        latency_ms=7.5,
    )

    assert capture.request.url == "http://target/hook"
    assert capture.request.headers["webhook-signature"] == "***"
    assert capture.response is not None
    assert capture.response.status_code == 200
    assert capture.response.latency_ms == 7.5
    assert capture.error is None


def test_failure_capture_carries_the_classified_error() -> None:
    failure = ClassifiedFailure(
        status_class=StatusClass.HTTP_SERVER_ERROR, message="The target responded with HTTP 500."
    )

    capture = build_http_capture(
        url="http://target/hook",
        redacted_headers={},
        status_code=500,
        body="server error",
        latency_ms=3.0,
        failure=failure,
    )

    assert capture.error is not None
    assert capture.error.status_class == "HTTP_SERVER_ERROR"
    assert capture.error.message == "The target responded with HTTP 500."
    assert capture.error.remediation == failure.remediation
    assert capture.response is not None
    assert capture.response.status_code == 500


def test_transport_failure_has_no_response_block() -> None:
    failure = ClassifiedFailure(status_class=StatusClass.CONNECTION, message="Connection refused.")

    capture = build_http_capture(url="http://target/hook", redacted_headers={}, failure=failure)

    assert capture.response is None
    assert capture.error is not None
    assert capture.error.status_class == "CONNECTION"


def test_response_body_is_truncated_to_the_limit() -> None:
    capture = build_http_capture(
        url="http://target/hook",
        redacted_headers={},
        status_code=200,
        body="x" * (RESPONSE_BODY_CAPTURE_LIMIT + 500),
    )

    assert capture.response is not None
    assert capture.response.body is not None
    assert len(capture.response.body) == RESPONSE_BODY_CAPTURE_LIMIT


def test_artifact_data_is_json_serializable_dict() -> None:
    capture = build_http_capture(url="http://target/hook", redacted_headers={"a": "b"}, status_code=204)

    data = capture.to_artifact_data()

    assert isinstance(data, dict)
    assert data["request"] == {"url": "http://target/hook", "headers": {"a": "b"}}
    assert data["response"]["status_code"] == 204
    assert data["error"] is None
    assert CapturedHttp(**data).request.url == "http://target/hook"
