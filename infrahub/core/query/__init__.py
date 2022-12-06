from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from enum import Enum
from typing import Generator, List, Optional, Union, TypeVar, TYPE_CHECKING

from neo4j.graph import Node, Relationship

import infrahub.config as config
from infrahub.core.constants import PermissionLevel
from infrahub.database import (
    execute_read_query_async,
    execute_write_query_async,
)
from infrahub.exceptions import QueryError
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from neo4j import AsyncSession
    from infrahub.core.branch import Branch

SelfQuery = TypeVar("SelfQuery", bound="Query")


class QueryType(Enum):
    READ = "read"
    WRITE = "write"


class QueryResult:
    def __init__(self, data, labels):
        self.data = data
        self.labels = labels
        self.branch_score = 0
        self.time_score = 0
        self.permission_score = PermissionLevel.DEFAULT
        self.has_deleted_rels = False

        self.calculate_branch_score()
        self.calculate_time_score()
        self.check_rels_status()

    def calculate_branch_score(self):
        """The branch score is a simple way to order and classify multiple responses for the same branch.
        If the branch name is not the default branch it will get a higher score
        """
        self.branch_score = 0

        for rel in self.get_rels():
            branch_name = rel.get("branch", None)

            if not branch_name:
                continue

            if branch_name == config.SETTINGS.main.default_branch:
                self.branch_score += 1
            else:
                self.branch_score += 2

    def calculate_time_score(self):
        """The time score look into the to and from time all relationships
        if the 'to' field is not defined
        """
        self.time_score = 0

        for rel in self.get_rels():
            branch_name = rel.get("branch", None)

            if not branch_name:
                continue

            # from_time =  rel.get("from", None)
            to_time = rel.get("to", None)

            if to_time:
                self.time_score += 2
            else:
                self.time_score += 1

    def check_rels_status(self):
        """Check if some relationships have the status deleted and update the flag `has_deleted_rels`"""
        for rel in self.get_rels():
            if rel.get("status", None) == "deleted":
                self.has_deleted_rels = True
                return

    def get(self, label: str) -> Union[Node, Relationship]:

        if label not in self.labels:
            raise ValueError(f"{label} is not a valid value for this query, must be one of {self.labels}")

        return_id = self.labels.index(label)

        return self.data[return_id]

    def get_rels(self) -> Generator[Relationship, None, None]:
        """Return all relationships."""

        for item in self.data:
            if hasattr(item, "nodes"):
                yield item

    def get_nodes(self) -> Generator[Node, None, None]:
        """Return all nodes."""
        for item in self.data:
            if hasattr(item, "labels"):
                yield item

    def __iter__(self):
        for item in self.data:
            yield item


class Query(ABC):

    name: str = "base-query"
    type: QueryType = QueryType.READ

    raise_error_if_empty: bool = False
    insert_return: bool = True

    order_by: Optional[List[str]] = None

    def __init__(self, branch: Branch = None, at: Union[Timestamp, str] = None, limit: int = None, *args, **kwargs):

        if branch:
            self.branch = branch

        if not hasattr(self, "at"):
            self.at = None

        if not self.at:
            self.at = Timestamp(at)

        self.limit = limit

        # Initialize internal variables
        self.params: dict = {}
        self.query_lines: List[str] = []
        self.return_labels: List[str] = []
        self.results: List[QueryResult] = None

        self.has_been_executed: bool = False
        self.has_errors: bool = False

    @classmethod
    async def init(
        cls,
        session: AsyncSession,
        branch: Branch = None,
        at: Union[Timestamp, str] = None,
        limit: int = None,
        *args,
        **kwargs,
    ):

        query = cls(branch=branch, at=at, limit=limit, *args, **kwargs)

        await query.query_init(session=session, *args, **kwargs)

        return query

    @abstractmethod
    async def query_init(self, session: AsyncSession, *args, **kwargs):
        raise NotImplementedError

    def add_to_query(self, query: str):
        self.query_lines.extend([line.strip() for line in query.split("\n") if line.strip()])

    def get_query(self, var: bool = False) -> str:
        # Make a local copy of the _query_lines

        tmp_query_lines = self.query_lines.copy()

        if self.insert_return:
            tmp_query_lines.append("RETURN " + ",".join(self.return_labels))

        if self.order_by:
            tmp_query_lines.append("ORDER BY " + ",".join(self.order_by))

        if self.limit:
            tmp_query_lines.append(f"LIMIT {self.limit}")

        query_str = "\n".join(tmp_query_lines)

        if not var:
            return query_str

        for key, value in self.params.items():
            if isinstance(value, (int, list)):
                query_str = query_str.replace(f"${key}", str(value))
            else:
                query_str = query_str.replace(f"${key}", f'"{value}"')

        return query_str

    async def execute(self, session: AsyncSession = None) -> SelfQuery:

        # Ensure all mandatory params have been provided
        # Ensure at least 1 return obj has been defined

        if config.SETTINGS.main.print_query_details:
            self.print(include_var=True)

        if self.type == QueryType.READ:
            results = await execute_read_query_async(query=self.get_query(), params=self.params, session=session)
        elif self.type == QueryType.WRITE:
            results = await execute_write_query_async(query=self.get_query(), params=self.params, session=session)
        else:
            raise ValueError(f"unknown value for {self.type}")

        if not results and self.raise_error_if_empty:
            raise QueryError(self.get_query(), self.params)

        self.results = [QueryResult(data=result, labels=self.return_labels) for result in results]
        self.has_been_executed = True

        return self

    def process_results(self, results) -> List[QueryResult]:
        return results

    def get_raw_results(self) -> List[QueryResult]:
        return self.results

    def get_result(self) -> QueryResult:
        """Return a single Result."""

        if not self.num_of_results:
            return None

        if self.num_of_results == 1:
            return self.results[0]

        return next(self.get_results())

    def get_results(self) -> Generator[QueryResult, None, None]:
        """Get all the results sorted by score."""

        score_idx = {}
        for idx, result in enumerate(self.results):
            score_idx[idx] = result.branch_score

        for idx, score in sorted(score_idx.items(), key=lambda x: x[1], reverse=True):
            yield self.results[idx]

    def get_results_group_by(self, *args) -> Generator[QueryResult, None, None]:
        """Return results group by the labels and attributes provided and filtered by scored.

        Examples:
            get_results_group_by(("n", "uuid"), ("a", "name")):
        """

        attrs_info = defaultdict(list)

        # Extract all attrname and relationships on all branches
        for idx, result in enumerate(self.results):
            identifier = []
            for label, attribute in args:
                node = result.get(label)
                if hasattr(node, attribute):
                    identifier.append(getattr(node, attribute))
                else:
                    identifier.append(node.get(attribute, None))

            info = {
                "idx": idx,
                "branch_score": result.branch_score,
                "time_score": result.time_score,
                "deleted": result.has_deleted_rels,
            }
            attrs_info[tuple(identifier)].append(info)

        for values in attrs_info.values():
            attr_info = sorted(values, key=lambda i: (i["branch_score"], i["time_score"], i["deleted"]), reverse=True)[
                0
            ]
            if attr_info["deleted"]:
                continue

            yield self.results[attr_info["idx"]]

    @property
    def num_of_results(self) -> int:
        if not self.has_been_executed:
            return None

        return len([result for result in self.results if not result.has_deleted_rels])

    def print_table(self):

        from rich import print as rprint
        from rich.console import Console
        from rich.table import Table

        console = Console()

        table = Table(title=f"Query {self.name} : params: {self.params}")

        for label in self.return_labels:

            # table.add_column("Name", justify="right", style="cyan", no_wrap=True)
            table.add_column(label)

        for result in self.results:
            table.add_row(*[str(result.get(label)) for label in self.return_labels])

        console.print(table)

    def print(self, include_var=False):

        # from rich import print
        from rich import print as rprint

        print("-------------------------------------------------------")
        print(self.get_query(include_var=include_var))
        if self.params:
            rprint(self.params)
