from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.create import create_node
from infrahub.core.ownership.models import (
    NODE_HOLDER,
    NODE_TARGET_HOLDER,
    HolderKey,
    OwnerOrigin,
    OwnerState,
    ResolvedOwnership,
    StoredOwnerState,
)
from infrahub.core.ownership.queries import NodeOwnerStateReadQuery
from infrahub.core.ownership.repository import OwnershipRepository
from infrahub.core.ownership.resolver import OwnershipResolver
from infrahub.core.ownership.writer import OwnershipWriter
from infrahub.core.query import QueryType
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_graph
from tests.helpers.db_query_counter import CountingInfrahubDatabase
from tests.helpers.ownership import TARGET_OWNERS_FIELD, USER_ID, add_node
from tests.helpers.schema.ownership import OWNERSHIP_SCHEMA

DEFAULT_BRANCH = "main"
OTHER_BRANCH = "branch2"
GROUPS = ("dc-emea", "dc-security", "network-emea", "deleted-group")
DEVICE_PROFILE = "ProfileTestDevice"
RACK_PROFILE = "ProfileTestRack"
SITE_PROFILE = "ProfileTestSite"
SITE_TEMPLATE = "TemplateTestSite"


async def _write(
    db: InfrahubDatabase, branch: Branch, node_id: str, holder: HolderKey, owner_ids: tuple[str, ...] | None
) -> Node:
    """Store an owner state, and return the node with the changelog of the write."""
    node = await NodeManager.get_one(db=db, branch=branch, id=node_id, raise_on_error=True)
    await node.save(db=db)
    writer = OwnershipWriter(repository=OwnershipRepository(db=db, branch=branch, at=None))
    await writer.apply(
        node=node, holder=holder, state=StoredOwnerState(owner_ids=owner_ids), at=Timestamp(), user_id=USER_ID
    )
    return node


async def _create_from_template(db: InfrahubDatabase, branch: Branch, template: Node, **data: Any) -> Node:
    """Create a site the way a mutation does, so that it gets a copy of the owners that its template gives."""
    return await create_node(
        data={**data, "object_template": {"id": template.id}},
        db=db,
        branch=branch,
        schema=registry.schema.get_node_schema(name="TestSite", branch=branch),
    )


async def _set_profiles(db: InfrahubDatabase, branch: Branch, node_id: str, profiles: list[Node]) -> None:
    node = await NodeManager.get_one(db=db, branch=branch, id=node_id, raise_on_error=True)
    await node.profiles.update(db=db, data=profiles)
    await node.save(db=db)


async def _resolve(db: InfrahubDatabase, branch: Branch, node_ids: list[str]) -> dict[str, ResolvedOwnership]:
    return await OwnershipResolver(repository=OwnershipRepository(db=db, branch=branch, at=None)).resolve(
        node_ids=node_ids
    )


async def _stored(db: InfrahubDatabase, branch: Branch, node_id: str) -> dict[HolderKey, StoredOwnerState]:
    stored = await OwnershipRepository(db=db, branch=branch, at=None).read(node_ids=[node_id])
    assert list(stored) == [node_id]
    return dict(stored[node_id].holders)


async def _given_owner_edges(db: InfrahubDatabase, profile_id: str) -> list[tuple[str, str, str, str, bool]]:
    """Return the edge to each set of owners that a profile gives, then the edges of the set, as stored."""
    rows = await db.execute_query(
        query="""
        MATCH (:Node {uuid: $profile_id})-[attached:HAS_TARGET_OWNER_SET]->(s:OwnerSet)
        OPTIONAL MATCH (s)-[r:HAS_OWNER|HAS_NO_OWNER]->(peer)
        UNWIND [[attached, "set"], [r, peer.uuid]] AS item
        WITH DISTINCT item[0] AS edge, item[1] AS peer
        WHERE edge IS NOT NULL
        RETURN type(edge) AS edge_type, peer, edge.branch AS branch, edge.status AS status, edge.to IS NULL AS is_open
        """,
        params={"profile_id": profile_id},
        name="test_read_given_owner_edges",
        type=QueryType.READ,
    )
    return sorted((row["edge_type"], row["peer"], row["branch"], row["status"], row["is_open"]) for row in rows)


async def _count_owner_sets(db: InfrahubDatabase, profile_id: str) -> int:
    rows = await db.execute_query(
        query="""
        MATCH (:Node {uuid: $profile_id})-[:HAS_TARGET_OWNER_SET]->(s:OwnerSet)
        RETURN count(DISTINCT s) AS owner_sets
        """,
        params={"profile_id": profile_id},
        name="test_count_owner_sets",
        type=QueryType.READ,
    )
    return rows[0]["owner_sets"]


@dataclass
class ProfileDataset:
    branches: dict[str, Branch]
    ids: dict[str, str]
    """The ID of each group, each profile and each node, by name."""


@dataclass
class ProfileOwnersTestCase:
    name: str
    node: str
    state: OwnerState
    owners: tuple[str, ...]
    """Group names."""

    origin: OwnerOrigin | None
    origin_node: str | None
    branch: str = DEFAULT_BRANCH


PROFILE_OWNERS_TEST_CASES: list[ProfileOwnersTestCase] = [
    ProfileOwnersTestCase(
        name="profile_gives_owners",
        node="device-one-profile",
        state=OwnerState.INHERIT,
        owners=("dc-emea",),
        origin=OwnerOrigin.PROFILE,
        origin_node="emea-fabric",
    ),
    ProfileOwnersTestCase(
        name="profile_with_the_lowest_priority_number_wins",
        node="device-two-profiles",
        state=OwnerState.INHERIT,
        owners=("dc-security",),
        origin=OwnerOrigin.PROFILE,
        origin_node="security",
    ),
    ProfileOwnersTestCase(
        name="profile_that_gives_nothing_is_skipped",
        node="device-first-profile-gives-nothing",
        state=OwnerState.INHERIT,
        owners=("dc-emea",),
        origin=OwnerOrigin.PROFILE,
        origin_node="emea-fabric",
    ),
    ProfileOwnersTestCase(
        name="own_owners_of_a_profile_do_not_reach_its_nodes",
        node="device-profile-gives-nothing",
        state=OwnerState.INHERIT,
        owners=("network-emea",),
        origin=OwnerOrigin.PARENT,
        origin_node="tenant-a",
    ),
    ProfileOwnersTestCase(
        name="own_owners_win_over_a_profile",
        node="device-own-owners",
        state=OwnerState.OWNERS,
        owners=("dc-security",),
        origin=OwnerOrigin.SELF,
        origin_node="device-own-owners",
    ),
    ProfileOwnersTestCase(
        name="own_no_owner_wins_over_a_profile",
        node="device-own-no-owner",
        state=OwnerState.NO_OWNER,
        owners=(),
        origin=OwnerOrigin.SELF,
        origin_node="device-own-no-owner",
    ),
    ProfileOwnersTestCase(
        name="profile_gives_no_owner",
        node="device-profile-gives-no-owner",
        state=OwnerState.INHERIT,
        owners=(),
        origin=OwnerOrigin.PROFILE,
        origin_node="gives-no-owner",
    ),
    ProfileOwnersTestCase(
        name="profile_gives_a_deleted_owner",
        node="device-profile-gives-deleted-group",
        state=OwnerState.INHERIT,
        owners=("deleted-group",),
        origin=OwnerOrigin.PROFILE,
        origin_node="gives-deleted-group",
    ),
    ProfileOwnersTestCase(
        name="profile_without_priority_comes_last",
        node="device-profile-without-priority",
        state=OwnerState.INHERIT,
        owners=("dc-emea",),
        origin=OwnerOrigin.PROFILE,
        origin_node="last-priority",
    ),
    ProfileOwnersTestCase(
        name="profile_of_the_parent",
        node="device-under-rack-with-profile",
        state=OwnerState.INHERIT,
        owners=("dc-security",),
        origin=OwnerOrigin.PARENT,
        origin_node="rack-with-profile",
    ),
    ProfileOwnersTestCase(
        name="template_copy_wins_over_the_parent",
        node="site-from-template",
        state=OwnerState.INHERIT,
        owners=("dc-security",),
        origin=OwnerOrigin.TEMPLATE,
        origin_node="site-template",
    ),
    ProfileOwnersTestCase(
        name="template_copy_of_no_owner_wins_over_the_parent",
        node="site-from-no-owner-template",
        state=OwnerState.INHERIT,
        owners=(),
        origin=OwnerOrigin.TEMPLATE,
        origin_node="no-owner-site-template",
    ),
    ProfileOwnersTestCase(
        name="profile_wins_over_a_template_copy",
        node="site-from-template-with-profile",
        state=OwnerState.INHERIT,
        owners=("dc-emea",),
        origin=OwnerOrigin.PROFILE,
        origin_node="site-fabric",
    ),
    ProfileOwnersTestCase(
        name="own_owners_win_over_a_profile_and_a_template_copy",
        node="site-from-template-own-owners",
        state=OwnerState.OWNERS,
        owners=("dc-emea", "dc-security"),
        origin=OwnerOrigin.SELF,
        origin_node="site-from-template-own-owners",
    ),
    ProfileOwnersTestCase(
        name="child_of_a_template_copy",
        node="site-under-template-copy",
        state=OwnerState.INHERIT,
        owners=("dc-security",),
        origin=OwnerOrigin.PARENT,
        origin_node="site-from-template",
    ),
    ProfileOwnersTestCase(
        name="default_branch_keeps_the_profile_that_a_branch_removed",
        node="device-profile-removed-on-branch",
        state=OwnerState.INHERIT,
        owners=("dc-emea",),
        origin=OwnerOrigin.PROFILE,
        origin_node="emea-fabric",
    ),
    ProfileOwnersTestCase(
        name="default_branch_keeps_the_profile_that_a_branch_deleted",
        node="device-profile-deleted-on-branch",
        state=OwnerState.INHERIT,
        owners=("dc-security",),
        origin=OwnerOrigin.PROFILE,
        origin_node="deleted-on-branch",
    ),
    ProfileOwnersTestCase(
        name="branch_changed_the_owners_that_the_profile_gives",
        branch=OTHER_BRANCH,
        node="device-one-profile",
        state=OwnerState.INHERIT,
        owners=("dc-emea", "dc-security"),
        origin=OwnerOrigin.PROFILE,
        origin_node="emea-fabric",
    ),
    ProfileOwnersTestCase(
        name="branch_changed_the_priority_of_a_profile",
        branch=OTHER_BRANCH,
        node="device-two-profiles",
        state=OwnerState.INHERIT,
        owners=("dc-emea", "dc-security"),
        origin=OwnerOrigin.PROFILE,
        origin_node="emea-fabric",
    ),
    ProfileOwnersTestCase(
        name="branch_removed_the_profile_from_the_node",
        branch=OTHER_BRANCH,
        node="device-profile-removed-on-branch",
        state=OwnerState.INHERIT,
        owners=("network-emea",),
        origin=OwnerOrigin.PARENT,
        origin_node="tenant-a",
    ),
    ProfileOwnersTestCase(
        name="branch_deleted_the_profile",
        branch=OTHER_BRANCH,
        node="device-profile-deleted-on-branch",
        state=OwnerState.INHERIT,
        owners=("dc-emea", "dc-security"),
        origin=OwnerOrigin.PROFILE,
        origin_node="emea-fabric",
    ),
    ProfileOwnersTestCase(
        name="branch_changed_the_template_after_the_create",
        branch=OTHER_BRANCH,
        node="site-from-template",
        state=OwnerState.INHERIT,
        owners=("dc-security",),
        origin=OwnerOrigin.TEMPLATE,
        origin_node="site-template",
    ),
    ProfileOwnersTestCase(
        name="branch_removed_the_profile_from_a_template_copy",
        branch=OTHER_BRANCH,
        node="site-from-template-with-profile",
        state=OwnerState.INHERIT,
        owners=("dc-security",),
        origin=OwnerOrigin.TEMPLATE,
        origin_node="site-template",
    ),
    ProfileOwnersTestCase(
        name="branch_set_the_profile_to_give_nothing",
        branch=OTHER_BRANCH,
        node="rack-with-profile",
        state=OwnerState.INHERIT,
        owners=("network-emea",),
        origin=OwnerOrigin.PARENT,
        origin_node="tenant-a",
    ),
]

DEVICES_IN_RACK_A: dict[str, tuple[str, ...]] = {
    "device-one-profile": ("emea-fabric",),
    "device-two-profiles": ("emea-fabric", "security"),
    "device-profile-gives-nothing": ("gives-nothing",),
    "device-first-profile-gives-nothing": ("gives-nothing", "emea-fabric"),
    "device-own-owners": ("emea-fabric",),
    "device-own-no-owner": ("emea-fabric",),
    "device-profile-gives-no-owner": ("gives-no-owner", "emea-fabric"),
    "device-profile-gives-deleted-group": ("gives-deleted-group", "emea-fabric"),
    "device-profile-without-priority": ("without-priority", "last-priority"),
    "device-without-profile": (),
    "device-profile-removed-on-branch": ("emea-fabric",),
    "device-profile-deleted-on-branch": ("deleted-on-branch", "emea-fabric"),
}
"""The profiles of each device of the rack `rack-a`, on the default branch."""


class TestProfileOwnersRead:
    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> ProfileDataset:
        branch = default_branch_scope_class
        registry.schema.register_schema(schema=OWNERSHIP_SCHEMA, branch=branch.name)
        branch.update_schema_hash()

        nodes: dict[str, Node] = {}
        for name in GROUPS:
            nodes[name] = await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name=name)
        device_profiles: dict[str, int] = {
            "emea-fabric": 100,
            "security": 50,
            "gives-nothing": 10,
            "gives-no-owner": 10,
            "gives-deleted-group": 10,
            "deleted-on-branch": 10,
            "without-priority": 10,
            "last-priority": 5000,
        }
        for name, priority in device_profiles.items():
            nodes[name] = await add_node(db=db, kind=DEVICE_PROFILE, profile_name=name, profile_priority=priority)
        nodes["rack-security"] = await add_node(db=db, kind=RACK_PROFILE, profile_name="rack-security")

        nodes["site-0"] = await add_node(db=db, kind="TestSite", name="site-0")
        nodes["tenant-a"] = await add_node(db=db, kind="TestTenant", name="tenant-a")
        nodes["rack-a"] = await add_node(
            db=db, kind="TestRack", name="rack-a", parent=nodes["site-0"], tenant=nodes["tenant-a"]
        )
        nodes["rack-with-profile"] = await add_node(
            db=db,
            kind="TestRack",
            name="rack-with-profile",
            parent=nodes["site-0"],
            tenant=nodes["tenant-a"],
            profiles=[nodes["rack-security"]],
        )
        for name, profile_names in DEVICES_IN_RACK_A.items():
            nodes[name] = await add_node(
                db=db,
                kind="TestDevice",
                name=name,
                rack=nodes["rack-a"],
                profiles=[nodes[profile_name] for profile_name in profile_names],
            )
        nodes["device-under-rack-with-profile"] = await add_node(
            db=db, kind="TestDevice", name="device-under-rack-with-profile", rack=nodes["rack-with-profile"]
        )
        nodes["site-owned"] = await add_node(db=db, kind="TestSite", name="site-owned")
        nodes["site-fabric"] = await add_node(db=db, kind=SITE_PROFILE, profile_name="site-fabric")
        for name in ("site-template", "no-owner-site-template"):
            nodes[name] = await add_node(db=db, kind=SITE_TEMPLATE, template_name=name)
        ids = {name: node.id for name, node in nodes.items()}

        own_owners: dict[str, tuple[str, ...]] = {
            "site-owned": ("network-emea",),
            "tenant-a": ("network-emea",),
            "device-own-owners": ("dc-security",),
            "device-own-no-owner": (),
            "gives-nothing": ("dc-security",),
        }
        given_owners: dict[str, tuple[str, ...]] = {
            "emea-fabric": ("dc-emea",),
            "security": ("dc-security",),
            "gives-no-owner": (),
            "gives-deleted-group": ("deleted-group",),
            "deleted-on-branch": ("dc-security",),
            "without-priority": ("network-emea",),
            "last-priority": ("dc-emea",),
            "rack-security": ("dc-security",),
            "site-fabric": ("dc-emea",),
            "site-template": ("dc-security",),
            "no-owner-site-template": (),
        }
        for holder, owners in ((NODE_HOLDER, own_owners), (NODE_TARGET_HOLDER, given_owners)):
            for name, group_names in owners.items():
                await _write(
                    db=db,
                    branch=branch,
                    node_id=ids[name],
                    holder=holder,
                    owner_ids=tuple(ids[group] for group in group_names),
                )
        sites_from_templates: dict[str, tuple[str, list[str]]] = {
            "site-from-template": ("site-template", []),
            "site-from-no-owner-template": ("no-owner-site-template", []),
            "site-from-template-with-profile": ("site-template", ["site-fabric"]),
            "site-from-template-own-owners": ("site-template", ["site-fabric"]),
        }
        for name, (template_name, profile_names) in sites_from_templates.items():
            site = await _create_from_template(
                db=db,
                branch=branch,
                template=nodes[template_name],
                name=name,
                parent={"id": ids["site-owned"]},
                profiles=[{"id": ids[profile_name]} for profile_name in profile_names],
            )
            ids[name] = site.id
        ids["site-under-template-copy"] = (
            await add_node(db=db, kind="TestSite", name="site-under-template-copy", parent=ids["site-from-template"])
        ).id
        await _write(
            db=db,
            branch=branch,
            node_id=ids["site-from-template-own-owners"],
            holder=NODE_HOLDER,
            owner_ids=(ids["dc-emea"], ids["dc-security"]),
        )
        await nodes["deleted-group"].delete(db=db)
        nodes["without-priority"].profile_priority.value = None
        await nodes["without-priority"].save(db=db)

        other_branch = await create_branch(branch_name=OTHER_BRANCH, db=db)
        await _write(
            db=db,
            branch=other_branch,
            node_id=ids["emea-fabric"],
            holder=NODE_TARGET_HOLDER,
            owner_ids=(ids["dc-emea"], ids["dc-security"]),
        )
        await _write(
            db=db, branch=other_branch, node_id=ids["rack-security"], holder=NODE_TARGET_HOLDER, owner_ids=None
        )
        security = await NodeManager.get_one(db=db, branch=other_branch, id=ids["security"], raise_on_error=True)
        security.profile_priority.value = 500
        await security.save(db=db)
        await _set_profiles(db=db, branch=other_branch, node_id=ids["device-profile-removed-on-branch"], profiles=[])
        await _write(
            db=db,
            branch=other_branch,
            node_id=ids["site-template"],
            holder=NODE_TARGET_HOLDER,
            owner_ids=(ids["dc-emea"],),
        )
        await _set_profiles(db=db, branch=other_branch, node_id=ids["site-from-template-with-profile"], profiles=[])
        deleted_profile = await NodeManager.get_one(
            db=db, branch=other_branch, id=ids["deleted-on-branch"], raise_on_error=True
        )
        await deleted_profile.delete(db=db)

        return ProfileDataset(branches={DEFAULT_BRANCH: branch, OTHER_BRANCH: other_branch}, ids=ids)

    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in PROFILE_OWNERS_TEST_CASES])
    async def test_resolve_applies_the_owners_that_profiles_give(
        self, db: InfrahubDatabase, dataset: ProfileDataset, test_case: ProfileOwnersTestCase
    ) -> None:
        node_id = dataset.ids[test_case.node]

        resolved = await _resolve(db=db, branch=dataset.branches[test_case.branch], node_ids=[node_id])

        assert resolved == {
            node_id: ResolvedOwnership(
                state=test_case.state,
                owner_ids=tuple(sorted(dataset.ids[group] for group in test_case.owners)),
                origin=test_case.origin,
                origin_node_id=dataset.ids[test_case.origin_node] if test_case.origin_node else None,
            )
        }

    async def test_read_returns_the_profiles_of_each_node_with_the_priority_of_the_branch(
        self, db: InfrahubDatabase, dataset: ProfileDataset
    ) -> None:
        ids = dataset.ids
        node_ids = [ids["device-two-profiles"], ids["device-profile-without-priority"], ids["device-without-profile"]]
        profiles: dict[str, dict[str, list[tuple[str, int | None]]]] = {}
        for branch_name, branch in dataset.branches.items():
            stored = await OwnershipRepository(db=db, branch=branch, at=None).read(node_ids=node_ids)
            profiles[branch_name] = {node_id: sorted(node.profiles) for node_id, node in stored.items()}

        assert profiles == {
            DEFAULT_BRANCH: {
                ids["device-two-profiles"]: sorted([(ids["emea-fabric"], 100), (ids["security"], 50)]),
                ids["device-profile-without-priority"]: sorted(
                    [(ids["without-priority"], None), (ids["last-priority"], 5000)]
                ),
                ids["device-without-profile"]: [],
            },
            OTHER_BRANCH: {
                ids["device-two-profiles"]: sorted([(ids["emea-fabric"], 100), (ids["security"], 500)]),
                ids["device-profile-without-priority"]: sorted(
                    [(ids["without-priority"], None), (ids["last-priority"], 5000)]
                ),
                ids["device-without-profile"]: [],
            },
        }

    async def test_number_of_reads_does_not_grow_with_the_number_of_nodes_of_a_page(
        self, db: InfrahubDatabase, dataset: ProfileDataset
    ) -> None:
        device_ids = [dataset.ids[name] for name in DEVICES_IN_RACK_A]
        counts: list[int] = []
        for node_ids in (device_ids[:1], device_ids):
            counting_db = CountingInfrahubDatabase.from_db(db=db)
            resolved = await _resolve(db=counting_db, branch=dataset.branches[DEFAULT_BRANCH], node_ids=node_ids)
            assert list(resolved) == node_ids
            counts.append(counting_db.count_for(NodeOwnerStateReadQuery.name))

        # One device: one read with its profiles, its rack and the tenant of the rack. A page of devices: one read
        # for the devices, one for their profiles and their rack, and one for the tenant of the rack.
        assert len(device_ids) > 10
        assert counts == [1, 3]

    async def test_graph_stays_valid_after_the_writes(self, db: InfrahubDatabase, dataset: ProfileDataset) -> None:
        await verify_graph(
            db=db,
            kinds=["TestDevice", "TestRack", "TestSite", DEVICE_PROFILE, RACK_PROFILE, SITE_PROFILE, SITE_TEMPLATE],
        )


@dataclass
class ChangesDataset:
    branch: Branch
    groups: dict[str, str]
    """The ID of each group, by name."""

    rack: Node
    """A rack whose tenant has the owner `network-emea`."""

    tenant: Node


class TestProfileOwnerChanges:
    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> ChangesDataset:
        branch = default_branch_scope_class
        registry.schema.register_schema(schema=OWNERSHIP_SCHEMA, branch=branch.name)
        branch.update_schema_hash()
        groups = {
            name: (await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name=name)).id
            for name in ("dc-emea", "dc-security", "network-emea")
        }
        tenant = await add_node(db=db, kind="TestTenant", name="tenant-a")
        rack = await add_node(db=db, kind="TestRack", name="rack-a", tenant=tenant)
        await _write(db=db, branch=branch, node_id=tenant.id, holder=NODE_HOLDER, owner_ids=(groups["network-emea"],))
        return ChangesDataset(branch=branch, groups=groups, rack=rack, tenant=tenant)

    async def _profile_that_gives(
        self, db: InfrahubDatabase, dataset: ChangesDataset, name: str, *group_names: str, priority: int = 100
    ) -> Node:
        profile = await add_node(db=db, kind=DEVICE_PROFILE, profile_name=name, profile_priority=priority)
        await _write(
            db=db,
            branch=dataset.branch,
            node_id=profile.id,
            holder=NODE_TARGET_HOLDER,
            owner_ids=tuple(dataset.groups[group] for group in group_names),
        )
        return profile

    async def test_profile_change_reaches_each_node_at_the_next_read_and_only_the_profile_records_it(
        self, db: InfrahubDatabase, dataset: ChangesDataset
    ) -> None:
        first_id, second_id = sorted([dataset.groups["dc-emea"], dataset.groups["dc-security"]])
        profile = await self._profile_that_gives(db, dataset, "profile-changed", "dc-emea")
        device_ids = [
            (
                await add_node(
                    db=db, kind="TestDevice", name=f"device-changed-{index}", rack=dataset.rack, profiles=[profile]
                )
            ).id
            for index in range(3)
        ]
        before = await _resolve(db=db, branch=dataset.branch, node_ids=device_ids)

        changed_profile = await _write(
            db=db,
            branch=dataset.branch,
            node_id=profile.id,
            holder=NODE_TARGET_HOLDER,
            owner_ids=(dataset.groups["dc-emea"], dataset.groups["dc-security"]),
        )

        assert before == dict.fromkeys(
            device_ids,
            ResolvedOwnership(
                state=OwnerState.INHERIT,
                owner_ids=(dataset.groups["dc-emea"],),
                origin=OwnerOrigin.PROFILE,
                origin_node_id=profile.id,
            ),
        )
        assert await _resolve(db=db, branch=dataset.branch, node_ids=device_ids) == dict.fromkeys(
            device_ids,
            ResolvedOwnership(
                state=OwnerState.INHERIT,
                owner_ids=(first_id, second_id),
                origin=OwnerOrigin.PROFILE,
                origin_node_id=profile.id,
            ),
        )
        change = changed_profile.node_changelog.attributes[TARGET_OWNERS_FIELD]
        assert changed_profile.node_changelog.updated_fields == [TARGET_OWNERS_FIELD]
        assert (change.kind, change.value_previous, change.value) == (
            "List",
            f'["{dataset.groups["dc-emea"]}"]',
            f'["{first_id}","{second_id}"]',
        )
        for device_id in device_ids:
            assert await _stored(db=db, branch=dataset.branch, node_id=device_id) == {}

    async def test_owners_set_on_the_node_replace_the_owners_of_its_profile_and_of_its_template(
        self, db: InfrahubDatabase, dataset: ChangesDataset
    ) -> None:
        profile = await add_node(db=db, kind=SITE_PROFILE, profile_name="site-profile-replaced")
        template = await add_node(db=db, kind=SITE_TEMPLATE, template_name="site-template-replaced")
        for giver, group in ((profile, "dc-emea"), (template, "dc-security")):
            await _write(
                db=db,
                branch=dataset.branch,
                node_id=giver.id,
                holder=NODE_TARGET_HOLDER,
                owner_ids=(dataset.groups[group],),
            )
        site = await _create_from_template(
            db=db, branch=dataset.branch, template=template, name="site-replaced", profiles=[{"id": profile.id}]
        )
        stored_before = await _stored(db=db, branch=dataset.branch, node_id=site.id)
        before = await _resolve(db=db, branch=dataset.branch, node_ids=[site.id])

        await _write(
            db=db,
            branch=dataset.branch,
            node_id=site.id,
            holder=NODE_HOLDER,
            owner_ids=(dataset.groups["network-emea"],),
        )

        assert stored_before == {
            NODE_HOLDER: StoredOwnerState(owner_ids=(dataset.groups["dc-security"],), template_id=template.id)
        }
        assert (before[site.id].origin, before[site.id].origin_node_id) == (OwnerOrigin.PROFILE, profile.id)
        assert await _stored(db=db, branch=dataset.branch, node_id=site.id) == {
            NODE_HOLDER: StoredOwnerState(owner_ids=(dataset.groups["network-emea"],))
        }
        assert await _resolve(db=db, branch=dataset.branch, node_ids=[site.id]) == {
            site.id: ResolvedOwnership(
                state=OwnerState.OWNERS,
                owner_ids=(dataset.groups["network-emea"],),
                origin=OwnerOrigin.SELF,
                origin_node_id=site.id,
            )
        }

    async def test_node_set_to_no_owner_keeps_no_owner_when_a_profile_is_added(
        self, db: InfrahubDatabase, dataset: ChangesDataset
    ) -> None:
        profile = await self._profile_that_gives(db, dataset, "profile-added-later", "dc-emea")
        device = await add_node(db=db, kind="TestDevice", name="device-no-owner", rack=dataset.rack)
        await _write(db=db, branch=dataset.branch, node_id=device.id, holder=NODE_HOLDER, owner_ids=())

        await _set_profiles(db=db, branch=dataset.branch, node_id=device.id, profiles=[profile])

        stored = await OwnershipRepository(db=db, branch=dataset.branch, at=None).read(node_ids=[device.id])
        assert stored[device.id].profiles == ((profile.id, 100),)
        assert await _resolve(db=db, branch=dataset.branch, node_ids=[device.id]) == {
            device.id: ResolvedOwnership(
                state=OwnerState.NO_OWNER, owner_ids=(), origin=OwnerOrigin.SELF, origin_node_id=device.id
            )
        }

    async def test_change_of_the_own_owners_of_a_profile_does_not_change_its_nodes(
        self, db: InfrahubDatabase, dataset: ChangesDataset
    ) -> None:
        profile = await self._profile_that_gives(db, dataset, "profile-own-owners", "dc-emea")
        device = await add_node(
            db=db, kind="TestDevice", name="device-own-owners", rack=dataset.rack, profiles=[profile]
        )
        await _write(
            db=db, branch=dataset.branch, node_id=profile.id, holder=NODE_HOLDER, owner_ids=(dataset.groups["dc-emea"],)
        )
        before = await _resolve(db=db, branch=dataset.branch, node_ids=[device.id])

        await _write(
            db=db,
            branch=dataset.branch,
            node_id=profile.id,
            holder=NODE_HOLDER,
            owner_ids=(dataset.groups["dc-security"],),
        )

        assert await _stored(db=db, branch=dataset.branch, node_id=profile.id) == {
            NODE_HOLDER: StoredOwnerState(owner_ids=(dataset.groups["dc-security"],)),
            NODE_TARGET_HOLDER: StoredOwnerState(owner_ids=(dataset.groups["dc-emea"],)),
        }
        resolved = await _resolve(db=db, branch=dataset.branch, node_ids=[device.id, profile.id])
        assert resolved[device.id] == before[device.id]
        assert resolved[device.id] == ResolvedOwnership(
            state=OwnerState.INHERIT,
            owner_ids=(dataset.groups["dc-emea"],),
            origin=OwnerOrigin.PROFILE,
            origin_node_id=profile.id,
        )
        assert resolved[profile.id] == ResolvedOwnership(
            state=OwnerState.OWNERS,
            owner_ids=(dataset.groups["dc-security"],),
            origin=OwnerOrigin.SELF,
            origin_node_id=profile.id,
        )

    async def test_node_takes_the_owners_of_its_parent_when_its_profile_is_removed(
        self, db: InfrahubDatabase, dataset: ChangesDataset
    ) -> None:
        profile = await self._profile_that_gives(db, dataset, "profile-removed", "dc-emea")
        device = await add_node(db=db, kind="TestDevice", name="device-removed", rack=dataset.rack, profiles=[profile])
        before = await _resolve(db=db, branch=dataset.branch, node_ids=[device.id])

        await _set_profiles(db=db, branch=dataset.branch, node_id=device.id, profiles=[])

        assert (before[device.id].origin, before[device.id].origin_node_id) == (OwnerOrigin.PROFILE, profile.id)
        assert await _resolve(db=db, branch=dataset.branch, node_ids=[device.id]) == {
            device.id: ResolvedOwnership(
                state=OwnerState.INHERIT,
                owner_ids=(dataset.groups["network-emea"],),
                origin=OwnerOrigin.PARENT,
                origin_node_id=dataset.tenant.id,
            )
        }

    async def test_profile_delete_closes_the_owners_that_the_profile_gives(
        self, db: InfrahubDatabase, dataset: ChangesDataset
    ) -> None:
        profile = await self._profile_that_gives(db, dataset, "profile-deleted", "dc-emea")
        device = await add_node(db=db, kind="TestDevice", name="device-deleted", rack=dataset.rack, profiles=[profile])
        main = dataset.branch.name
        assert await _given_owner_edges(db=db, profile_id=profile.id) == [
            ("HAS_OWNER", dataset.groups["dc-emea"], main, "active", True),
            ("HAS_TARGET_OWNER_SET", "set", main, "active", True),
        ]

        await profile.delete(db=db)

        assert await _given_owner_edges(db=db, profile_id=profile.id) == [
            ("HAS_OWNER", dataset.groups["dc-emea"], main, "active", False),
            ("HAS_TARGET_OWNER_SET", "set", main, "active", False),
        ]
        assert await _resolve(db=db, branch=dataset.branch, node_ids=[device.id]) == {
            device.id: ResolvedOwnership(
                state=OwnerState.INHERIT,
                owner_ids=(dataset.groups["network-emea"],),
                origin=OwnerOrigin.PARENT,
                origin_node_id=dataset.tenant.id,
            )
        }
        await verify_graph(db=db, kinds=["TestDevice", DEVICE_PROFILE])

    async def test_write_reuses_the_set_that_another_branch_created(
        self, db: InfrahubDatabase, dataset: ChangesDataset
    ) -> None:
        profile = await add_node(db=db, kind=DEVICE_PROFILE, profile_name="profile-shared-set")
        other_branch = await create_branch(branch_name="branch-shared-set", db=db)
        emea, security = dataset.groups["dc-emea"], dataset.groups["dc-security"]

        await _write(db=db, branch=other_branch, node_id=profile.id, holder=NODE_TARGET_HOLDER, owner_ids=None)
        sets_after_inherit = await _count_owner_sets(db=db, profile_id=profile.id)
        await _write(db=db, branch=other_branch, node_id=profile.id, holder=NODE_TARGET_HOLDER, owner_ids=(emea,))
        await _write(db=db, branch=dataset.branch, node_id=profile.id, holder=NODE_TARGET_HOLDER, owner_ids=(security,))
        await _write(db=db, branch=other_branch, node_id=profile.id, holder=NODE_TARGET_HOLDER, owner_ids=())

        assert sets_after_inherit == 0
        assert await _count_owner_sets(db=db, profile_id=profile.id) == 1
        assert await _stored(db=db, branch=dataset.branch, node_id=profile.id) == {
            NODE_TARGET_HOLDER: StoredOwnerState(owner_ids=(security,))
        }
        assert await _stored(db=db, branch=other_branch, node_id=profile.id) == {
            NODE_TARGET_HOLDER: StoredOwnerState(owner_ids=())
        }

        await _write(db=db, branch=dataset.branch, node_id=profile.id, holder=NODE_TARGET_HOLDER, owner_ids=None)

        assert await _count_owner_sets(db=db, profile_id=profile.id) == 1
        assert await _stored(db=db, branch=dataset.branch, node_id=profile.id) == {}
        assert await _stored(db=db, branch=other_branch, node_id=profile.id) == {
            NODE_TARGET_HOLDER: StoredOwnerState(owner_ids=())
        }
