from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from rich import print as rprint
from rich.console import Console
from rich.table import Table

from infrahub.core import registry
from infrahub.core.branch.models import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.migrations.query.node_duplicate import NodeDuplicateQuery, SchemaNodeInfo
from infrahub.core.query import Query, QueryType
from infrahub.core.schema import SchemaRoot, internal_schema
from infrahub.core.schema.manager import SchemaManager
from infrahub.log import get_logger

from ..constants import FAILED_BADGE, SUCCESS_BADGE

if TYPE_CHECKING:
    from infrahub.core.schema.node_schema import NodeSchema
    from infrahub.database import InfrahubDatabase

log = get_logger()


@dataclass
class KindLabelCount:
    kind: str
    labels: frozenset[str]
    num_nodes: int


@dataclass
class KindLabelCountCorrected(KindLabelCount):
    node_schema: NodeSchema


class GetAllKindsAndLabels(Query):
    name = "get_all_kinds_and_labels"
    type = QueryType.READ
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params["branch_name"] = self.branch.name
        self.params["branched_from"] = self.branch.get_branched_from()
        query = """
MATCH (n:Node)-[r:IS_PART_OF {branch: $branch_name}]->(:Root)
WHERE r.from >= $branched_from
AND r.to IS NULL
AND r.status = "active"
RETURN DISTINCT n.kind AS kind, labels(n) AS labels, count(*) AS num_nodes
ORDER BY kind ASC
        """
        self.return_labels = ["kind", "labels", "num_nodes"]
        self.add_to_query(query)

    def get_kind_label_counts(self) -> list[KindLabelCount]:
        kind_label_counts: list[KindLabelCount] = []
        for result in self.results:
            kind = result.get_as_type(label="kind", return_type=str)
            num_nodes = result.get_as_type(label="num_nodes", return_type=int)
            labels: list[str] = result.get_as_type(label="labels", return_type=list)
            # we can ignore the Node label and the label that matches the kind
            cleaned_labels = frozenset(str(lbl) for lbl in labels if lbl not in ["Node", "CoreNode", kind])
            kind_label_counts.append(KindLabelCount(kind=kind, labels=cleaned_labels, num_nodes=num_nodes))
        return kind_label_counts


def display_kind_label_counts(kind_label_counts_by_branch: dict[str, list[KindLabelCountCorrected]]) -> None:
    console = Console()

    table = Table(title="Incorrect Inheritance Nodes")

    table.add_column("Branch")
    table.add_column("Kind")
    table.add_column("Incorrect Labels")
    table.add_column("Num Nodes")

    for branch_name, kind_label_counts in kind_label_counts_by_branch.items():
        for kind_label_count in kind_label_counts:
            table.add_row(
                branch_name, kind_label_count.kind, str(list(kind_label_count.labels)), str(kind_label_count.num_nodes)
            )

    console.print(table)


async def check_inheritance(db: InfrahubDatabase, fix: bool = False) -> None:
    schema_manager = SchemaManager()
    registry.schema = schema_manager
    schema = SchemaRoot(**internal_schema)
    schema_manager.register_schema(schema=schema)
    branches_by_name = {b.name: b for b in await Branch.get_list(db=db)}
    kind_label_counts_by_branch: dict[str, list[KindLabelCountCorrected]] = defaultdict(list)
    for branch in branches_by_name.values():
        if not branch.is_default:
            continue

        rprint(f"Checking branch: {branch.name}", end="...")
        # get the kind and labels for every node on the database
        kind_label_query = await GetAllKindsAndLabels.init(db=db, branch=branch)
        await kind_label_query.execute(db=db)
        kind_label_counts = kind_label_query.get_kind_label_counts()

        if branch.is_global:
            schema_branch = await schema_manager.load_schema_from_db(db=db, branch=registry.default_branch)
        else:
            schema_branch = await schema_manager.load_schema_from_db(db=db, branch=branch)

        for kind_label_count in kind_label_counts:
            node_schema = schema_branch.get_node(name=kind_label_count.kind, duplicate=False)
            correct_labels = frozenset(node_schema.inherit_from)
            if kind_label_count.labels == correct_labels:
                continue

            kind_label_counts_by_branch[branch.name].append(
                KindLabelCountCorrected(
                    kind=kind_label_count.kind,
                    labels=kind_label_count.labels,
                    num_nodes=kind_label_count.num_nodes,
                    node_schema=node_schema,
                )
            )
        rprint("done")

    if not kind_label_counts_by_branch:
        rprint(f"{SUCCESS_BADGE} All nodes have the correct inheritance")
        return

    display_kind_label_counts(kind_label_counts_by_branch)

    if not fix:
        rprint(f"{FAILED_BADGE} Use the --fix flag to fix the inheritance of any invalid nodes")
        return

    for branch_name, kind_label_counts_corrected in kind_label_counts_by_branch.items():
        for kind_label_count in kind_label_counts_corrected:
            rprint(f"Fixing kind {kind_label_count.kind} on branch {branch_name}", end="...")
            node_schema = kind_label_count.node_schema
            migration_query = await NodeDuplicateQuery.init(
                db=db,
                branch=branches_by_name[branch_name],
                previous_node=SchemaNodeInfo(
                    name=node_schema.name,
                    namespace=node_schema.namespace,
                    branch_support=node_schema.branch.value,
                    labels=list(kind_label_count.labels) + [kind_label_count.kind, InfrahubKind.NODE],
                    kind=kind_label_count.kind,
                ),
                new_node=SchemaNodeInfo(
                    name=node_schema.name,
                    namespace=node_schema.namespace,
                    branch_support=node_schema.branch.value,
                    labels=list(node_schema.inherit_from) + [kind_label_count.kind, InfrahubKind.NODE],
                    kind=kind_label_count.kind,
                ),
            )
            await migration_query.execute(db=db)
            rprint("done")

    rprint(f"{SUCCESS_BADGE} All nodes have the correct inheritance")
