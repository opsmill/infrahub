from __future__ import annotations

import logging
from typing import Any

import ujson

logger = logging.getLogger(__name__)

PAYLOAD_LOG_LIMIT: int = 2048  # characters shown inline; the full payload is logged at debug level


class WebhookLogFormatter:
    """Builds the log messages emitted during a webhook delivery.

    Its sole responsibility is the wording and layout of those messages, laid out over several
    labeled lines so an operator can find the request target, headers, payload, outcome, and retry
    position at a glance. It only returns strings; emitting them is left to the caller. Header
    redaction is not done here: the caller passes headers that are already masked.
    """

    def __init__(self, *, attempts: int, retry_delay_seconds: float, payload_log_limit: int) -> None:
        self._attempts = attempts
        self._retry_delay_seconds = retry_delay_seconds
        self._payload_log_limit = payload_log_limit

    def attempt_phrase(self, attempt: int | None) -> str:
        """Position a send within its retry sequence, or note that no flow run is driving retries."""
        if attempt is None:
            return "outside a flow run"
        return f"attempt {attempt}/{self._attempts}"

    def outgoing_request(
        self, *, webhook_name: str, url: str, headers: dict[str, Any], payload: Any, attempt: int | None
    ) -> str:
        """Summarize the outgoing request: target, headers one per line, and the truncated payload."""
        return (
            f"Webhook '{webhook_name}' {self.attempt_phrase(attempt)}\n"
            f"POST {url}\n"
            f"Headers:\n{self._headers_block(headers)}\n"
            f"Payload:\n{self._truncate(self._indent(self._to_json(payload)))}"
        )

    def full_payload(self, *, webhook_name: str, payload: Any, attempt: int | None) -> str:
        """Render the full, untruncated payload for the debug-level line."""
        return (
            f"Webhook '{webhook_name}' {self.attempt_phrase(attempt)} full payload:\n"
            f"{self._indent(self._to_json(payload))}"
        )

    def delivery_succeeded(self, *, url: str, status_code: int, attempt: int | None, elapsed_ms: float) -> str:
        return f"Webhook delivered to {url} {self.attempt_phrase(attempt)}, HTTP {status_code} in {elapsed_ms:.0f} ms"

    def delivery_failed(
        self, *, status_class: str, message: str, remediation: str, attempt: int | None, elapsed_ms: float
    ) -> str:
        return (
            f"Webhook delivery failed [{status_class}] {self.attempt_phrase(attempt)} "
            f"after {elapsed_ms:.0f} ms: {message.rstrip('.')}. {remediation}{self._retry_note(attempt)}"
        )

    def _retry_note(self, attempt: int | None) -> str:
        """State when the next attempt runs, or that none remain. Empty when no flow run drives retries."""
        if attempt is None:
            return ""
        if attempt < self._attempts:
            return f" Retrying in {self._retry_delay_seconds:.0f}s (attempt {attempt + 1}/{self._attempts})."
        return " No retries remaining."

    def _headers_block(self, headers: dict[str, Any]) -> str:
        if not headers:
            return "  (none)"
        return "\n".join(f"  {key}: {value}" for key, value in headers.items())

    def _truncate(self, text: str) -> str:
        if len(text) <= self._payload_log_limit:
            return text
        remaining = len(text) - self._payload_log_limit
        return (
            f"{text[: self._payload_log_limit]}… (+{remaining} characters; enable debug logging for the full payload)"
        )

    @staticmethod
    def _to_json(payload: Any) -> str:
        try:
            return ujson.dumps(payload, indent=2)
        except (TypeError, ValueError) as exc:
            logger.warning(
                "Webhook payload of type '%s' could not be serialized to JSON for logging (%s); "
                "falling back to its plain representation",
                type(payload).__name__,
                exc,
            )
            return str(payload)

    @staticmethod
    def _indent(text: str) -> str:
        return "\n".join(f"  {line}" for line in text.splitlines())
