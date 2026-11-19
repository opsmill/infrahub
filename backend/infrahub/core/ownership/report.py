"""Report of the data whose meaning changes with node owners.

The queries read only vertices and edges that a database of the release before holds, so the report runs before the
upgrade.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.constants import InfrahubKind
from infrahub.core.ownership.input import OWNER_KINDS
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

OPEN_EDGE_FILTER = 'r.status = "active" AND r.to IS NULL'


@dataclass(frozen=True)
class RepositoryOwnerRow:
    repository_id: str
    repository_kind: str
    node_kind: str
    attribute_name: str
    branch: str
    nb_attributes: int


@dataclass(frozen=True)
class OtherOwnerRow:
    owner_kind: str
    node_kind: str
    attribute_name: str
    branch: str
    nb_attributes: int


@dataclass(frozen=True)
class LinkOwnerRow:
    identifier: str
    peer_kinds: tuple[str, ...]
    owner_kind: str
    branch: str
    nb_links: int


@dataclass(frozen=True)
class ProtectedValueRow:
    node_kind: str
    attribute_name: str
    branch: str
    nb_values: int


@dataclass(frozen=True)
class OwnershipReport:
    repository_owners: list[RepositoryOwnerRow]
    other_owners: list[OtherOwnerRow]
    link_owners: list[LinkOwnerRow]
    protected_values: list[ProtectedValueRow]


class RepositoryOwnersReportQuery(Query):
    """Count the attributes that a repository owns, for each repository, kind, attribute name and branch."""

    name = "ownership_report_repository_owners"
    type = QueryType.READ

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
MATCH (repository:%(repository_label)s)<-[r:HAS_OWNER]-(attribute:Attribute)<-[:HAS_ATTRIBUTE]-(node:Node)
WHERE %(open_edge)s
        """ % {"repository_label": InfrahubKind.GENERICREPOSITORY, "open_edge": OPEN_EDGE_FILTER}
        self.add_to_query(query)
        self.return_labels = [
            "repository.uuid AS repository_id",
            "repository.kind AS repository_kind",
            "node.kind AS node_kind",
            "attribute.name AS attribute_name",
            "r.branch AS branch",
            "count(DISTINCT attribute) AS nb_attributes",
        ]
        self.order_by = ["repository_id", "node_kind", "attribute_name", "branch"]

    def get_rows(self) -> list[RepositoryOwnerRow]:
        return [
            RepositoryOwnerRow(
                repository_id=result.get_as_type("repository_id", str),
                repository_kind=result.get_as_type("repository_kind", str),
                node_kind=result.get_as_type("node_kind", str),
                attribute_name=result.get_as_type("attribute_name", str),
                branch=result.get_as_type("branch", str),
                nb_attributes=result.get_as_type("nb_attributes", int),
            )
            for result in self.get_results()
        ]


class OtherOwnersReportQuery(Query):
    """Count the attributes whose owner is not an account, an account group or a repository.

    The count is for each kind of owner, kind of node, attribute name and branch.
    """

    name = "ownership_report_other_owners"
    type = QueryType.READ

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["excluded_labels"] = sorted(OWNER_KINDS | {InfrahubKind.GENERICREPOSITORY})
        query = """
MATCH (owner:Node)<-[r:HAS_OWNER]-(attribute:Attribute)<-[:HAS_ATTRIBUTE]-(node:Node)
WHERE %(open_edge)s
AND NOT any(label IN labels(owner) WHERE label IN $excluded_labels)
        """ % {"open_edge": OPEN_EDGE_FILTER}
        self.add_to_query(query)
        self.return_labels = [
            "owner.kind AS owner_kind",
            "node.kind AS node_kind",
            "attribute.name AS attribute_name",
            "r.branch AS branch",
            "count(DISTINCT attribute) AS nb_attributes",
        ]
        self.order_by = ["owner_kind", "node_kind", "attribute_name", "branch"]

    def get_rows(self) -> list[OtherOwnerRow]:
        return [
            OtherOwnerRow(
                owner_kind=result.get_as_type("owner_kind", str),
                node_kind=result.get_as_type("node_kind", str),
                attribute_name=result.get_as_type("attribute_name", str),
                branch=result.get_as_type("branch", str),
                nb_attributes=result.get_as_type("nb_attributes", int),
            )
            for result in self.get_results()
        ]


class LinkOwnersReportQuery(Query):
    """Count the links that have an owner, for each relationship identifier, kind of owner and branch."""

    name = "ownership_report_link_owners"
    type = QueryType.READ

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
MATCH (link:Relationship)-[r:HAS_OWNER]->(owner:Node)
WHERE %(open_edge)s
WITH link, owner, r, COLLECT { MATCH (link)-[:IS_RELATED]-(peer:Node) RETURN DISTINCT peer.kind ORDER BY peer.kind } AS peer_kinds
        """ % {"open_edge": OPEN_EDGE_FILTER}
        self.add_to_query(query)
        self.return_labels = [
            "link.name AS identifier",
            "peer_kinds",
            "owner.kind AS owner_kind",
            "r.branch AS branch",
            "count(DISTINCT link) AS nb_links",
        ]
        self.order_by = ["identifier", "peer_kinds", "owner_kind", "branch"]

    def get_rows(self) -> list[LinkOwnerRow]:
        return [
            LinkOwnerRow(
                identifier=result.get_as_type("identifier", str),
                peer_kinds=tuple(result.get_as_list_of_type("peer_kinds", str)),
                owner_kind=result.get_as_type("owner_kind", str),
                branch=result.get_as_type("branch", str),
                nb_links=result.get_as_type("nb_links", int),
            )
            for result in self.get_results()
        ]


class ProtectedValuesReportQuery(Query):
    """Count the attribute values with `is_protected` set, for each kind, attribute name and branch."""

    name = "ownership_report_protected_values"
    type = QueryType.READ

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
MATCH (:Boolean {value: true})<-[r:IS_PROTECTED]-(attribute:Attribute)<-[:HAS_ATTRIBUTE]-(node:Node)
WHERE %(open_edge)s
        """ % {"open_edge": OPEN_EDGE_FILTER}
        self.add_to_query(query)
        self.return_labels = [
            "node.kind AS node_kind",
            "attribute.name AS attribute_name",
            "r.branch AS branch",
            "count(DISTINCT attribute) AS nb_values",
        ]
        self.order_by = ["node_kind", "attribute_name", "branch"]

    def get_rows(self) -> list[ProtectedValueRow]:
        return [
            ProtectedValueRow(
                node_kind=result.get_as_type("node_kind", str),
                attribute_name=result.get_as_type("attribute_name", str),
                branch=result.get_as_type("branch", str),
                nb_values=result.get_as_type("nb_values", int),
            )
            for result in self.get_results()
        ]


async def build_ownership_report(db: InfrahubDatabase) -> OwnershipReport:
    """Return the attribute owners that are not accounts or groups, the links with owners and the protected values.

    The report covers every branch.
    """
    repository_owners = await RepositoryOwnersReportQuery.init(db=db)
    await repository_owners.execute(db=db)
    other_owners = await OtherOwnersReportQuery.init(db=db)
    await other_owners.execute(db=db)
    link_owners = await LinkOwnersReportQuery.init(db=db)
    await link_owners.execute(db=db)
    protected_values = await ProtectedValuesReportQuery.init(db=db)
    await protected_values.execute(db=db)
    return OwnershipReport(
        repository_owners=repository_owners.get_rows(),
        other_owners=other_owners.get_rows(),
        link_owners=link_owners.get_rows(),
        protected_values=protected_values.get_rows(),
    )
