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
        # The result can never exceed one row per branch and attribute, so this bound is exact. It
        # has to be non-zero: execute() reads a falsy limit as "unpaginated" and pages the read.
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
        // ----------
        // One HAS_ATTRIBUTE edge exists per branch that touched the attribute, so the match above
        // yields one row per edge. Deduplicating here also keeps the uuid seek and the attribute
        // expansion above the branch loop, so they run once instead of once per branch.
        // ----------
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
