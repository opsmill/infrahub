"""AWS Neptune-specific database implementations.

Neptune's OpenCypher support has limited index management compared to Neo4j.
Neptune manages indexes internally and does not support the full CREATE INDEX
syntax. This module provides no-op or best-effort index management.
"""

from __future__ import annotations

from infrahub.constants.database import EntityType, IndexType
from infrahub.log import get_logger

from .index import IndexInfo, IndexItem, IndexManagerBase

log = get_logger()


class IndexNodeNeptune(IndexItem):
    """Neptune does not support explicit index creation via OpenCypher.

    Indexes are managed automatically by Neptune's query optimizer. These
    methods are no-ops that log the intended action for visibility.
    """

    def get_add_query(self) -> str:
        # Neptune does not support CREATE INDEX via OpenCypher
        # Return a comment-only query that is safe to execute
        log.debug(
            "Neptune manages indexes internally; skipping explicit index creation",
            label=self.label,
            properties=self.properties,
        )
        return f"// Neptune: index on :{self.label}({', '.join(self.properties)}) managed internally"

    def get_drop_query(self) -> str:
        log.debug(
            "Neptune manages indexes internally; skipping explicit index drop",
            label=self.label,
            properties=self.properties,
        )
        return f"// Neptune: drop index on :{self.label}({', '.join(self.properties)}) not supported"


class IndexManagerNeptune(IndexManagerBase):
    """Index manager for AWS Neptune.

    Neptune automatically indexes all properties and does not expose index
    management through OpenCypher queries. The add/drop operations are no-ops,
    and list returns an empty set since Neptune does not expose index metadata.
    """

    def init(self, nodes: list[IndexItem], rels: list[IndexItem]) -> None:  # noqa: ARG002
        self.nodes = [IndexNodeNeptune(**item.model_dump()) for item in nodes]
        # Neptune does not support relationship indexes
        self.rels = []
        self.initialized = True

    async def add(self) -> None:
        # Neptune manages indexes automatically
        log.info("Neptune indexes are managed automatically by the query optimizer; skipping explicit index creation")

    async def drop(self) -> None:
        # Neptune manages indexes automatically
        log.info("Neptune indexes are managed automatically by the query optimizer; skipping explicit index drop")

    async def list(self) -> list[IndexInfo]:
        # Neptune does not expose index information via OpenCypher
        # Return a synthetic list based on what we know we'd want indexed
        results = []
        for node in self.nodes:
            results.append(
                IndexInfo(
                    name=f"neptune_auto_{node.label}_{'_'.join(node.properties)}",
                    label=node.label,
                    properties=node.properties,
                    type=IndexType.NOT_APPLICABLE,
                    entity_type=EntityType.NODE,
                )
            )
        return results
