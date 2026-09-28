from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import NULL_VALUE, InfrahubKind
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

STORED_OBJECT_KINDS = (InfrahubKind.ARTIFACT, InfrahubKind.ARTIFACTCHECK, InfrahubKind.FILEOBJECT)
"""Kinds that record the checksum of the stored object they reference."""


class RecordedChecksumsQuery(Query):
    """Return the checksums recorded alongside a storage identifier, on any branch and at any time.

    A checksum only counts when it was recorded on the same branch and at the same time as the
    identifier, so the content of one version never matches the checksum of another.
    """

    name = "stored_object_recorded_checksums"
    type = QueryType.READ
    insert_return = False

    def __init__(self, identifier: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.params["identifier"] = identifier

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        kind_filter = " OR ".join(f"node:{kind}" for kind in STORED_OBJECT_KINDS)
        query = """
        MATCH (stored:AttributeValueIndexed {value: $identifier})
        MATCH (stored)<-[stored_edge:HAS_VALUE]-(:Attribute {name: "storage_id"})<-[:HAS_ATTRIBUTE]-(node:Node)
        WHERE stored_edge.status = "active" AND (%(kind_filter)s)
        MATCH (node)-[:HAS_ATTRIBUTE]->(:Attribute {name: "checksum"})-[checksum_edge:HAS_VALUE]->(checksum:AttributeValue)
        WHERE checksum_edge.status = "active"
            AND checksum_edge.branch = stored_edge.branch
            AND stored_edge.from < coalesce(checksum_edge.to, $open_end)
            AND checksum_edge.from < coalesce(stored_edge.to, $open_end)
        RETURN collect(DISTINCT checksum.value) AS checksums
        """ % {"kind_filter": kind_filter}
        # Edge times are ISO 8601 strings, so an open interval ends after every timestamp.
        self.params["open_end"] = "9999"
        self.add_to_query(query)
        self.return_labels = ["checksums"]

    def get_checksums(self) -> frozenset[str]:
        result = self.get_result()
        if result is None:
            return frozenset()
        return frozenset(
            checksum for checksum in result.get_as_list_of_type("checksums", str) if checksum != NULL_VALUE
        )
