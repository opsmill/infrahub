from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.constants import NULL_VALUE, InfrahubKind
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class ArtifactChecksumsQueryResult:
    checksums: frozenset[str]


class ArtifactChecksumsQuery(Query):
    """Return the checksums artifacts recorded with a storage identifier, on any branch and at any time.

    A checksum only counts when it was recorded on the same branch and at the same time as the
    identifier, so the file of one artifact version never matches the checksum of another.
    """

    name = "artifact-checksums"
    type = QueryType.READ
    insert_return = False

    def __init__(self, storage_id: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.params["storage_id"] = storage_id

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
        MATCH (stored:AttributeValueIndexed {value: $storage_id})
        MATCH (stored)<-[stored_edge:HAS_VALUE]-(:Attribute {name: "storage_id"})<-[:HAS_ATTRIBUTE]-(artifact:%(kind)s)
        WHERE stored_edge.status = "active"
        MATCH (artifact)-[:HAS_ATTRIBUTE]->(:Attribute {name: "checksum"})-[checksum_edge:HAS_VALUE]->(checksum:AttributeValue)
        WHERE checksum_edge.status = "active"
            AND checksum_edge.branch = stored_edge.branch
            AND stored_edge.from < coalesce(checksum_edge.to, $open_end)
            AND checksum_edge.from < coalesce(stored_edge.to, $open_end)
        RETURN collect(DISTINCT checksum.value) AS checksums
        """ % {"kind": InfrahubKind.ARTIFACT}
        # Edge times are ISO 8601 strings, so an open interval ends after every timestamp.
        self.params["open_end"] = "9999"
        self.add_to_query(query)
        self.return_labels = ["checksums"]

    def get_data(self) -> ArtifactChecksumsQueryResult:
        result = self.get_result()
        checksums = result.get_as_list_of_type("checksums", str) if result else []
        return ArtifactChecksumsQueryResult(
            checksums=frozenset(checksum for checksum in checksums if checksum != NULL_VALUE)
        )
