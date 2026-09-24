from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.constants import NULL_VALUE, InfrahubKind
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class RecordedArtifactChecksum:
    node_id: str
    kind: str
    branch: str
    checksum: str | None
    """None when the node references the object without having recorded a checksum for it."""


class ArtifactStorageChecksumQuery(Query):
    """Find the checksums recorded for a storage object by the artifacts and artifact checks referencing it.

    The storage_id and the checksum of a node are written in the same save, so their HAS_VALUE edges
    start at the same time on the same branch. Pairing the two on their time range returns the checksum
    recorded for this exact object, on every branch and in past versions: a proposed change diff reads
    previous storage ids with no branch context. The ranges are half-open, a value stops being current
    at the instant the next one starts, so a version never pairs with the checksum of the next one.
    """

    name = "artifact_storage_checksum"
    type: QueryType = QueryType.READ

    def __init__(self, storage_id: str, **kwargs: Any) -> None:
        self.storage_id = storage_id
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["storage_id"] = self.storage_id
        self.params["kinds"] = [InfrahubKind.ARTIFACT, InfrahubKind.ARTIFACTCHECK]
        query = """
        MATCH (sv:AttributeValueIndexed { value: $storage_id })<-[r1:HAS_VALUE]-(:Attribute { name: "storage_id" })<-[:HAS_ATTRIBUTE]-(n:Node)
        WHERE n.kind IN $kinds
        MATCH (n)-[:HAS_ATTRIBUTE]->(:Attribute { name: "checksum" })-[r2:HAS_VALUE]->(cv:AttributeValue)
        WHERE r2.branch = r1.branch
          AND r2.from < coalesce(r1.to, "9999")
          AND coalesce(r2.to, "9999") > r1.from
        WITH DISTINCT n.uuid AS node_id, n.kind AS kind, r1.branch AS branch, cv.value AS checksum
        """
        self.add_to_query(query)
        self.return_labels = ["node_id", "kind", "branch", "checksum"]

    def get_recorded_checksums(self) -> list[RecordedArtifactChecksum]:
        return [
            RecordedArtifactChecksum(
                node_id=result.get_as_type(label="node_id", return_type=str),
                kind=result.get_as_type(label="kind", return_type=str),
                branch=result.get_as_type(label="branch", return_type=str),
                checksum=_recorded_checksum(result.get_as_optional_type(label="checksum", return_type=str)),
            )
            for result in self.get_results()
        ]


def _recorded_checksum(value: str | None) -> str | None:
    return None if value in (None, NULL_VALUE) else value
