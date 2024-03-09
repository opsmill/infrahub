from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Generator, List, Optional, Union

from neo4j.graph import Node as Neo4jNode
from neo4j.graph import Relationship as Neo4jRelationship

from infrahub import config
from infrahub.core.constants import PermissionLevel
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import QueryError

if TYPE_CHECKING:
    from typing_extensions import Self

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


def sort_results_by_time(results: List[QueryResult], rel_label: str) -> List[QueryResult]:
    """Sort a list of QueryResult based on the to and from fields on given relationship.

    To sort the results, we are generating an ID per item
        The ID is derived from the timestamp of the last action and we multiply it by 1000
        To differentiate two records that have been updated at the same time
        We are adding more weight (500) to the record for which the last action was to set "from"
         versus a record with "from" and "to" set.
    """

    results_dict = {}

    for result in results:
        from_time = result.get(rel_label).get("from")
        to_time = result.get(rel_label).get("to")

        if not to_time:
            record_id = Timestamp(from_time).to_timestamp() * 1000 + 500
        else:
            record_id = Timestamp(to_time).to_timestamp() * 1000

        results_dict[record_id] = result

    return [value for _, value in sorted(results_dict.items(), reverse=False)]


class QueryElementType(Enum):
    NODE = "node"
    RELATIONSHIP = "relationship"


class QueryRelDirection(Enum):
    BIDIR = "bidirectional"
    INBOUND = "inbound"
    OUTBOUND = "outbound"


@dataclass
class QueryElement:
    type: QueryElementType
    name: Optional[str] = None
    labels: Optional[List[str]] = None
    params: Optional[dict] = None

    def __str__(self):
        main_str = "%s%s%s" % (self.name or "", self.labels_as_str, self.params_as_str)
        if self.type == QueryElementType.NODE:
            return "(%s)" % main_str
        return "[%s]" % main_str

    @property
    def labels_as_str(self) -> str:
        if not self.labels:
            return ""

        return ":" + ":".join(self.labels)

    @property
    def params_as_str(self) -> str:
        if not self.params:
            return ""

        params_list = []
        for key, value in self.params.items():
            if isinstance(value, str) and not value.startswith("$"):
                value_str = f'"{value}"'
            else:
                value_str = value

            params_list.append(f"{key}: {value_str}")

        return " { " + ",".join(params_list) + " }"


@dataclass
class QueryNode(QueryElement):
    type: QueryElementType = QueryElementType.NODE


@dataclass
class QueryRel(QueryElement):
    type: QueryElementType = QueryElementType.RELATIONSHIP
    direction: QueryRelDirection = QueryRelDirection.BIDIR
    length_min: int = 1
    length_max: Optional[int] = None

    def __str__(self):
        lenght_str = ""
        if self.length_max:
            lenght_str = "*%s..%s" % (
                self.length_min,
                self.length_max,
            )

        main_str = "[%s%s%s%s]" % (
            self.name or "",
            self.labels_as_str,
            lenght_str,
            self.params_as_str,
        )

        if self.direction == QueryRelDirection.INBOUND:
            return "<-%s-" % main_str
        if self.direction == QueryRelDirection.OUTBOUND:
            return "-%s->" % main_str

        return "-%s-" % main_str


class QueryType(Enum):
    READ = "read"
    WRITE = "write"


def cleanup_return_labels(labels):
    """Cleanup a list of return labels by checking if there is an alias defined.
    if an alias is defined with `value AS alias` we extract just the alias from the label
    """
    clean_labels = []
    for label in labels:
        idx = label.lower().find(" as ")
        if idx > 0:
            clean_idx = idx + 4
            clean_label = label[clean_idx:]
            clean_labels.append(clean_label.strip())
        else:
            clean_labels.append(label)

    return clean_labels


class QueryResult:
    def __init__(self, data: List[Union[Neo4jNode, Neo4jRelationship, List[Neo4jNode]]], labels: List[str]):
        self.data = data
        self.labels = cleanup_return_labels(labels)
        self.branch_score: int = 0
        self.time_score: int = 0
        self.permission_score = PermissionLevel.DEFAULT
        self.has_deleted_rels: bool = False

        self.calculate_branch_score()
        self.calculate_time_score()
        self.check_rels_status()

    def calculate_branch_score(self):
        """The branch score is a simple way to order and classify multiple responses for the same branch.
        If the branch name is not the default branch it will get a higher score
        """
        self.branch_score = 0

        for rel in self.get_rels():
            branch_level = rel.get("branch_level", None)

            if not branch_level:
                continue

            self.branch_score += branch_level

    def calculate_time_score(self):
        """The time score look into the to and from time all relationships
        if the 'to' field is not defined
        """
        self.time_score = 0

        for rel in self.get_rels():
            branch_name = rel.get("branch", None)

            if not branch_name:
                continue

            to_time = rel.get("to", None)

            if to_time:
                self.time_score += 1
            else:
                self.time_score += 2

    def check_rels_status(self):
        """Check if some relationships have the status deleted and update the flag `has_deleted_rels`"""
        for rel in self.get_rels():
            if rel.get("status", None) == "deleted":
                self.has_deleted_rels = True
                return

    def _get(self, label: str) -> Union[Neo4jNode, Neo4jRelationship, List[Neo4jNode]]:
        if label not in self.labels:
            raise ValueError(f"{label} is not a valid value for this query, must be one of {self.labels}")

        return_id = self.labels.index(label)
        return self.data[return_id]

    def get(self, label: str) -> Union[Neo4jNode, Neo4jRelationship]:
        return self._get(label=label)

    def get_as_str(self, label: str) -> Optional[str]:
        item = self._get(label=label)
        if item:
            return str(item)
        return None

    def get_node_collection(self, label: str) -> List[Neo4jNode]:
        entry = self._get(label=label)
        if isinstance(entry, list):
            return entry
        raise ValueError(f"{label} is not a collection use .get_node() or .get()")

    def get_node(self, label: str) -> Neo4jNode:
        node = self.get(label=label)
        if isinstance(node, Neo4jNode):
            return node
        raise ValueError(f"{label} is not a Node")

    def get_rel(self, label: str) -> Neo4jRelationship:
        rel = self.get(label=label)
        if isinstance(rel, Neo4jRelationship):
            return rel
        raise ValueError(f"{label} is not a Relationship")

    def get_rels(self) -> Generator[Neo4jRelationship, None, None]:
        """Return all relationships."""

        for item in self.data:
            if isinstance(item, Neo4jRelationship):
                yield item

    def get_nodes(self) -> Generator[Neo4jNode, None, None]:
        """Return all nodes."""
        for item in self.data:
            if isinstance(item, Neo4jNode):
                yield item

    def __iter__(self):
        yield from self.data


@dataclass
class QueryStats:
    stats: List[QueryStat] = field(default_factory=list)

    def add(self, data: Optional[Dict[str, Any]]) -> None:
        if data:
            self.stats.append(QueryStat.from_metadata(data))

    def get_counter(self, name: str) -> int:
        cnt = 0
        for stat in self.stats:
            if not hasattr(stat, name):
                raise ValueError(f"Counter {name} is not available")
            cnt += getattr(stat, name)

        return cnt


@dataclass
class QueryStat:
    contains_updates: bool = False
    labels_added: Optional[int] = None
    nodes_created: Optional[int] = None
    properties_set: Optional[int] = None
    relationships_created: Optional[int] = None

    @classmethod
    def from_metadata(cls, data: Dict[str, Any]) -> Self:
        data = {key.replace("-", "_"): value for key, value in data.items()}
        return cls(**data)


class Query(ABC):
    name: str = "base-query"
    type: QueryType = QueryType.READ

    raise_error_if_empty: bool = False
    insert_return: bool = True

    def __init__(
        self,
        branch: Optional[Branch] = None,
        at: Optional[Union[Timestamp, str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order_by: Optional[List[str]] = None,
    ):
        if branch:
            self.branch = branch

        if not hasattr(self, "at"):
            self.at = Timestamp(at)

        if not self.at:
            self.at = Timestamp(at)

        self.limit = limit
        self.offset = offset
        self.order_by = order_by

        # Initialize internal variables
        self.params: dict = {}
        self.query_lines: List[str] = []
        self.return_labels: List[str] = []
        self.results: List[QueryResult] = []

        self.has_been_executed: bool = False
        self.has_errors: bool = False

        self.stats: QueryStats = QueryStats()

    def update_return_labels(self, value: Union[str, List[str]]) -> None:
        if isinstance(value, str) and value not in self.return_labels:
            self.return_labels.append(value)
            return
        if isinstance(value, list):
            for item in value:
                self.update_return_labels(value=item)

    @classmethod
    async def init(
        cls,
        db: InfrahubDatabase,
        branch: Optional[Branch] = None,
        at: Optional[Union[Timestamp, str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        *args,
        **kwargs,
    ) -> Self:
        query = cls(branch=branch, at=at, limit=limit, offset=offset, *args, **kwargs)

        await query.query_init(db=db, **kwargs)

        return query

    @abstractmethod
    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        raise NotImplementedError

    def add_to_query(self, query: Union[str, List[str]]) -> None:
        """Add a new section at the end of the query.

        A string with multiple lines will be broken down into multiple entries in self.query_lines
        Trailing and leading spaces per line will be removed."""

        if isinstance(query, list):
            for item in query:
                self.add_to_query(query=item)
        else:
            self.query_lines.extend([line.strip() for line in query.split("\n") if line.strip()])

    def add_subquery(self, subquery: str, with_clause: Optional[str] = None) -> None:
        self.add_to_query("CALL {")
        self.add_to_query(subquery)
        self.add_to_query("}")
        if with_clause:
            self.add_to_query(f"WITH {with_clause}")

    def get_query(
        self, var: bool = False, inline: bool = False, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> str:
        # Make a local copy of the _query_lines
        limit = limit or self.limit
        offset = offset or self.offset
        tmp_query_lines = self.query_lines.copy()

        if self.insert_return:
            tmp_query_lines.append("RETURN " + ",".join(self.return_labels))

        if self.order_by:
            tmp_query_lines.append("ORDER BY " + ",".join(self.order_by))

        if offset:
            tmp_query_lines.append(f"SKIP {offset}")

        if limit:
            tmp_query_lines.append(f"LIMIT {limit}")

        query_str = "\n".join(tmp_query_lines)

        if var and not inline:
            return "\n" + self.get_params_for_shell() + "\n\n" + query_str
        if var and inline:
            return self.insert_variables_in_query(query=query_str, variables=self.params)

        return query_str

    def get_count_query(self, var: bool = False) -> str:
        tmp_query_lines = self.query_lines.copy()
        tmp_query_lines.append("RETURN count(*) as count")
        query_str = "\n".join(tmp_query_lines)

        if not var:
            return query_str

        return self.insert_variables_in_query(query=query_str, variables=self.params)

    @staticmethod
    def insert_variables_in_query(query: str, variables: dict) -> str:
        """Search for all the variables in a Query string and replace each variable with its value."""

        def prep_value(v):
            if isinstance(v, (int, list)):
                return str(v)
            return f'"{v}"'

        for key, value in variables.items():
            if isinstance(value, dict):
                value_items = [f"{key1}: {prep_value(value1)}" for key1, value1 in value.items()]
                value_str = "{ " + ", ".join(value_items) + " }"
                query = query.replace(f"${key}", value_str)
            else:
                query = query.replace(f"${key}", prep_value(value))

        return query

    def get_params_for_shell(self):
        if config.SETTINGS.database.db_type.value == "memgraph":
            return json.dumps(self.params)

        return self._get_params_for_neo4j_shell()

    def _get_params_for_neo4j_shell(self):
        """Generate string to define some parameters in Neo4j browser interface.
        It's especially useful to later execute a query that includes some variables.

        The params string must be executed on its own window in Neo4j, before executing the query.
        """

        params = []

        for key, value in self.params.items():
            if isinstance(value, (int, list)):
                params.append(f"{key}: {str(value)}")
            else:
                params.append(f'{key}: "{value}"')

        return ":params { " + ", ".join(params) + " }"

    async def execute(self, db: InfrahubDatabase) -> Self:
        # Ensure all mandatory params have been provided
        # Ensure at least 1 return obj has been defined

        if config.SETTINGS.miscellaneous.print_query_details:
            self.print(include_var=True)

        if self.type == QueryType.READ:
            if self.limit or self.offset:
                results = await db.execute_query(query=self.get_query(), params=self.params, name=self.name)
            else:
                results = await self.query_with_size_limit(db=db)

        elif self.type == QueryType.WRITE:
            results, metadata = await db.execute_query_with_metadata(
                query=self.get_query(), params=self.params, name=self.name
            )
            if "stats" in metadata:
                self.stats.add(metadata.get("stats"))
        else:
            raise ValueError(f"unknown value for {self.type}")

        if not results and self.raise_error_if_empty:
            raise QueryError(self.get_query(), self.params)

        self.results = [QueryResult(data=result, labels=self.return_labels) for result in results]
        self.has_been_executed = True

        return self

    async def query_with_size_limit(self, db: InfrahubDatabase):
        query_limit = config.SETTINGS.database.query_size_limit
        offset = 0
        results = []
        remaining = True
        while remaining:
            offset_results, metadata = await db.execute_query_with_metadata(
                query=self.get_query(limit=query_limit, offset=offset),
                params=self.params,
                name=self.name,
            )
            if "stats" in metadata:
                self.stats.add(metadata.get("stats"))
            results.extend(offset_results)
            offset += query_limit

            if len(offset_results) < query_limit:
                remaining = False

        return results

    async def count(self, db: InfrahubDatabase) -> int:
        """Count the number of results matching a READ query.
        OFFSET and LIMIT are automatically excluded when counting.
        """

        if self.type == QueryType.WRITE:
            raise TypeError("Unable to count the number of response on a Write query.")
        if self.type != QueryType.READ:
            raise ValueError(f"unknown value for {self.type}")

        results = await db.execute_query(query=self.get_count_query(), params=self.params, name=f"{self.name}_count")

        if not results and self.raise_error_if_empty:
            raise QueryError(self.get_count_query(), self.params)

        return results[0][0]

    def process_results(self, results) -> List[QueryResult]:
        return results

    def get_raw_results(self) -> List[QueryResult]:
        return self.results

    def get_result(self) -> Union[QueryResult, None]:
        """Return a single Result."""

        if not self.has_been_executed:
            return None

        if self.num_of_results == 1:
            return self.results[0]

        return next(self.get_results())

    def get_results(self) -> Generator[QueryResult, None, None]:
        """Get all the results sorted by score."""

        score_idx = {}
        for idx, result in enumerate(self.results):
            score_idx[idx] = result.branch_score

        for idx, _ in sorted(score_idx.items(), key=lambda x: x[1], reverse=True):
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
            raise ValueError("The query hasn't been executed yet")

        return len([result for result in self.results if not result.has_deleted_rels])

    def print_table(self):
        # pylint: disable=import-outside-toplevel

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
        # pylint: disable=import-outside-toplevel
        from rich import print as rprint

        print("-------------------------------------------------------")
        print(self.get_query(var=include_var))
        if self.params:
            rprint(self.params)
