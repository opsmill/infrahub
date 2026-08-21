from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generator, Sequence

from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class AttributeHealDetectionQueryResult:
    """One damaged (active node, schema-defined attribute) pair."""

    node_uuid: str
    attribute_name: str


class AttributeHealDetectionQuery(Query):
    """Find every active node of the given kinds missing any of the given attributes.

    Batched per kind: a single execution audits all nodes carrying the given labels
    against every attribute name. A node whose only row for an attribute is
    tombstoned counts as damaged. Deleted nodes are skipped.
    """

    name = "attribute_heal_detection"
    type = QueryType.READ
    insert_return = False

    def __init__(
        self,
        node_kinds: list[str],
        attribute_names: Sequence[str],
        **kwargs: Any,
    ) -> None:
        self.node_kinds = node_kinds
        self.attribute_names = list(attribute_names)
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)
        self.params["attribute_names"] = self.attribute_names

        node_kinds_str = "|".join(self.node_kinds)
        query = """
        MATCH (n:%(node_kinds_str)s)
        CALL (n) {
            MATCH (n)-[r:IS_PART_OF]->(:Root)
            WHERE %(branch_filter)s
            RETURN r AS is_part_of_e
            ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
            LIMIT 1
        }
        WITH n, is_part_of_e
        WHERE is_part_of_e.status = "active"
        UNWIND $attribute_names AS attr_name
        CALL (n, attr_name) {
            OPTIONAL MATCH (n)-[r:HAS_ATTRIBUTE]-(a:Attribute { name: attr_name })
            WHERE %(branch_filter)s
            RETURN r AS has_attr_e
            ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
            LIMIT 1
        }
        WITH n, attr_name, has_attr_e
        WHERE has_attr_e IS NULL OR has_attr_e.status = "deleted"
        RETURN n.uuid AS node_uuid, attr_name AS attribute_name
        """ % {
            "node_kinds_str": node_kinds_str,
            "branch_filter": branch_filter,
        }

        self.add_to_query(query)
        self.return_labels = ["node_uuid", "attribute_name"]

    def get_data(self) -> Generator[AttributeHealDetectionQueryResult, None, None]:
        for result in self.get_results():
            yield AttributeHealDetectionQueryResult(
                node_uuid=result.get_as_type("node_uuid", str),
                attribute_name=result.get_as_type("attribute_name", str),
            )
