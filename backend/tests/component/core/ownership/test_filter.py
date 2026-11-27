from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.ownership.constants import (
    MAX_INHERITANCE_DEPTH,
    OWNERS_IDS_FILTER,
    OWNERS_ISNULL_FILTER,
    SOURCES_IDS_FILTER,
)
from infrahub.core.ownership.models import NODE_SOURCES_HOLDER
from infrahub.core.query.node import NodeGetListQuery
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from tests.helpers.ownership import add_node, assert_filter_agrees_with_resolver, set_owners
from tests.helpers.schema.ownership import OWNERSHIP_SCHEMA

if TYPE_CHECKING:
    from infrahub.core.node import Node

DEFAULT_BRANCH = "main"
OTHER_BRANCH = "branch2"
GROUPS = ("dc-emea", "network-emea", "security", "deleted-group")
KINDS = ("TestSite", "TestTenant", "TestRack", "TestDevice", "TestLocation")
SITES_WITH_OWNERS = tuple(f"site-{level}" for level in range(MAX_INHERITANCE_DEPTH + 1))
SITE_BEYOND_DEPTH_LIMIT = f"site-{MAX_INHERITANCE_DEPTH + 1}"
PAGE_SIZE = 5


@dataclass
class FilterDataset:
    branches: dict[str, Branch]
    ids: dict[str, str]
    """The ID of each group and each node, by name."""

    def names(self, node_ids: list[str]) -> list[str]:
        names_by_id = {node_id: name for name, node_id in self.ids.items()}
        return sorted(names_by_id[node_id] for node_id in node_ids)


@dataclass
class FilterTestCase:
    name: str
    branch: str
    kind: str
    filters: dict[str, Any]
    """A list of group names for the owner filter and the source filter."""

    expected: tuple[str, ...]


FILTER_TEST_CASES: list[FilterTestCase] = [
    FilterTestCase(
        name="own_owners_and_hierarchy_parents_up_to_the_depth_limit",
        branch=DEFAULT_BRANCH,
        kind="TestSite",
        filters={OWNERS_IDS_FILTER: ["dc-emea"]},
        expected=SITES_WITH_OWNERS,
    ),
    FilterTestCase(
        name="parent_relationship_wins_over_hierarchy_parent",
        branch=DEFAULT_BRANCH,
        kind="TestRack",
        filters={OWNERS_IDS_FILTER: ["dc-emea"]},
        expected=("rack-own-owners",),
    ),
    FilterTestCase(
        name="parent_relationship_one_level",
        branch=DEFAULT_BRANCH,
        kind="TestRack",
        filters={OWNERS_IDS_FILTER: ["network-emea"]},
        expected=("rack-a",),
    ),
    FilterTestCase(
        name="parent_relationship_two_levels",
        branch=DEFAULT_BRANCH,
        kind="TestDevice",
        filters={OWNERS_IDS_FILTER: ["network-emea"]},
        expected=("device-a",),
    ),
    FilterTestCase(
        name="node_with_two_matching_owners_is_listed_one_time",
        branch=DEFAULT_BRANCH,
        kind="TestRack",
        filters={OWNERS_IDS_FILTER: ["dc-emea", "security"]},
        expected=("rack-own-owners",),
    ),
    FilterTestCase(
        name="any_of_the_owners",
        branch=DEFAULT_BRANCH,
        kind="TestDevice",
        filters={OWNERS_IDS_FILTER: ["network-emea", "security"]},
        expected=("device-a", "device-b"),
    ),
    FilterTestCase(
        name="generic_kind",
        branch=DEFAULT_BRANCH,
        kind="TestLocation",
        filters={OWNERS_IDS_FILTER: ["dc-emea"]},
        expected=(*SITES_WITH_OWNERS, "rack-own-owners"),
    ),
    FilterTestCase(
        name="deleted_owner_matches_nothing",
        branch=DEFAULT_BRANCH,
        kind="TestTenant",
        filters={OWNERS_IDS_FILTER: ["deleted-group"]},
        expected=(),
    ),
    FilterTestCase(
        name="empty_list_of_owners_matches_nothing",
        branch=DEFAULT_BRANCH,
        kind="TestTenant",
        filters={OWNERS_IDS_FILTER: []},
        expected=(),
    ),
    FilterTestCase(
        name="no_owner_beyond_the_depth_limit",
        branch=DEFAULT_BRANCH,
        kind="TestSite",
        filters={OWNERS_ISNULL_FILTER: True},
        expected=(SITE_BEYOND_DEPTH_LIMIT,),
    ),
    FilterTestCase(
        name="no_owner_without_state_and_with_only_a_deleted_owner",
        branch=DEFAULT_BRANCH,
        kind="TestTenant",
        filters={OWNERS_ISNULL_FILTER: True},
        expected=("tenant-of-deleted-group", "tenant-without-owners"),
    ),
    FilterTestCase(
        name="no_owner_set_under_a_parent_with_owners",
        branch=DEFAULT_BRANCH,
        kind="TestRack",
        filters={OWNERS_ISNULL_FILTER: True},
        expected=(
            "rack-no-owner",
            "rack-of-deleted-group",
            "rack-of-tenant-without-owners",
            "rack-of-tenant-a-with-a-deleted-owner",
        ),
    ),
    FilterTestCase(
        name="no_owner_inherited",
        branch=DEFAULT_BRANCH,
        kind="TestDevice",
        filters={OWNERS_ISNULL_FILTER: True},
        expected=("device-c", "device-d", "device-e"),
    ),
    FilterTestCase(
        name="with_an_owner",
        branch=DEFAULT_BRANCH,
        kind="TestDevice",
        filters={OWNERS_ISNULL_FILTER: False},
        expected=("device-a", "device-b"),
    ),
    FilterTestCase(
        name="owner_and_no_owner_together_match_nothing",
        branch=DEFAULT_BRANCH,
        kind="TestDevice",
        filters={OWNERS_IDS_FILTER: ["network-emea"], OWNERS_ISNULL_FILTER: True},
        expected=(),
    ),
    FilterTestCase(
        name="owner_filter_with_a_filter_on_node_ids",
        branch=DEFAULT_BRANCH,
        kind="TestSite",
        filters={OWNERS_IDS_FILTER: ["dc-emea"], "ids": ["site-1", SITE_BEYOND_DEPTH_LIMIT]},
        expected=("site-1",),
    ),
    FilterTestCase(
        name="no_owner_filter_with_an_attribute_filter",
        branch=DEFAULT_BRANCH,
        kind="TestRack",
        filters={OWNERS_ISNULL_FILTER: True, "name__value": "rack-no-owner"},
        expected=("rack-no-owner",),
    ),
    FilterTestCase(
        name="owner_filter_with_an_indexed_attribute_filter_on_a_node_without_the_owner",
        branch=DEFAULT_BRANCH,
        kind="TestRack",
        filters={OWNERS_IDS_FILTER: ["dc-emea"], "name__value": "rack-a"},
        expected=(),
    ),
    FilterTestCase(
        name="owner_filter_with_an_indexed_attribute_filter_on_the_same_node",
        branch=DEFAULT_BRANCH,
        kind="TestRack",
        filters={OWNERS_IDS_FILTER: ["dc-emea"], "name__value": "rack-own-owners"},
        expected=("rack-own-owners",),
    ),
    FilterTestCase(
        name="source_filter_with_an_indexed_attribute_filter_on_a_node_without_the_source",
        branch=DEFAULT_BRANCH,
        kind="TestRack",
        filters={SOURCES_IDS_FILTER: ["security"], "name__value": "rack-a"},
        expected=(),
    ),
    FilterTestCase(
        name="source_filter_with_an_indexed_attribute_filter_on_the_same_node",
        branch=DEFAULT_BRANCH,
        kind="TestRack",
        filters={SOURCES_IDS_FILTER: ["security"], "name__value": "rack-own-owners"},
        expected=("rack-own-owners",),
    ),
    FilterTestCase(
        name="branch_removed_the_owner",
        branch=OTHER_BRANCH,
        kind="TestRack",
        filters={OWNERS_IDS_FILTER: ["network-emea"]},
        expected=(),
    ),
    FilterTestCase(
        name="branch_added_an_owner_and_set_a_node_back_to_inherit",
        branch=OTHER_BRANCH,
        kind="TestRack",
        filters={OWNERS_IDS_FILTER: ["security"]},
        expected=("rack-a", "rack-no-owner", "rack-own-owners"),
    ),
    FilterTestCase(
        name="branch_changed_the_parent",
        branch=OTHER_BRANCH,
        kind="TestDevice",
        filters={OWNERS_IDS_FILTER: ["dc-emea"]},
        expected=("device-a", "device-b"),
    ),
    FilterTestCase(
        name="branch_set_no_owner_above_nodes_that_inherit",
        branch=OTHER_BRANCH,
        kind="TestSite",
        filters={OWNERS_ISNULL_FILTER: True},
        expected=(*SITES_WITH_OWNERS, SITE_BEYOND_DEPTH_LIMIT),
    ),
    FilterTestCase(
        name="branch_no_owner_inherited",
        branch=OTHER_BRANCH,
        kind="TestDevice",
        filters={OWNERS_ISNULL_FILTER: True},
        expected=("device-d", "device-e"),
    ),
]


class TestOwnerFilter:
    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> FilterDataset:
        branch = default_branch_scope_class
        registry.schema.register_schema(schema=OWNERSHIP_SCHEMA, branch=branch.name)
        branch.update_schema_hash()

        nodes: dict[str, Node] = {}
        for name in GROUPS:
            nodes[name] = await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name=name)

        nodes["site-0"] = await add_node(db=db, kind="TestSite", name="site-0")
        for level in range(1, MAX_INHERITANCE_DEPTH + 2):
            nodes[f"site-{level}"] = await add_node(
                db=db, kind="TestSite", name=f"site-{level}", parent=nodes[f"site-{level - 1}"]
            )
        for name in ("tenant-a", "tenant-without-owners", "tenant-of-deleted-group"):
            nodes[name] = await add_node(db=db, kind="TestTenant", name=name)
        racks = {
            "rack-a": "tenant-a",
            "rack-own-owners": "tenant-a",
            "rack-no-owner": "tenant-a",
            "rack-of-tenant-without-owners": "tenant-without-owners",
            "rack-of-deleted-group": "tenant-of-deleted-group",
            "rack-of-tenant-a-with-a-deleted-owner": "tenant-a",
        }
        for name, tenant in racks.items():
            nodes[name] = await add_node(
                db=db, kind="TestRack", name=name, parent=nodes["site-0"], tenant=nodes[tenant]
            )
        devices = {
            "device-a": "rack-a",
            "device-b": "rack-own-owners",
            "device-c": "rack-no-owner",
            "device-d": "rack-of-deleted-group",
            "device-e": "rack-of-tenant-a-with-a-deleted-owner",
        }
        for name, rack in devices.items():
            nodes[name] = await add_node(db=db, kind="TestDevice", name=name, rack=nodes[rack])
        ids = {name: node.id for name, node in nodes.items()}

        owners: dict[str, tuple[str, ...]] = {
            "site-0": ("dc-emea",),
            "tenant-a": ("network-emea",),
            "tenant-of-deleted-group": ("deleted-group",),
            "rack-own-owners": ("dc-emea", "security"),
            "rack-no-owner": (),
            "rack-of-tenant-a-with-a-deleted-owner": ("deleted-group",),
        }
        for name, group_names in owners.items():
            await set_owners(
                db=db, branch=branch, node_id=ids[name], owner_ids=tuple(ids[group] for group in group_names)
            )

        await set_owners(
            db=db,
            branch=branch,
            node_id=ids["rack-own-owners"],
            owner_ids=(ids["security"],),
            holder=NODE_SOURCES_HOLDER,
        )

        await nodes["deleted-group"].delete(db=db)

        other_branch = await create_branch(branch_name=OTHER_BRANCH, db=db)
        device = await NodeManager.get_one(db=db, branch=other_branch, id=ids["device-a"], raise_on_error=True)
        await device.rack.update(db=db, data=nodes["rack-own-owners"])
        await device.save(db=db)
        await set_owners(db=db, branch=other_branch, node_id=ids["tenant-a"], owner_ids=(ids["security"],))
        await set_owners(db=db, branch=other_branch, node_id=ids["rack-no-owner"], owner_ids=None)
        await set_owners(db=db, branch=other_branch, node_id=ids["site-0"], owner_ids=())

        return FilterDataset(branches={DEFAULT_BRANCH: branch, OTHER_BRANCH: other_branch}, ids=ids)

    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in FILTER_TEST_CASES])
    async def test_filter_lists_and_counts_the_nodes_that_match(
        self, db: InfrahubDatabase, dataset: FilterDataset, test_case: FilterTestCase
    ) -> None:
        branch = dataset.branches[test_case.branch]
        filters = dict(test_case.filters)
        for group_filter in (OWNERS_IDS_FILTER, SOURCES_IDS_FILTER):
            if group_filter in filters:
                filters[group_filter] = [dataset.ids[name] for name in filters[group_filter]]
        if "ids" in filters:
            filters["ids"] = [dataset.ids[name] for name in filters["ids"]]

        nodes = await NodeManager.query(db=db, schema=test_case.kind, branch=branch, filters=filters)
        count = await NodeManager.count(db=db, schema=test_case.kind, branch=branch, filters=filters)

        assert dataset.names([node.id for node in nodes]) == sorted(test_case.expected)
        assert count == len(test_case.expected)

    @pytest.mark.parametrize("branch_name", [DEFAULT_BRANCH, OTHER_BRANCH])
    @pytest.mark.parametrize("kind", KINDS)
    async def test_filter_agrees_with_the_owners_that_apply_to_each_node(
        self, db: InfrahubDatabase, dataset: FilterDataset, branch_name: str, kind: str
    ) -> None:
        live_groups = {dataset.ids[name]: name for name in GROUPS if name != "deleted-group"}
        await assert_filter_agrees_with_resolver(
            db=db, branch=dataset.branches[branch_name], kind=kind, live_groups=live_groups
        )

    async def test_filter_applies_before_pagination(self, db: InfrahubDatabase, dataset: FilterDataset) -> None:
        branch = dataset.branches[DEFAULT_BRANCH]
        filters = {OWNERS_IDS_FILTER: [dataset.ids["dc-emea"]]}
        pages: list[list[str]] = []
        for offset in range(0, len(SITES_WITH_OWNERS) + PAGE_SIZE, PAGE_SIZE):
            query = await NodeGetListQuery.init(
                db=db,
                schema=registry.schema.get(name="TestSite", branch=branch),
                branch=branch,
                filters=filters,
                limit=PAGE_SIZE,
                offset=offset,
            )
            await query.execute(db=db)
            pages.append(query.get_node_ids())

        listed = [node_id for page in pages for node_id in page]
        assert [len(page) for page in pages] == [PAGE_SIZE, PAGE_SIZE, PAGE_SIZE, 2, 0]
        assert len(listed) == len(set(listed))
        assert dataset.names(listed) == sorted(SITES_WITH_OWNERS)
        assert await NodeManager.count(db=db, schema="TestSite", branch=branch, filters=filters) == len(
            SITES_WITH_OWNERS
        )
