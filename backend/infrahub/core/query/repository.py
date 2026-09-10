from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.constants import NULL_VALUE
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from collections.abc import Generator

    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class RepositoryBranchAttributeValue:
    """One repository attribute value as it resolves on one branch."""

    repository_id: str
    """UUID of the repository node."""

    branch_name: str
    """Name of the branch the value was resolved for."""

    attribute_name: str
    """Name of the attribute, e.g. `commit`."""

    attribute_id: str
    """UUID of the attribute node."""

    value: str | None
    """Value the winning value edge points at, None when the attribute holds no value."""

    own_value: bool
    """True when the winning value edge lives on `branch_name` itself rather than being inherited."""

    updated_at: str | None
    """Time the winning value edge was created."""


class RepositoryBranchAttributesQuery(Query):
    """Resolve repository attribute values on many branches in one statement."""

    name = "repository-branch-attributes"
    type = QueryType.READ
    insert_return = False
    insert_limit = False

    def __init__(
        self,
        repository_ids: list[str],
        branch_names: list[str],
        attribute_names: list[str],
        default_branch_name: str,
        global_branch_name: str,
        **kwargs: Any,
    ) -> None:
        self.repository_ids = repository_ids
        self.branch_names = branch_names
        self.attribute_names = attribute_names
        self.default_branch_name = default_branch_name
        self.global_branch_name = global_branch_name
        super().__init__(**kwargs)
        # The statement carries no LIMIT of its own; unless this limit covers every row it can
        # produce, the read is paginated and re-run until a batch comes back short.
        self.limit = max(len(repository_ids) * len(branch_names) * len(attribute_names), 1)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "repository_ids": self.repository_ids,
            "branch_names": self.branch_names,
            "attribute_names": self.attribute_names,
            "default_branch_name": self.default_branch_name,
            "global_branch_name": self.global_branch_name,
            "at": self.at.to_string(),
        }

        query = """
UNWIND $branch_names AS branch_name
MATCH (br:Branch {name: branch_name})
// ----------
// An isolated branch reads the default branch as of its fork point; a branch saved before
// isolation became the default reads it at query time, like the standard per-branch read does.
// ----------
WITH branch_name, CASE WHEN br.is_isolated THEN br.branched_from ELSE $at END AS default_window
MATCH (n:Node)-[:HAS_ATTRIBUTE]->(a:Attribute)
WHERE n.uuid IN $repository_ids AND a.name IN $attribute_names
// ----------
// One HAS_ATTRIBUTE edge exists per branch that touched the attribute, so the match above yields
// one row per edge; the election below has to run once per (node, attribute, branch) instead.
// ----------
WITH DISTINCT n, a, branch_name, default_window
CALL (n, a, branch_name, default_window) {
    MATCH (n)-[r:HAS_ATTRIBUTE]->(a)
    WHERE (r.branch IN [branch_name, $global_branch_name] AND r.from <= $at AND r.to IS NULL)
       OR (r.branch IN [branch_name, $global_branch_name] AND r.from <= $at AND r.to > $at)
       OR (branch_name <> $default_branch_name AND r.branch = $default_branch_name
           AND r.from <= default_window AND r.to IS NULL)
       OR (branch_name <> $default_branch_name AND r.branch = $default_branch_name
           AND r.from <= default_window AND r.to > default_window)
    RETURN r
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
WITH n, a, branch_name, default_window, r
WHERE r.status = "active"
CALL (a, branch_name, default_window) {
    MATCH (a)-[r_value:HAS_VALUE]->(av:AttributeValue)
    WHERE (r_value.branch IN [branch_name, $global_branch_name] AND r_value.from <= $at AND r_value.to IS NULL)
       OR (r_value.branch IN [branch_name, $global_branch_name] AND r_value.from <= $at AND r_value.to > $at)
       OR (branch_name <> $default_branch_name AND r_value.branch = $default_branch_name
           AND r_value.from <= default_window AND r_value.to IS NULL)
       OR (branch_name <> $default_branch_name AND r_value.branch = $default_branch_name
           AND r_value.from <= default_window AND r_value.to > default_window)
    RETURN r_value, av
    ORDER BY r_value.branch_level DESC, r_value.from DESC, r_value.status ASC
    LIMIT 1
}
WITH n, a, branch_name, r_value, av
WHERE r_value.status = "active"
RETURN n.uuid AS repository_id, branch_name, a.name AS attribute_name, a.uuid AS attribute_id,
       av.value AS value, r_value.branch AS value_branch, r_value.from AS updated_at
        """
        self.add_to_query(query)
        self.return_labels = [
            "repository_id",
            "branch_name",
            "attribute_name",
            "attribute_id",
            "value",
            "value_branch",
            "updated_at",
        ]

    def get_data(self) -> Generator[RepositoryBranchAttributeValue, None, None]:
        """Yield one resolved value per repository, branch and attribute name that produced a row."""
        for result in self.get_results():
            raw_value = result.get_as_optional_type("value", str)
            branch_name = result.get_as_type("branch_name", str)
            yield RepositoryBranchAttributeValue(
                repository_id=result.get_as_type("repository_id", str),
                branch_name=branch_name,
                attribute_name=result.get_as_type("attribute_name", str),
                attribute_id=result.get_as_type("attribute_id", str),
                value=None if raw_value == NULL_VALUE else raw_value,
                own_value=result.get_as_optional_type("value_branch", str) == branch_name,
                updated_at=result.get_as_optional_type("updated_at", str),
            )
