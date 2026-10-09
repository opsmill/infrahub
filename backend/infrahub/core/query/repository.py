from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.constants import NULL_VALUE
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from collections.abc import Generator

    from infrahub.core.branch.models import Branch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class BranchReadWindow:
    """The branches an edge may sit on, and the time they are read at."""

    branch_names: tuple[str, ...]
    time: str


@dataclass(frozen=True)
class BranchScope:
    """Every window one Infrahub branch reads through, and the name its rows carry."""

    branch_name: str
    windows: tuple[BranchReadWindow, ...]

    @classmethod
    def from_branch(cls, branch: Branch, at: Timestamp) -> BranchScope:
        """Transcribe a branch's read windows, which is where the fork-point rule already lives."""
        return cls(
            branch_name=branch.name,
            windows=tuple(
                BranchReadWindow(branch_names=tuple(sorted(branch_names)), time=time)
                for branch_names, time in branch.get_branches_and_times_to_query_global(at=at).items()
            ),
        )


@dataclass(frozen=True)
class RepositoryBranchValue:
    """One repository attribute as one Infrahub branch resolves it."""

    branch_name: str
    attribute_name: str
    value: str | None
    source_branch: str | None
    """The branch whose edge supplied the value, or None when no edge did."""


class RepositoryBranchValuesQuery(Query):
    """Resolve attributes of one repository across many Infrahub branches in a single statement.

    Repository kinds are branch-agnostic, so the row set is driven by the branch list rather than by
    the node's own edges, and an isolated branch that never wrote the attribute resolves the value it
    inherits from its origin branch at the fork point.
    """

    name = "repository_branch_values"
    type = QueryType.READ
    # The row bound below is exact rather than a page, so a literal LIMIT could only ever truncate
    # an unordered result.
    insert_limit = False

    def __init__(
        self,
        repository_id: str,
        branch_scopes: list[BranchScope],
        attribute_names: set[str],
        **kwargs: Any,
    ) -> None:
        """Build the query.

        Raises:
            ValueError: If `limit` or `offset` is given, which the read cannot honour, or if two
                scopes name the same branch, which would emit that branch's rows twice.

        """
        unsupported = sorted(argument for argument in ("limit", "offset") if kwargs.get(argument) is not None)
        if unsupported:
            raise ValueError(f"{', '.join(unsupported)} not supported: the read returns every matching row")

        counts = Counter(scope.branch_name for scope in branch_scopes)
        duplicates = sorted(branch_name for branch_name, count in counts.items() if count > 1)
        if duplicates:
            raise ValueError(f"branch_scopes names {', '.join(duplicates)} more than once")

        self.repository_id = repository_id
        self.branch_scopes = branch_scopes
        self.attribute_names = sorted(attribute_names)
        super().__init__(**kwargs)
        # Never zero, because a falsy limit is read as "unpaginated" and pages the read.
        self.limit = max(len(self.branch_scopes) * len(self.attribute_names), 1)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "repository_id": self.repository_id,
            "attribute_names": self.attribute_names,
            "branch_scopes": [
                {
                    "branch_name": scope.branch_name,
                    "windows": [
                        {"branch_names": list(window.branch_names), "time": window.time} for window in scope.windows
                    ],
                }
                for scope in self.branch_scopes
            ],
        }

        query = """
        MATCH (repository:Node { uuid: $repository_id })-[:HAS_ATTRIBUTE]->(attr:Attribute)
        WHERE attr.name IN $attribute_names
        // Deduplicating keeps the uuid seek and the attribute expansion above the branch loop, so
        // they run once instead of once per branch.
        WITH DISTINCT repository, attr
        UNWIND $branch_scopes AS scope
        CALL (repository, attr, scope) {
            MATCH (repository)-[r:HAS_ATTRIBUTE]->(attr)
            WHERE any(
                window IN scope.windows
                WHERE r.branch IN window.branch_names
                    AND r.from <= window.time
                    AND (r.to IS NULL OR r.to > window.time)
            )
            RETURN r
            ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
            LIMIT 1
        }
        WITH repository, attr, scope, r
        WHERE r.status = "active"
        CALL (attr, scope) {
            MATCH (attr)-[r_value:HAS_VALUE]->(attr_value:AttributeValue)
            WHERE any(
                window IN scope.windows
                WHERE r_value.branch IN window.branch_names
                    AND r_value.from <= window.time
                    AND (r_value.to IS NULL OR r_value.to > window.time)
            )
            RETURN r_value, attr_value
            ORDER BY r_value.branch_level DESC, r_value.from DESC, r_value.status ASC
            LIMIT 1
        }
        WITH scope.branch_name AS branch_name, attr.name AS attribute_name, r_value, attr_value
        WHERE r_value.status = "active"
        """
        self.add_to_query(query=query)
        self.return_labels = [
            "branch_name",
            "attribute_name",
            "attr_value.value AS resolved_value",
            "r_value.branch AS value_branch",
        ]

    def get_data(self) -> Generator[RepositoryBranchValue, None, None]:
        """Yield one row per branch and attribute, with a null value where no edge resolved."""
        resolved: dict[tuple[str, str], RepositoryBranchValue] = {}
        for result in self.get_results():
            branch_name = result.get_as_type(label="branch_name", return_type=str)
            attribute_name = result.get_as_type(label="attribute_name", return_type=str)
            value = result.get_as_optional_type(label="resolved_value", return_type=str)
            resolved[branch_name, attribute_name] = RepositoryBranchValue(
                branch_name=branch_name,
                attribute_name=attribute_name,
                value=None if value == NULL_VALUE else value,
                source_branch=result.get_as_optional_type(label="value_branch", return_type=str),
            )

        for scope in self.branch_scopes:
            for attribute_name in self.attribute_names:
                yield resolved.get(
                    (scope.branch_name, attribute_name),
                    RepositoryBranchValue(
                        branch_name=scope.branch_name,
                        attribute_name=attribute_name,
                        value=None,
                        source_branch=None,
                    ),
                )


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
    """Resolve repository attribute values on many branches in one statement.

    The read is unpageable: it resolves every requested repository, branch and attribute in one
    batch, so it accepts neither `limit` nor `offset`.
    """

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
        """Build the query.

        Raises:
            ValueError: If `limit` or `offset` is given, which the read cannot honour.

        """
        # The unset pair arrives as None rather than absent, so only a non-None value counts.
        unsupported = sorted(argument for argument in ("limit", "offset") if kwargs.get(argument) is not None)
        if unsupported:
            raise ValueError(f"{', '.join(unsupported)} not supported: the read returns every matching row")
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
MATCH (n:Node) WHERE n.uuid IN $repository_ids
MATCH (n)-[:HAS_ATTRIBUTE]->(a:Attribute)
WHERE a.name IN $attribute_names
// ----------
// One HAS_ATTRIBUTE edge exists per branch that touched the attribute, so the match above yields
// one row per edge; the election below has to run once per (node, attribute, branch) instead.
// Deduplicating before the branch list multiplies the rows also keeps this match off the branch
// loop, so the uuid lookup and the attribute expansion run once instead of once per branch.
// ----------
WITH DISTINCT n, a
UNWIND $branch_names AS branch_name
MATCH (br:Branch {name: branch_name})
// ----------
// A branch reads the default branch as of its fork point. The fork point only narrows a window
// that extends past it: for a time before the branch existed the requested time is already the
// tighter bound, and moving forward to the fork would expose default-branch writes made after the
// time asked for.
// ----------
WITH n, a, branch_name,
     CASE WHEN br.branched_from < $at THEN br.branched_from ELSE $at END AS default_window
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
