from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import NULL_VALUE
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class StorageChecksumsQuery(Query):
    """Return, for each storage identifier of a list, the checksums that nodes of one kind recorded with it.

    The identifiers are looked up on any branch and at any time. A checksum counts only when it was recorded on
    the same branch and at the same time as the identifier, so the file of one version of a node never matches the
    checksum of another. An identifier no node of the kind records has no row.

    The branch and time rules are those of the query that serves an artifact file; change them together.
    """

    name = "storage-checksums"
    type = QueryType.READ
    insert_return = False

    def __init__(self, storage_ids: list[str], kind: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.params["storage_ids"] = storage_ids
        self.kind = kind

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
        UNWIND $storage_ids AS storage_id
        MATCH (stored:AttributeValueIndexed {value: storage_id})
        MATCH (stored)<-[stored_edge:HAS_VALUE]-(:Attribute {name: "storage_id"})<-[:HAS_ATTRIBUTE]-(node:%(kind)s)
        WHERE stored_edge.status = "active"
        MATCH (node)-[:HAS_ATTRIBUTE]->(:Attribute {name: "checksum"})-[checksum_edge:HAS_VALUE]->(checksum:AttributeValue)
        WHERE checksum_edge.status = "active"
            AND checksum_edge.branch = stored_edge.branch
            AND stored_edge.from < coalesce(checksum_edge.to, $open_end)
            AND checksum_edge.from < coalesce(stored_edge.to, $open_end)
        RETURN storage_id, collect(DISTINCT checksum.value) AS checksums
        """ % {"kind": self.kind}
        # Edge times are ISO 8601 strings, so an open interval ends after every timestamp.
        self.params["open_end"] = "9999"
        self.add_to_query(query)
        self.return_labels = ["storage_id", "checksums"]

    def get_data(self) -> dict[str, frozenset[str]]:
        data: dict[str, frozenset[str]] = {}
        for result in self.get_results():
            checksums = result.get_as_list_of_type("checksums", str)
            data[result.get_as_type("storage_id", str)] = frozenset(c for c in checksums if c != NULL_VALUE)
        return data
