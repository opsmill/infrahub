from dataclasses import dataclass

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.ownership.constants import MAX_INHERITANCE_DEPTH, MAX_NODES_FOR_LINEAGE_WALK
from infrahub.core.ownership.models import NODE_HOLDER, OwnerOrigin, OwnerState, ResolvedOwnership, StoredOwnerState
from infrahub.core.ownership.queries import NodeOwnerStateReadQuery
from infrahub.core.ownership.repository import OwnershipRepository
from infrahub.core.ownership.resolver import OwnershipResolver
from infrahub.core.ownership.writer import OwnershipWriter
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.helpers.db_query_counter import CountingInfrahubDatabase
from tests.helpers.schema.ownership import OWNERSHIP_SCHEMA

USER_ID = "test-user-id"
SITE_AT_DEPTH_LIMIT = f"site-{MAX_INHERITANCE_DEPTH}"
SITE_BEYOND_DEPTH_LIMIT = f"site-{MAX_INHERITANCE_DEPTH + 1}"
GROUP_NAMES = ("dc-emea", "network-emea", "security")


async def _create(db: InfrahubDatabase, kind: str, name: str, **kwargs: Node) -> Node:
    node = await Node.init(db=db, schema=kind)
    await node.new(db=db, name=name, **kwargs)
    await node.save(db=db)
    return node


async def _set_owners(db: InfrahubDatabase, branch: Branch, node: Node, owner_ids: tuple[str, ...]) -> None:
    writer = OwnershipWriter(repository=OwnershipRepository(db=db, branch=branch, at=None))
    await writer.apply(
        node=node, holder=NODE_HOLDER, state=StoredOwnerState(owner_ids=owner_ids), at=Timestamp(), user_id=USER_ID
    )


def _resolver(db: InfrahubDatabase, branch: Branch) -> OwnershipResolver:
    return OwnershipResolver(repository=OwnershipRepository(db=db, branch=branch, at=None))


@dataclass
class ResolverDataset:
    branch: Branch
    """On this branch, the device `device-a` is in the rack `rack-own-owners`."""

    ids: dict[str, str]
    """The ID of each group and each node, by name."""


@dataclass
class ResolverTestCase:
    name: str
    node: str
    state: OwnerState
    owners: tuple[str, ...]
    """Group names."""

    origin: OwnerOrigin | None
    origin_node: str | None


RESOLVER_TEST_CASES: list[ResolverTestCase] = [
    ResolverTestCase(
        name="hierarchy_parent",
        node="site-1",
        state=OwnerState.INHERIT,
        owners=("dc-emea",),
        origin=OwnerOrigin.PARENT,
        origin_node="site-0",
    ),
    ResolverTestCase(
        name="parent_relationship_wins_over_hierarchy_parent",
        node="rack-a",
        state=OwnerState.INHERIT,
        owners=("network-emea",),
        origin=OwnerOrigin.PARENT,
        origin_node="tenant-a",
    ),
    ResolverTestCase(
        name="parent_relationship_without_owners_wins_over_hierarchy_parent",
        node="rack-of-tenant-without-owners",
        state=OwnerState.INHERIT,
        owners=(),
        origin=None,
        origin_node=None,
    ),
    ResolverTestCase(
        name="parent_relationship_two_levels",
        node="device-a",
        state=OwnerState.INHERIT,
        owners=("network-emea",),
        origin=OwnerOrigin.PARENT,
        origin_node="tenant-a",
    ),
    ResolverTestCase(
        name="owners_at_the_depth_limit",
        node=SITE_AT_DEPTH_LIMIT,
        state=OwnerState.INHERIT,
        owners=("dc-emea",),
        origin=OwnerOrigin.PARENT,
        origin_node="site-0",
    ),
    ResolverTestCase(
        name="owners_one_level_beyond_the_depth_limit",
        node=SITE_BEYOND_DEPTH_LIMIT,
        state=OwnerState.INHERIT,
        owners=(),
        origin=None,
        origin_node=None,
    ),
]


class TestOwnershipResolver:
    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> ResolverDataset:
        branch = default_branch_scope_class
        registry.schema.register_schema(schema=OWNERSHIP_SCHEMA, branch=branch.name)
        branch.update_schema_hash()

        nodes: dict[str, Node] = {}
        for name in GROUP_NAMES:
            nodes[name] = await _create(db=db, kind=InfrahubKind.ACCOUNTGROUP, name=name)

        nodes["site-0"] = await _create(db=db, kind="TestSite", name="site-0")
        for level in range(1, MAX_INHERITANCE_DEPTH + 2):
            nodes[f"site-{level}"] = await _create(
                db=db, kind="TestSite", name=f"site-{level}", parent=nodes[f"site-{level - 1}"]
            )
        for name in ("tenant-a", "tenant-without-owners"):
            nodes[name] = await _create(db=db, kind="TestTenant", name=name)
        racks = {
            "rack-a": "tenant-a",
            "rack-own-owners": "tenant-a",
            "rack-no-owner": "tenant-a",
            "rack-of-tenant-without-owners": "tenant-without-owners",
        }
        for name, tenant in racks.items():
            nodes[name] = await _create(db=db, kind="TestRack", name=name, parent=nodes["site-0"], tenant=nodes[tenant])
        devices = {"device-a": "rack-a", "device-b": "rack-own-owners", "device-c": "rack-no-owner"}
        for name, rack in devices.items():
            nodes[name] = await _create(db=db, kind="TestDevice", name=name, rack=nodes[rack])

        owners = {
            "site-0": ("dc-emea",),
            "tenant-a": ("network-emea",),
            "rack-own-owners": ("dc-emea", "security"),
            "rack-no-owner": (),
        }
        for name, group_names in owners.items():
            await _set_owners(
                db=db, branch=branch, node=nodes[name], owner_ids=tuple(nodes[group].id for group in group_names)
            )

        other_branch = await create_branch(branch_name="branch2", db=db)
        device = await NodeManager.get_one(db=db, branch=other_branch, id=nodes["device-a"].id, raise_on_error=True)
        await device.rack.update(db=db, data=nodes["rack-own-owners"])
        await device.save(db=db)

        return ResolverDataset(branch=other_branch, ids={name: node.id for name, node in nodes.items()})

    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in RESOLVER_TEST_CASES])
    async def test_resolve_on_default_branch(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        dataset: ResolverDataset,
        test_case: ResolverTestCase,
    ) -> None:
        node_id = dataset.ids[test_case.node]

        resolved = await _resolver(db=db, branch=default_branch_scope_class).resolve(node_ids=[node_id])

        assert resolved == {
            node_id: ResolvedOwnership(
                state=test_case.state,
                owner_ids=tuple(sorted(dataset.ids[group] for group in test_case.owners)),
                origin=test_case.origin,
                origin_node_id=dataset.ids[test_case.origin_node] if test_case.origin_node else None,
            )
        }

    async def test_resolve_many_nodes_gives_each_node_the_result_of_its_own_walk(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, dataset: ResolverDataset
    ) -> None:
        resolver = _resolver(db=db, branch=default_branch_scope_class)
        node_ids = [node_id for name, node_id in dataset.ids.items() if name not in GROUP_NAMES]
        one_by_one: dict[str, ResolvedOwnership] = {}
        for node_id in node_ids:
            one_by_one.update(await resolver.resolve(node_ids=[node_id]))

        resolved = await resolver.resolve(node_ids=[*node_ids, "unknown-id"])

        assert len(one_by_one) == len(node_ids)
        assert resolved == one_by_one

    async def test_resolve_follows_the_parent_of_the_branch(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, dataset: ResolverDataset
    ) -> None:
        device_id = dataset.ids["device-a"]

        on_branch = await _resolver(db=db, branch=dataset.branch).resolve(node_ids=[device_id])
        on_default_branch = await _resolver(db=db, branch=default_branch_scope_class).resolve(node_ids=[device_id])

        assert on_branch[device_id].owner_ids == tuple(sorted([dataset.ids["dc-emea"], dataset.ids["security"]]))
        assert on_branch[device_id].origin_node_id == dataset.ids["rack-own-owners"]
        assert on_default_branch[device_id].owner_ids == (dataset.ids["network-emea"],)
        assert on_default_branch[device_id].origin_node_id == dataset.ids["tenant-a"]

    async def test_one_read_gives_the_parents_of_all_levels_for_one_node_and_for_many(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, dataset: ResolverDataset
    ) -> None:
        device_ids = [dataset.ids[name] for name in ("device-a", "device-b", "device-c")]
        counts: list[int] = []
        for branch, node_ids in (
            (default_branch_scope_class, device_ids[:1]),
            (default_branch_scope_class, device_ids),
            (dataset.branch, device_ids),
        ):
            counting_db = CountingInfrahubDatabase.from_db(db=db)
            resolved = await _resolver(db=counting_db, branch=branch).resolve(node_ids=node_ids)
            assert list(resolved) == node_ids
            counts.append(counting_db.count_for(NodeOwnerStateReadQuery.name))

        # One read for the devices, their racks and the tenant of the rack that inherits, also on a branch.
        assert counts == [1, 1, 1]

    async def test_template_copy_is_read_without_its_parents(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        dataset: ResolverDataset,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        branch = default_branch_scope_class
        parent = await NodeManager.get_one(db=db, branch=branch, id=dataset.ids["site-1"], raise_on_error=True)
        template = await Node.init(db=db, schema="TemplateTestSite")
        await template.new(db=db, template_name="site-template")
        await template.save(db=db)
        site = await _create(db=db, kind="TestSite", name="site-from-template", parent=parent)
        writer = OwnershipWriter(repository=OwnershipRepository(db=db, branch=branch, at=None))
        await writer.copy_from_template(
            node=site, template_id=template.id, owner_ids=(dataset.ids["security"],), at=Timestamp(), user_id=USER_ID
        )
        expected = ResolvedOwnership(
            state=OwnerState.INHERIT,
            owner_ids=(dataset.ids["security"],),
            origin=OwnerOrigin.TEMPLATE,
            origin_node_id=template.id,
        )

        nodes_read: dict[int, int] = {}
        # With a limit of 0 nodes, the resolver reads one level of parents for each query.
        for walk_limit in (MAX_NODES_FOR_LINEAGE_WALK, 0):
            monkeypatch.setattr("infrahub.core.ownership.resolver.MAX_NODES_FOR_LINEAGE_WALK", walk_limit)
            counting_db = CountingInfrahubDatabase.from_db(db=db)
            resolved = await _resolver(db=counting_db, branch=branch).resolve(node_ids=[site.id])
            assert resolved == {site.id: expected}
            nodes_read[walk_limit] = counting_db.rows_for(NodeOwnerStateReadQuery.name)

        assert nodes_read == {MAX_NODES_FOR_LINEAGE_WALK: 1, 0: 1}
