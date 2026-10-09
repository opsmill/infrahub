from __future__ import annotations

STATUS = "delivery_status"
FAILURE_CAUSE = "delivery_failure_cause"
ERROR = "delivery_error"
QUEUE = "delivery_queue"
HELD_REGENERATION = "delivery_held_regeneration"
LAST_ABANDONMENT = "delivery_last_abandonment"
LAST_DELIVERED_COMMIT = "delivery_last_delivered_commit"
REVERTED = "delivery_reverted"
PROGRESS = "delivery_progress"
DELIVERY_ATTRIBUTES = (
    STATUS,
    FAILURE_CAUSE,
    ERROR,
    QUEUE,
    HELD_REGENERATION,
    LAST_ABANDONMENT,
    LAST_DELIVERED_COMMIT,
    REVERTED,
    PROGRESS,
)
