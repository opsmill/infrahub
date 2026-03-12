from enum import StrEnum


class WebhookAction(StrEnum):
    CONFIGURE = "configure"
    DELETE = "delete"
    RECONCILE_ALL = "reconcile_all"


EVENT_TO_ACTION: dict[str, WebhookAction] = {
    "infrahub.node.created": WebhookAction.CONFIGURE,
    "infrahub.node.updated": WebhookAction.CONFIGURE,
    "infrahub.node.deleted": WebhookAction.DELETE,
}
