"""A schema migration query given node IDs finds its nodes through the node ID index, and scans its kinds without.

Each case explains the full query twice on the data set: with a few node IDs, where the plan must seek the
`Node(uuid)` index for the selected node, and without IDs, where the plan must not use that index and must read
the kinds in at most one scan rather than one scan per kind.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import BranchSupportType
from infrahub.core.migrations.query.attribute_add import AttributeAddQuery
from infrahub.core.migrations.query.attribute_remove import AttributeRemoveQuery
from infrahub.core.migrations.query.attribute_rename import AttributeRenameQuery
from infrahub.core.migrations.query.node_duplicate import NodeDuplicateQuery, SchemaNodeInfo
from infrahub.core.migrations.query.selection import MigrationSelectionQuery
from infrahub.core.migrations.schema.attribute_kind_update import (
    AttributeKindUpdateMigration,
    AttributeKindUpdateMigrationQuery,
)
from infrahub.core.migrations.schema.attribute_name_update import (
    AttributeNameUpdateMigration,
    AttributeNameUpdateMigrationQuery01,
)
from infrahub.core.migrations.schema.attribute_supports_generated_schema import (
    AttributeSupportsGeneratedSchemaMigration,
    ProfilesAttributeAddMigrationQuery,
    ProfilesAttributeRemoveMigrationQuery,
    TemplatesAttributeAddMigrationQuery,
    TemplatesAttributeRemoveMigrationQuery,
)
from infrahub.core.migrations.schema.node_attribute_add import (
    NodeAttributeAddMigration,
    NodeAttributeAddMigrationQuery01,
)
from infrahub.core.migrations.schema.node_attribute_remove import (
    NodeAttributeRemoveMigration,
    NodeAttributeRemoveMigrationQuery01,
)
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigrationQuery01
from infrahub.core.migrations.schema.node_relationship_remove import NodeRelationshipRemoveMigrationQuery
from infrahub.core.migrations.schema.node_remove import (
    NodeRemoveMigrationBaseQuery,
    NodeRemoveMigrationQueryIn,
    NodeRemoveMigrationQueryOut,
)
from infrahub.core.schema import AttributeSchema
from tests.component.core.migrations.schema.selection_dataset import (
    WIDGET_KIND,
    SelectionDataset,
    build_attribute_add_migration,
    build_attribute_migration,
    build_node_kind_update_migration,
    build_node_remove_migration,
    build_relationship_remove_params,
    load_selection_dataset,
    population,
)
from tests.helpers.query_plan import plan_operators

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

InitKwargsBuilder = Callable[["InfrahubDatabase", "Branch"], dict[str, Any]]

SCOPED_NODE_NAMES = ["w1", "w3", "pw1"]

WIDGET_POPULATION_LABELS = "SelWidget|ProfileSelWidget|TemplateSelWidget"

BUILT_ONLY_THROUGH_SUBCLASSES: set[type[MigrationSelectionQuery]] = {
    AttributeRemoveQuery,
    AttributeRenameQuery,
    NodeRemoveMigrationBaseQuery,
}
"""Base classes that production code never builds itself, so their selection is explained through their subclasses.

Every other subclass of the selection query, found recursively, is concrete and needs a plan case.
"""


@dataclass
class PlanCase:
    name: str
    query_class: type[MigrationSelectionQuery]
    init_kwargs: InitKwargsBuilder
    """Builds the keyword arguments of the query, except the node IDs, the way production code builds them."""
    variable: str
    """The variable the selection binds to the migrated nodes."""
    unscoped_kind_scan: str | None
    """The one operator that scans the kinds without IDs, or `None` when the planner starts from another index."""


def _size_attribute() -> AttributeSchema:
    return AttributeSchema(name="size", kind="Text", optional=True, branch=BranchSupportType.AWARE)


def _attribute_add(db: InfrahubDatabase, branch: Branch) -> dict[str, Any]:
    return {
        "node_kinds": population(WIDGET_KIND),
        "attribute_name": "size",
        "attribute_kind": "Text",
        "branch_support": BranchSupportType.AWARE.value,
    }


def _node_attribute_add(db: InfrahubDatabase, branch: Branch) -> dict[str, Any]:
    return {
        "migration": build_attribute_add_migration(NodeAttributeAddMigration, branch, WIDGET_KIND, _size_attribute())
    }


def _generated_schema(db: InfrahubDatabase, branch: Branch) -> dict[str, Any]:
    return {
        "migration": build_attribute_migration(AttributeSupportsGeneratedSchemaMigration, branch, WIDGET_KIND, "color")
    }


def _node_attribute_remove(db: InfrahubDatabase, branch: Branch) -> dict[str, Any]:
    return {"migration": build_attribute_migration(NodeAttributeRemoveMigration, branch, WIDGET_KIND, "color")}


def _attribute_rename(db: InfrahubDatabase, branch: Branch) -> dict[str, Any]:
    return {
        "migration": build_attribute_migration(
            AttributeNameUpdateMigration, branch, WIDGET_KIND, "color", name="colour"
        )
    }


def _attribute_kind_update(db: InfrahubDatabase, branch: Branch) -> dict[str, Any]:
    return {
        "migration": build_attribute_migration(
            AttributeKindUpdateMigration, branch, WIDGET_KIND, "color", kind="TextArea"
        )
    }


def _node_kind_update(db: InfrahubDatabase, branch: Branch) -> dict[str, Any]:
    return {"migration": build_node_kind_update_migration(branch, WIDGET_KIND, namespace="Selx")}


def _node_duplicate(db: InfrahubDatabase, branch: Branch) -> dict[str, Any]:
    return {
        "kind_updates_map": {
            WIDGET_KIND: SchemaNodeInfo(
                name="Widget",
                namespace="Sel",
                branch_support=BranchSupportType.AWARE.value,
                labels=[WIDGET_KIND, "Node"],
                kind=WIDGET_KIND,
            )
        }
    }


def _node_remove(db: InfrahubDatabase, branch: Branch) -> dict[str, Any]:
    return {"migration": build_node_remove_migration(branch, WIDGET_KIND)}


def _relationship_remove(db: InfrahubDatabase, branch: Branch) -> dict[str, Any]:
    migration, query_params = build_relationship_remove_params(db, branch, WIDGET_KIND, "gadget")
    return {"migration": migration, "query_params": query_params}


PLAN_CASES: list[PlanCase] = [
    PlanCase(
        name="AttributeAddQuery",
        query_class=AttributeAddQuery,
        init_kwargs=_attribute_add,
        variable="n",
        unscoped_kind_scan=f"UnionNodeByLabelsScan@neo4j: n:{WIDGET_POPULATION_LABELS}",
    ),
    PlanCase(
        name="NodeAttributeAddMigrationQuery01",
        query_class=NodeAttributeAddMigrationQuery01,
        init_kwargs=_node_attribute_add,
        variable="n",
        unscoped_kind_scan=f"UnionNodeByLabelsScan@neo4j: n:{WIDGET_POPULATION_LABELS}",
    ),
    PlanCase(
        name="ProfilesAttributeAddMigrationQuery",
        query_class=ProfilesAttributeAddMigrationQuery,
        init_kwargs=_generated_schema,
        variable="n",
        unscoped_kind_scan="NodeByLabelScan@neo4j: n:ProfileSelWidget",
    ),
    PlanCase(
        name="TemplatesAttributeAddMigrationQuery",
        query_class=TemplatesAttributeAddMigrationQuery,
        init_kwargs=_generated_schema,
        variable="n",
        unscoped_kind_scan="NodeByLabelScan@neo4j: n:TemplateSelWidget",
    ),
    PlanCase(
        name="NodeAttributeRemoveMigrationQuery01",
        query_class=NodeAttributeRemoveMigrationQuery01,
        init_kwargs=_node_attribute_remove,
        variable="node",
        unscoped_kind_scan=f"UnionNodeByLabelsScan@neo4j: node:{WIDGET_POPULATION_LABELS}",
    ),
    PlanCase(
        name="ProfilesAttributeRemoveMigrationQuery",
        query_class=ProfilesAttributeRemoveMigrationQuery,
        init_kwargs=_generated_schema,
        variable="node",
        unscoped_kind_scan="NodeByLabelScan@neo4j: node:ProfileSelWidget",
    ),
    PlanCase(
        name="TemplatesAttributeRemoveMigrationQuery",
        query_class=TemplatesAttributeRemoveMigrationQuery,
        init_kwargs=_generated_schema,
        variable="node",
        unscoped_kind_scan="NodeByLabelScan@neo4j: node:TemplateSelWidget",
    ),
    PlanCase(
        name="AttributeNameUpdateMigrationQuery01",
        query_class=AttributeNameUpdateMigrationQuery01,
        init_kwargs=_attribute_rename,
        variable="node",
        unscoped_kind_scan=f"UnionNodeByLabelsScan@neo4j: node:{WIDGET_POPULATION_LABELS}",
    ),
    PlanCase(
        # Without IDs the node and its attribute are one pattern, which the planner starts from the attribute name.
        name="AttributeKindUpdateMigrationQuery",
        query_class=AttributeKindUpdateMigrationQuery,
        init_kwargs=_attribute_kind_update,
        variable="n",
        unscoped_kind_scan=None,
    ),
    PlanCase(
        name="NodeKindUpdateMigrationQuery01",
        query_class=NodeKindUpdateMigrationQuery01,
        init_kwargs=_node_kind_update,
        variable="node",
        unscoped_kind_scan=f"UnionNodeByLabelsScan@neo4j: node:{WIDGET_POPULATION_LABELS}",
    ),
    PlanCase(
        name="NodeDuplicateQuery",
        query_class=NodeDuplicateQuery,
        init_kwargs=_node_duplicate,
        variable="node",
        unscoped_kind_scan="NodeByLabelScan@neo4j: node:SelWidget",
    ),
    PlanCase(
        name="NodeRemoveMigrationQueryIn",
        query_class=NodeRemoveMigrationQueryIn,
        init_kwargs=_node_remove,
        variable="node",
        unscoped_kind_scan="NodeByLabelScan@neo4j: node:SelWidget",
    ),
    PlanCase(
        name="NodeRemoveMigrationQueryOut",
        query_class=NodeRemoveMigrationQueryOut,
        init_kwargs=_node_remove,
        variable="node",
        unscoped_kind_scan="NodeByLabelScan@neo4j: node:SelWidget",
    ),
    PlanCase(
        name="NodeRelationshipRemoveMigrationQuery",
        query_class=NodeRelationshipRemoveMigrationQuery,
        init_kwargs=_relationship_remove,
        variable="node",
        unscoped_kind_scan=f"UnionNodeByLabelsScan@neo4j: node:{WIDGET_POPULATION_LABELS}",
    ),
]


def _all_subclasses(cls: type) -> set[type]:
    subclasses: set[type] = set()
    for subclass in cls.__subclasses__():
        subclasses.add(subclass)
        subclasses |= _all_subclasses(subclass)
    return subclasses


def _kind_scans(operators: list[str], variable: str) -> list[str]:
    """Return the operators that find the nodes bound to `variable` by scanning one or more labels."""
    scans = []
    for operator in operators:
        operator_type, _, details = operator.partition(": ")
        if operator_type.split("@")[0].endswith(("ByLabelScan", "ByLabelsScan")) and details.startswith(f"{variable}:"):
            scans.append(operator)
    return scans


async def _explain(db: InfrahubDatabase, query: MigrationSelectionQuery) -> list[str]:
    rendered = query.render()
    _, metadata = await db.execute_query_with_metadata(
        query="EXPLAIN\n" + rendered.text, params=rendered.params, name=f"explain_{query.name}"
    )
    return plan_operators(metadata["plan"])


def test_every_selection_query_has_a_plan_case() -> None:
    covered = {case.query_class for case in PLAN_CASES}
    selection_queries = _all_subclasses(MigrationSelectionQuery)

    assert (
        sorted(
            cls.__name__ for cls in selection_queries if cls not in covered and cls not in BUILT_ONLY_THROUGH_SUBCLASSES
        )
        == []
    )
    assert sorted(base.__name__ for base in BUILT_ONLY_THROUGH_SUBCLASSES if not _all_subclasses(base) & covered) == []


class TestMigrationQueryPlan:
    @pytest.fixture(scope="class")
    async def selection_dataset(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, node_group_schema_scope_class: None
    ) -> SelectionDataset:
        return await load_selection_dataset(db=db, default_branch=default_branch_scope_class)

    @pytest.fixture
    def restore_schema_branch(self, default_branch_scope_class: Branch) -> Generator[None, None, None]:
        """Put back the registered schema of the branch, which building a relationship removal replaces."""
        schema_branch = registry.schema.get_schema_branch(name=default_branch_scope_class.name)
        yield
        registry.schema.set_schema_branch(name=default_branch_scope_class.name, schema=schema_branch)

    @pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in PLAN_CASES])
    async def test_scope_seeks_the_node_id_index_and_no_scope_scans_the_kinds(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        selection_dataset: SelectionDataset,
        restore_schema_branch: None,
        case: PlanCase,
    ) -> None:
        branch = default_branch_scope_class
        node_ids = [selection_dataset.nodes[name].id for name in SCOPED_NODE_NAMES]
        init_kwargs = case.init_kwargs(db, branch)

        scoped = await _explain(db, await case.query_class.init(db=db, branch=branch, node_ids=node_ids, **init_kwargs))
        unscoped = await _explain(db, await case.query_class.init(db=db, branch=branch, **init_kwargs))

        node_id_seek = f"NodeIndexSeek@neo4j: RANGE INDEX {case.variable}:Node(uuid) WHERE uuid IN $node_ids"
        assert [operator for operator in scoped if operator.startswith(node_id_seek)] != []
        assert _kind_scans(scoped, case.variable) == []

        assert [operator for operator in unscoped if "Node(uuid)" in operator] == []
        expected_scans = [] if case.unscoped_kind_scan is None else [case.unscoped_kind_scan]
        assert _kind_scans(unscoped, case.variable) == expected_scans
