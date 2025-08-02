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


class GetSchemaWithUpdatedInheritance(Query):
    """
    Get the name, namespace, and branch of any SchemaNodes with _updated_ inheritance
    This query will only return schemas that have had `inherit_from` updated after they were created
    """

    name = "get_schema_with_updated_inheritance"
    type = QueryType.READ
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
// find inherit_from attributes that have been updated
MATCH p = (schema_node:SchemaNode)-[has_attr_e:HAS_ATTRIBUTE {status: "active"}]->(a:Attribute {name: "inherit_from"})
WHERE has_attr_e.to IS NULL
CALL (a) {
  // only get branches on which the value was updated, we can ignore the initial create
  MATCH (a)-[e:HAS_VALUE]->(:AttributeValue)
  ORDER BY e.from ASC
  // tail leaves out the earliest one, which is the initial create
  RETURN tail(collect(e.branch)) AS branches
}
WITH schema_node, a, branches
WHERE size(branches) > 0
UNWIND branches AS branch
WITH DISTINCT schema_node, a, branch

//get branch details
CALL (branch) {
  MATCH (b:Branch {name: branch})
  RETURN b.branched_from AS branched_from, b.hierarchy_level AS branch_level
}

// get the namespace for the schema
CALL (schema_node, a, branch, branched_from, branch_level) {
  MATCH (schema_node)-[e1:HAS_ATTRIBUTE]-(:Attribute {name: "namespace"})-[e2:HAS_VALUE]->(av)
  WHERE (
    e1.branch = branch OR
    (e1.branch_level < branch_level AND e1.from <= branched_from)
  ) AND e1.to IS NULL
  AND e1.status = "active"
  AND (
    e2.branch = branch OR
    (e2.branch_level < branch_level AND e2.from <= branched_from)
  ) AND e2.to IS NULL
  AND e2.status = "active"
  ORDER BY e2.branch_level DESC, e1.branch_level DESC, e2.from DESC, e1.from DESC
  RETURN av.value AS namespace
  LIMIT 1
}

// get the name for the schema
CALL (schema_node, a, branch, branched_from, branch_level) {
  MATCH (schema_node)-[e1:HAS_ATTRIBUTE]-(:Attribute {name: "name"})-[e2:HAS_VALUE]->(av)
  WHERE (
    e1.branch = branch OR
    (e1.branch_level < branch_level AND e1.from <= branched_from)
  ) AND e1.to IS NULL
  AND e1.status = "active"
  AND (
    e2.branch = branch OR
    (e2.branch_level < branch_level AND e2.from <= branched_from)
  ) AND e2.to IS NULL
  AND e2.status = "active"
  ORDER BY e2.branch_level DESC, e1.branch_level DESC, e2.from DESC, e1.from DESC
  RETURN av.value AS name
  LIMIT 1
}
RETURN name, namespace, branch
"""
        self.return_labels = ["name", "namespace", "branch"]
        self.add_to_query(query)

    def get_updated_inheritance_kinds_by_branch(self) -> dict[str, list[str]]:
        kinds_by_branch: dict[str, list[str]] = defaultdict(list)
        for result in self.results:
            name = result.get_as_type(label="name", return_type=str)
            namespace = result.get_as_type(label="namespace", return_type=str)
            branch = result.get_as_type(label="branch", return_type=str)
            kinds_by_branch[branch].append(f"{namespace}{name}")
        return kinds_by_branch


@dataclass
class KindLabelCount:
    kind: str
    labels: frozenset[str]
    num_nodes: int


@dataclass
class KindLabelCountCorrected(KindLabelCount):
    node_schema: NodeSchema


class GetAllKindsAndLabels(Query):
    """
    Get the kind, labels, and number of nodes for the given kinds and branch
    """

    name = "get_all_kinds_and_labels"
    type = QueryType.READ
    insert_return = False

    def __init__(self, kinds: list[str] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.kinds = kinds

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params["branch_name"] = self.branch.name
        self.params["branched_from"] = self.branch.get_branched_from()
        self.params["branch_level"] = self.branch.hierarchy_level
        kinds_str = "Node"
        if self.kinds:
            kinds_str = "|".join(self.kinds)
        query = """
MATCH (n:%(kinds_str)s)-[r:IS_PART_OF]->(:Root)
WHERE (
    r.branch = $branch_name OR
    (r.branch_level < $branch_level AND r.from <= $branched_from)
)
AND r.to IS NULL
AND r.status = "active"
RETURN DISTINCT n.kind AS kind, labels(n) AS labels, count(*) AS num_nodes
ORDER BY kind ASC
        """ % {"kinds_str": kinds_str}
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


async def check_inheritance(db: InfrahubDatabase, fix: bool = False) -> bool:
    """
    Run migrations to update the inheritance of any nodes with incorrect inheritance from a failed migration
    1. Identifies node schemas that have had their inheritance updated after they were created
        a. includes the kind and branch of the inheritance update
    2. Checks nodes of the given kinds on the given branch to verify their inheritance is correct
    3. Displays counts of any kinds with incorrect inheritance on the given branch
    4. If fix is True, runs migrations to update the inheritance of any nodes with incorrect inheritance
        on the correct branch
    """

    updated_inheritance_query = await GetSchemaWithUpdatedInheritance.init(db=db)
    await updated_inheritance_query.execute(db=db)
    updated_inheritance_kinds_by_branch = updated_inheritance_query.get_updated_inheritance_kinds_by_branch()

    if not updated_inheritance_kinds_by_branch:
        rprint(f"{SUCCESS_BADGE} No schemas have had their inheritance updated")
        return True

    schema_manager = SchemaManager()
    registry.schema = schema_manager
    schema = SchemaRoot(**internal_schema)
    schema_manager.register_schema(schema=schema)
    branches_by_name = {b.name: b for b in await Branch.get_list(db=db)}

    kind_label_counts_by_branch: dict[str, list[KindLabelCountCorrected]] = defaultdict(list)
    for branch_name, kinds in updated_inheritance_kinds_by_branch.items():
        rprint(f"Checking branch: {branch_name}", end="...")
        branch = branches_by_name[branch_name]
        schema_branch = await schema_manager.load_schema_from_db(db=db, branch=branch)
        kind_label_query = await GetAllKindsAndLabels.init(db=db, branch=branch, kinds=kinds)
        await kind_label_query.execute(db=db)
        kind_label_counts = kind_label_query.get_kind_label_counts()

        for kind_label_count in kind_label_counts:
            node_schema = schema_branch.get_node(name=kind_label_count.kind, duplicate=False)
            correct_labels = frozenset(node_schema.inherit_from)
            if kind_label_count.labels == correct_labels:
                continue

            kind_label_counts_by_branch[branch_name].append(
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
        return True

    display_kind_label_counts(kind_label_counts_by_branch)

    if not fix:
        rprint(f"{FAILED_BADGE} Use the --fix flag to fix the inheritance of any invalid nodes")
        return False

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

    if registry.default_branch in kind_label_counts_by_branch:
        kinds = [kind_label_count.kind for kind_label_count in kind_label_counts_by_branch[registry.default_branch]]
        rprint(
            "[bold cyan]Note that migrations were run on the default branch for the following schema kinds: "
            f"{', '.join(kinds)}. You should rebase any branches that include/will include changes using "
            "the migrated schemas[/bold cyan]"
        )

    return True
