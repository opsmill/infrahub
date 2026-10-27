from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub_sdk.diff import NodeDiff, NodeDiffElement, NodeDiffSummary

from infrahub.core.constants import DiffAction, RelationshipCardinality
from infrahub.core.diff.model.diff import DiffElementType
from infrahub.core.query import Query, QueryType
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class BranchEdit:
    """The latest edit made on a branch to one field of a node.

    ``field_name`` is the attribute name, or the relationship identifier when ``is_relationship`` is set.
    ``node_created_at`` is set only for a node created on the branch, and ``node_removed_at`` only for a node
    removed from it.
    """

    node_id: str
    kind: str
    field_name: str
    is_relationship: bool
    edited_at: Timestamp
    node_created_at: Timestamp | None = None
    node_removed_at: Timestamp | None = None


class BranchEditsQuery(Query):
    """Return the latest edit made on the query branch after a time to each field of nodes of the given kinds.

    An edge ended on the branch counts as an edit at its end time, which is how a relationship added and
    removed on the same branch records the removal.
    """

    name = "branch-edits"
    type = QueryType.READ

    def __init__(self, since: Timestamp, kinds: list[str], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.since = since
        self.kinds = kinds

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["branch_name"] = self.branch.name
        self.params["since"] = self.since.to_string()
        self.params["kinds"] = self.kinds

        query = """
CALL () {
    MATCH (n:Node)-[edit:HAS_ATTRIBUTE]->(field:Attribute)
    WHERE edit.branch = $branch_name AND n.kind IN $kinds
    RETURN n, field.name AS field_name, FALSE AS is_relationship, coalesce(edit.to, edit.from) AS edited_at
    UNION ALL
    MATCH (n:Node)-[:HAS_ATTRIBUTE]->(field:Attribute)-[edit:HAS_VALUE|IS_PROTECTED|HAS_OWNER|HAS_SOURCE]->()
    WHERE edit.branch = $branch_name AND n.kind IN $kinds
    RETURN n, field.name AS field_name, FALSE AS is_relationship, coalesce(edit.to, edit.from) AS edited_at
    UNION ALL
    MATCH (n:Node)-[edit:IS_RELATED]-(field:Relationship)
    WHERE edit.branch = $branch_name AND n.kind IN $kinds
    RETURN n, field.name AS field_name, TRUE AS is_relationship, coalesce(edit.to, edit.from) AS edited_at
    UNION ALL
    MATCH (n:Node)-[:IS_RELATED]-(field:Relationship)-[edit:IS_PROTECTED|HAS_OWNER|HAS_SOURCE]->()
    WHERE edit.branch = $branch_name AND n.kind IN $kinds
    RETURN n, field.name AS field_name, TRUE AS is_relationship, coalesce(edit.to, edit.from) AS edited_at
}
WITH n, field_name, is_relationship, edited_at
WHERE edited_at > $since
WITH n, field_name, is_relationship, max(edited_at) AS edited_at
CALL (n) {
    MATCH (n)-[part:IS_PART_OF]->(:Root)
    WITH part
    ORDER BY part.from DESC
    WITH collect(part) AS parts
    RETURN
        CASE
            WHEN all(p IN parts WHERE p.branch = $branch_name)
            THEN reduce(created = NULL, p IN parts | CASE WHEN p.status = "active" THEN p.from ELSE created END)
        END AS node_created_at,
        CASE
            WHEN parts[0].status = "deleted" THEN parts[0].from
            WHEN parts[0].to IS NOT NULL THEN parts[0].to
        END AS node_removed_at
}
WITH n.uuid AS node_id, n.kind AS kind, field_name, is_relationship, edited_at, node_created_at, node_removed_at
        """
        self.add_to_query(query)
        self.return_labels = [
            "node_id",
            "kind",
            "field_name",
            "is_relationship",
            "edited_at",
            "node_created_at",
            "node_removed_at",
        ]
        self.order_by = ["node_id", "field_name", "is_relationship"]

    def get_data(self) -> Generator[BranchEdit]:
        for result in self.get_results():
            yield BranchEdit(
                node_id=result.get_as_type("node_id", str),
                kind=result.get_as_type("kind", str),
                field_name=result.get_as_type("field_name", str),
                is_relationship=result.get_as_type("is_relationship", bool),
                edited_at=Timestamp(result.get_as_type("edited_at", str)),
                node_created_at=_optional_timestamp(result.get_as_optional_type("node_created_at", str)),
                node_removed_at=_optional_timestamp(result.get_as_optional_type("node_removed_at", str)),
            )


def _optional_timestamp(value: str | None) -> Timestamp | None:
    return Timestamp(value) if value is not None else None


class BranchEditReader:
    """Read the edits made on a branch, which a branch diff hides once a value is back to its target-branch value."""

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def read(self, branch: Branch, since: Timestamp, kinds: Iterable[str]) -> list[BranchEdit]:
        kind_list = sorted(set(kinds))
        if not kind_list:
            return []
        query = await BranchEditsQuery.init(db=self.db, branch=branch, since=since, kinds=kind_list)
        await query.execute(db=self.db)
        return list(query.get_data())


def edits_seen_since(edits: Iterable[BranchEdit], since: Timestamp, latest_check: Timestamp) -> list[BranchEdit]:
    """Return the edits made after ``since`` that a check up to ``latest_check`` can have missed.

    A node created on the branch after ``latest_check`` and already removed was never seen by such a check and is
    no longer on the branch, so its edits cannot make the check out of date.
    """
    return [
        edit
        for edit in edits
        if edit.edited_at > since
        and not (
            edit.node_created_at is not None
            and edit.node_removed_at is not None
            and edit.node_created_at > latest_check
        )
    ]


def edits_to_diff_summary(edits: Iterable[BranchEdit], branch_name: str, schema_branch: SchemaBranch) -> list[NodeDiff]:
    """Express edits as diff summary entries, with every edited field marked updated.

    A relationship identifier maps to every relationship of the kind that carries it, since an edit on the
    shared vertex does not say which side was meant. Kinds missing from the schema are left out.
    """
    elements_by_node: dict[tuple[str, str], dict[str, str]] = {}
    for edit in edits:
        if not schema_branch.has(name=edit.kind):
            continue
        elements = elements_by_node.setdefault((edit.node_id, edit.kind), {})
        if not edit.is_relationship:
            elements[edit.field_name] = DiffElementType.ATTRIBUTE.name
            continue
        node_schema = schema_branch.get(name=edit.kind, duplicate=False)
        for relationship in node_schema.relationships:
            if relationship.get_identifier() == edit.field_name:
                elements[relationship.name] = (
                    DiffElementType.RELATIONSHIP_ONE.name
                    if relationship.cardinality == RelationshipCardinality.ONE
                    else DiffElementType.RELATIONSHIP_MANY.name
                )

    return [
        NodeDiff(
            branch=branch_name,
            kind=kind,
            id=node_id,
            action=DiffAction.UPDATED.name,
            display_label="",
            elements=[
                NodeDiffElement(
                    name=name,
                    element_type=element_type,
                    action=DiffAction.UPDATED.name,
                    summary=NodeDiffSummary(added=0, updated=1, removed=0),
                )
                for name, element_type in sorted(elements.items())
            ],
        )
        for (node_id, kind), elements in sorted(elements_by_node.items())
        if elements
    ]
