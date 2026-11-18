from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.ownership.constants import MAX_INHERITANCE_DEPTH, OWNERS_IDS_FILTER, OWNERS_ISNULL_FILTER
from infrahub.core.ownership.models import NODE_HOLDER, StoredOwnerState
from infrahub.core.ownership.repository import OwnershipRepository
from infrahub.core.ownership.resolver import OwnershipResolver
from infrahub.core.ownership.writer import OwnershipWriter
from infrahub.core.query.node import NodeGetListQuery
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.helpers.schema.ownership import OWNERSHIP_SCHEMA

USER_ID = "test-user-id"
DEFAULT_BRANCH = "main"
OTHER_BRANCH = "branch2"
GROUPS = ("dc-emea", "network-emea", "security", "deleted-group")
KINDS = ("TestSite", "TestTenant", "TestRack", "TestDevice", "TestLocation")
SITES_WITH_OWNERS = tuple(f"site-{level}" for level in range(MAX_INHERITANCE_DEPTH + 1))
SITE_BEYOND_DEPTH_LIMIT = f"site-{MAX_INHERITANCE_DEPTH + 1}"
PAGE_SIZE = 5


async def _create(db: InfrahubDatabase, kind: str, name: str, **kwargs: Node) -> Node:
    node = await Node.init(db=db, schema=kind)
    await node.new(db=db, name=name, **kwargs)
    await node.save(db=db)
    return node


async def _set_owners(db: InfrahubDatabase, branch: Branch, node_id: str, owner_ids: tuple[str, ...] | None) -> None:
    node = await NodeManager.get_one(db=db, branch=branch, id=node_id, raise_on_error=True)
    writer = OwnershipWriter(repository=OwnershipRepository(db=db, branch=branch, at=None))
    await writer.apply(
        node=node, holder=NODE_HOLDER, state=StoredOwnerState(owner_ids=owner_ids), at=Timestamp(), user_id=USER_ID
    )


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
    """A list of group names for the owner filter."""

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
        expected=("rack-no-owner", "rack-of-deleted-group", "rack-of-tenant-without-owners"),
    ),
    FilterTestCase(
        name="no_owner_inherited",
        branch=DEFAULT_BRANCH,
        kind="TestDevice",
        filters={OWNERS_ISNULL_FILTER: True},
        expected=("device-c", "device-d"),
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
        expected=("device-d",),
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
            nodes[name] = await _create(db=db, kind=InfrahubKind.ACCOUNTGROUP, name=name)

        nodes["site-0"] = await _create(db=db, kind="TestSite", name="site-0")
        for level in range(1, MAX_INHERITANCE_DEPTH + 2):
            nodes[f"site-{level}"] = await _create(
                db=db, kind="TestSite", name=f"site-{level}", parent=nodes[f"site-{level - 1}"]
            )
        for name in ("tenant-a", "tenant-without-owners", "tenant-of-deleted-group"):
            nodes[name] = await _create(db=db, kind="TestTenant", name=name)
        racks = {
            "rack-a": "tenant-a",
            "rack-own-owners": "tenant-a",
            "rack-no-owner": "tenant-a",
            "rack-of-tenant-without-owners": "tenant-without-owners",
            "rack-of-deleted-group": "tenant-of-deleted-group",
        }
        for name, tenant in racks.items():
            nodes[name] = await _create(db=db, kind="TestRack", name=name, parent=nodes["site-0"], tenant=nodes[tenant])
        devices = {
            "device-a": "rack-a",
            "device-b": "rack-own-owners",
            "device-c": "rack-no-owner",
            "device-d": "rack-of-deleted-group",
        }
        for name, rack in devices.items():
            nodes[name] = await _create(db=db, kind="TestDevice", name=name, rack=nodes[rack])
        ids = {name: node.id for name, node in nodes.items()}

        owners: dict[str, tuple[str, ...]] = {
            "site-0": ("dc-emea",),
            "tenant-a": ("network-emea",),
            "tenant-of-deleted-group": ("deleted-group",),
            "rack-own-owners": ("dc-emea", "security"),
            "rack-no-owner": (),
        }
        for name, group_names in owners.items():
            await _set_owners(
                db=db, branch=branch, node_id=ids[name], owner_ids=tuple(ids[group] for group in group_names)
            )

        await nodes["deleted-group"].delete(db=db)

        other_branch = await create_branch(branch_name=OTHER_BRANCH, db=db)
        device = await NodeManager.get_one(db=db, branch=other_branch, id=ids["device-a"], raise_on_error=True)
        await device.rack.update(db=db, data=nodes["rack-own-owners"])
        await device.save(db=db)
        await _set_owners(db=db, branch=other_branch, node_id=ids["tenant-a"], owner_ids=(ids["security"],))
        await _set_owners(db=db, branch=other_branch, node_id=ids["rack-no-owner"], owner_ids=None)
        await _set_owners(db=db, branch=other_branch, node_id=ids["site-0"], owner_ids=())

        return FilterDataset(branches={DEFAULT_BRANCH: branch, OTHER_BRANCH: other_branch}, ids=ids)

    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in FILTER_TEST_CASES])
    async def test_filter_lists_and_counts_the_nodes_that_match(
        self, db: InfrahubDatabase, dataset: FilterDataset, test_case: FilterTestCase
    ) -> None:
        branch = dataset.branches[test_case.branch]
        filters = {key: value for key, value in test_case.filters.items() if key != OWNERS_IDS_FILTER}
        if OWNERS_IDS_FILTER in test_case.filters:
            filters[OWNERS_IDS_FILTER] = [dataset.ids[name] for name in test_case.filters[OWNERS_IDS_FILTER]]
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
        branch = dataset.branches[branch_name]
        live_groups = {dataset.ids[name]: name for name in GROUPS if name != "deleted-group"}
        node_ids = [node.id for node in await NodeManager.query(db=db, schema=kind, branch=branch)]
        resolved = await OwnershipResolver(repository=OwnershipRepository(db=db, branch=branch, at=None)).resolve(
            node_ids=node_ids
        )
        expected: dict[str, list[str]] = {name: [] for name in (*live_groups.values(), "no owner", "an owner")}
        for node_id in sorted(node_ids):
            groups = [live_groups[owner_id] for owner_id in resolved[node_id].owner_ids if owner_id in live_groups]
            for name in groups or ["no owner"]:
                expected[name].append(node_id)
            if groups:
                expected["an owner"].append(node_id)

        listed: dict[str, list[str]] = {}
        filters: dict[str, dict[str, Any]] = {
            "no owner": {OWNERS_ISNULL_FILTER: True},
            "an owner": {OWNERS_ISNULL_FILTER: False},
            **{name: {OWNERS_IDS_FILTER: [group_id]} for group_id, name in live_groups.items()},
        }
        for name, owner_filter in filters.items():
            nodes = await NodeManager.query(db=db, schema=kind, branch=branch, filters=owner_filter)
            listed[name] = sorted(node.id for node in nodes)

        assert len(node_ids) > 0
        assert listed == expected

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
