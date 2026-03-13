from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class KeyValueWebhookResult:
    """Webhook UUIDs linked to a KeyValue node."""

    webhook_uuids: frozenset[str]


class KeyValueGetWebhooksQuery(Query):
    """Find webhooks linked to a KeyValue node via the webhook__headers relationship."""

    name = "keyvalue_get_webhooks"
    type = QueryType.READ

    def __init__(self, keyvalue_id: str, **kwargs: Any) -> None:
        self.keyvalue_id = keyvalue_id
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["keyvalue_id"] = self.keyvalue_id

        query = """
        MATCH (kv:CoreKeyValue {uuid: $keyvalue_id})
              -[e1:IS_RELATED]->(rl:Relationship {name: "webhook__headers"})
              <-[e2:IS_RELATED]-(webhook:CoreWebhook)
        """
        self.add_to_query(query)
        self.return_labels = ["DISTINCT webhook.uuid AS webhook_uuid"]

    def get_data(self) -> KeyValueWebhookResult:
        return KeyValueWebhookResult(
            webhook_uuids=frozenset(str(result.get("webhook_uuid")) for result in self.get_results())
        )
