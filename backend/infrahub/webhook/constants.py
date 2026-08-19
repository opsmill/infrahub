from enum import StrEnum

CACHE_KEY_PREFIX = "webhook"

WEBHOOK_SEND_RETRIES: int = 3
WEBHOOK_SEND_RETRY_DELAY_SECONDS: float = 120  # fixed 2m delay between attempts
WEBHOOK_SEND_ATTEMPTS: int = WEBHOOK_SEND_RETRIES + 1  # the initial try plus its retries

RESPONSE_BODY_CAPTURE_LIMIT = 10_000


class WebhookAction(StrEnum):
    CONFIGURE = "configure"
    DELETE = "delete"
    RECONCILE_ALL = "reconcile_all"


EVENT_TO_ACTION: dict[str, WebhookAction] = {
    "infrahub.node.created": WebhookAction.CONFIGURE,
    "infrahub.node.updated": WebhookAction.CONFIGURE,
    "infrahub.node.deleted": WebhookAction.DELETE,
}
