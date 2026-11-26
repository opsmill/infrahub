from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import InfrahubKind, MetadataOptions
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node.create import create_node
from infrahub.core.ownership.models import (
    NODE_HOLDER,
    NODE_TARGET_HOLDER,
    HolderKey,
    HolderKind,
    OwnerOrigin,
    OwnerState,
    ResolvedOwnership,
    StoredOwnerState,
)
from infrahub.core.ownership.queries import NodeOwnerStateReadQuery
from infrahub.core.ownership.repository import OwnershipRepository
from infrahub.core.ownership.resolver import OwnershipResolver
from infrahub.core.registry import registry
from infrahub.core.timestamp import Timestamp
from infrahub.database.validation import verify_graph
from tests.constants import TestKind
from tests.helpers.db_query_counter import CountingInfrahubDatabase
from tests.helpers.ownership import (
    OWNERS_FIELD,
    OwnerDataset,
    add_node,
    copies,
    load_owner_dataset,
    resolve_owners,
    set_owners,
    site_from,
    site_template,
    template_copies,
)
from tests.helpers.schema import DEVICE_SCHEMA, load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase

DEVICE_TEMPLATE = f"Template{TestKind.DEVICE}"
INTERFACE_TEMPLATE = f"Template{TestKind.PHYSICAL_INTERFACE}"
SFP_TEMPLATE = f"Template{TestKind.SFP}"
DEVICE_PROFILE = f"Profile{TestKind.DEVICE}"


@dataclass
class TemplateDataset:
    branch: Branch
    groups: dict[str, str]
    """The ID of each account group, by name."""

    def owners(self, *names: str) -> tuple[str, ...]:
        return tuple(sorted(self.groups[name] for name in names))


@pytest.fixture
async def dataset(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None) -> TemplateDataset:
    await load_schema(db=db, schema=DEVICE_SCHEMA, branch_name=default_branch.name)
    groups: dict[str, str] = {}
    for name in ("dc-emea", "dc-security", "network-emea"):
        groups[name] = (await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name=name)).id
    return TemplateDataset(branch=default_branch, groups=groups)


async def _device_template(
    db: InfrahubDatabase, dataset: TemplateDataset, name: str, owners: tuple[str, ...] | None
) -> Node:
    """Create a device template that gives these owners to its devices. None gives nothing."""
    template = await add_node(
        db=db, kind=DEVICE_TEMPLATE, template_name=name, manufacturer="Acme", weight=1, airflow="Passive"
    )
    if owners is not None:
        await set_owners(db=db, branch=dataset.branch, node_id=template.id, holder=NODE_TARGET_HOLDER, owner_ids=owners)
    return template


async def _interface_template(
    db: InfrahubDatabase, dataset: TemplateDataset, template: Node, name: str, owners: tuple[str, ...] | None
) -> Node:
    """Add to a device template an interface subtemplate that gives these owners. None gives nothing."""
    interface = await add_node(
        db=db,
        kind=INTERFACE_TEMPLATE,
        template_name=f"{template.template_name.value}-{name}",
        name=name,
        phys_type="SFP+ (10GE)",
        device=template.id,
    )
    if owners is not None:
        await set_owners(
            db=db, branch=dataset.branch, node_id=interface.id, holder=NODE_TARGET_HOLDER, owner_ids=owners
        )
    return interface


async def _create_device(db: InfrahubDatabase, dataset: TemplateDataset, name: str, template: Node) -> Node:
    return await create_node(
        data={"name": name, "object_template": {"id": template.id}},
        db=db,
        branch=dataset.branch,
        schema=registry.schema.get_node_schema(name=TestKind.DEVICE, branch=dataset.branch),
    )


async def _resolve(db: InfrahubDatabase, dataset: TemplateDataset, *node_ids: str) -> dict[str, ResolvedOwnership]:
    resolver = OwnershipResolver(repository=OwnershipRepository(db=db, branch=dataset.branch, at=None))
    return await resolver.resolve(node_ids=list(node_ids))


async def _stored(db: InfrahubDatabase, dataset: TemplateDataset, node_id: str) -> dict[HolderKey, StoredOwnerState]:
    stored = await OwnershipRepository(db=db, branch=dataset.branch, at=None).read(node_ids=[node_id])
    return dict(stored[node_id].holders)


def _from_template(template: Node, owner_ids: tuple[str, ...]) -> ResolvedOwnership:
    return ResolvedOwnership(
        state=OwnerState.INHERIT, owner_ids=owner_ids, origin=OwnerOrigin.TEMPLATE, origin_node_id=template.id
    )


async def test_node_created_from_a_template_gets_a_copy_of_the_owners_that_the_template_gives(
    db: InfrahubDatabase, dataset: TemplateDataset
) -> None:
    owner_ids = dataset.owners("dc-emea", "network-emea")
    template = await _device_template(db=db, dataset=dataset, name="emea-leaf", owners=owner_ids)

    device = await _create_device(db=db, dataset=dataset, name="leaf-1", template=template)

    assert await _resolve(db, dataset, device.id) == {device.id: _from_template(template, owner_ids)}
    assert await _stored(db, dataset, device.id) == {
        NODE_HOLDER: StoredOwnerState(owner_ids=owner_ids, template_id=template.id)
    }
    change = device.node_changelog.attributes[OWNERS_FIELD]
    assert (change.kind, change.value_previous, change.value) == (
        "List",
        None,
        f'["{owner_ids[0]}","{owner_ids[1]}"]',
    )
    await verify_graph(db=db, kinds=[TestKind.DEVICE, DEVICE_TEMPLATE])


@pytest.mark.parametrize(
    ("given", "expected_origin"),
    [
        pytest.param((), OwnerOrigin.TEMPLATE, id="template_gives_no_owner"),
        pytest.param(None, None, id="template_gives_nothing"),
    ],
)
async def test_node_created_from_a_template_that_gives_no_owners(
    db: InfrahubDatabase, dataset: TemplateDataset, given: tuple[str, ...] | None, expected_origin: OwnerOrigin | None
) -> None:
    template = await _device_template(db=db, dataset=dataset, name="plain-leaf", owners=given)

    device = await _create_device(db=db, dataset=dataset, name="leaf-1", template=template)

    assert await _resolve(db, dataset, device.id) == {
        device.id: ResolvedOwnership(
            state=OwnerState.INHERIT,
            owner_ids=(),
            origin=expected_origin,
            origin_node_id=template.id if expected_origin else None,
        )
    }
    assert (OWNERS_FIELD in device.node_changelog.attributes) is (given is not None)


@pytest.mark.parametrize(
    "deleted",
    [pytest.param(("dc-emea",), id="one_owner_deleted"), pytest.param(("dc-emea", "network-emea"), id="all_deleted")],
)
async def test_node_created_from_a_template_gets_the_deleted_owners_that_the_template_gives(
    db: InfrahubDatabase, dataset: TemplateDataset, deleted: tuple[str, ...]
) -> None:
    owner_ids = dataset.owners("dc-emea", "network-emea")
    template = await _device_template(db=db, dataset=dataset, name="emea-leaf", owners=owner_ids)
    for name in deleted:
        group = await NodeManager.get_one(db=db, branch=dataset.branch, id=dataset.groups[name], raise_on_error=True)
        await group.delete(db=db)

    device = await _create_device(db=db, dataset=dataset, name="leaf-1", template=template)

    assert await _stored(db, dataset, device.id) == {
        NODE_HOLDER: StoredOwnerState(owner_ids=owner_ids, template_id=template.id)
    }
    assert await _resolve(db, dataset, device.id) == {device.id: _from_template(template, owner_ids)}


async def test_copy_of_a_deleted_owner_on_a_branch_made_after_the_delete_is_a_valid_graph(
    db: InfrahubDatabase, dataset: TemplateDataset
) -> None:
    owner_ids = dataset.owners("dc-emea")
    template = await _device_template(db=db, dataset=dataset, name="emea-leaf", owners=owner_ids)
    group = await NodeManager.get_one(db=db, branch=dataset.branch, id=dataset.groups["dc-emea"], raise_on_error=True)
    await group.delete(db=db)
    branch = await create_branch(db=db, branch_name="after-delete")

    device = await create_node(
        data={"name": "leaf-1", "object_template": {"id": template.id}},
        db=db,
        branch=branch,
        schema=registry.schema.get_node_schema(name=TestKind.DEVICE, branch=branch),
    )

    stored = await OwnershipRepository(db=db, branch=branch, at=None).read(node_ids=[device.id])
    assert dict(stored[device.id].holders) == {
        NODE_HOLDER: StoredOwnerState(owner_ids=owner_ids, template_id=template.id)
    }
    await verify_graph(db=db)


async def test_profile_replaces_the_owners_that_came_from_a_template(
    db: InfrahubDatabase, dataset: TemplateDataset
) -> None:
    template_owners = dataset.owners("dc-emea")
    template = await _device_template(db=db, dataset=dataset, name="emea-leaf", owners=template_owners)
    device = await _create_device(db=db, dataset=dataset, name="leaf-1", template=template)
    profile = await add_node(db=db, kind=DEVICE_PROFILE, profile_name="security-devices")
    await set_owners(
        db=db,
        branch=dataset.branch,
        node_id=profile.id,
        holder=NODE_TARGET_HOLDER,
        owner_ids=dataset.owners("dc-security"),
    )
    resolved: dict[str, ResolvedOwnership] = {}

    for step, profiles in (("profile attached", [profile]), ("profile removed", [])):
        stored_device = await NodeManager.get_one(db=db, branch=dataset.branch, id=device.id, raise_on_error=True)
        await stored_device.profiles.update(db=db, data=profiles)
        await stored_device.save(db=db)
        resolved[step] = (await _resolve(db, dataset, device.id))[device.id]

    assert resolved == {
        "profile attached": ResolvedOwnership(
            state=OwnerState.INHERIT,
            owner_ids=dataset.owners("dc-security"),
            origin=OwnerOrigin.PROFILE,
            origin_node_id=profile.id,
        ),
        "profile removed": _from_template(template, template_owners),
    }


async def test_template_changed_after_the_create_does_not_change_the_node(
    db: InfrahubDatabase, dataset: TemplateDataset
) -> None:
    first_owners = dataset.owners("dc-emea")
    template = await _device_template(db=db, dataset=dataset, name="emea-leaf", owners=first_owners)
    device = await _create_device(db=db, dataset=dataset, name="leaf-1", template=template)

    await set_owners(
        db=db,
        branch=dataset.branch,
        node_id=template.id,
        holder=NODE_TARGET_HOLDER,
        owner_ids=dataset.owners("dc-security"),
    )
    later_device = await _create_device(db=db, dataset=dataset, name="leaf-2", template=template)

    assert await _resolve(db, dataset, device.id, later_device.id) == {
        device.id: _from_template(template, first_owners),
        later_device.id: _from_template(template, dataset.owners("dc-security")),
    }


async def test_components_get_the_owners_that_their_subtemplates_give(
    db: InfrahubDatabase, dataset: TemplateDataset
) -> None:
    device_owners = dataset.owners("dc-emea")
    template = await _device_template(db=db, dataset=dataset, name="emea-leaf", owners=device_owners)
    subtemplates = {
        name: await _interface_template(db=db, dataset=dataset, template=template, name=name, owners=owners)
        for name, owners in (
            ("eth0", dataset.owners("dc-security")),
            ("eth1", None),
            ("eth2", ()),
        )
    }
    sfp_subtemplate = await add_node(
        db=db,
        kind=SFP_TEMPLATE,
        template_name="emea-leaf-eth0-sfp",
        phys_type="SFP+ (10GE)",
        serial_number="sn-0",
        interface=subtemplates["eth0"].id,
    )
    await set_owners(
        db=db,
        branch=dataset.branch,
        node_id=sfp_subtemplate.id,
        holder=NODE_TARGET_HOLDER,
        owner_ids=dataset.owners("network-emea"),
    )

    device = await _create_device(db=db, dataset=dataset, name="leaf-1", template=template)

    interfaces = {
        interface.name.value: interface
        for interface in await NodeManager.query(db=db, schema=TestKind.PHYSICAL_INTERFACE, branch=dataset.branch)
    }
    sfps = await NodeManager.query(db=db, schema=TestKind.SFP, branch=dataset.branch)
    assert (sorted(interfaces), len(sfps)) == (["eth0", "eth1", "eth2"], 1)
    resolved = await _resolve(db, dataset, device.id, sfps[0].id, *(interface.id for interface in interfaces.values()))
    assert resolved == {
        device.id: _from_template(template, device_owners),
        interfaces["eth0"].id: _from_template(subtemplates["eth0"], dataset.owners("dc-security")),
        interfaces["eth1"].id: ResolvedOwnership(
            state=OwnerState.INHERIT, owner_ids=device_owners, origin=OwnerOrigin.PARENT, origin_node_id=device.id
        ),
        interfaces["eth2"].id: _from_template(subtemplates["eth2"], ()),
        sfps[0].id: _from_template(sfp_subtemplate, dataset.owners("network-emea")),
    }
    await verify_graph(db=db, kinds=[TestKind.DEVICE, TestKind.PHYSICAL_INTERFACE, TestKind.SFP])


async def test_component_created_at_a_given_time_gets_the_owners_of_its_subtemplate(
    db: InfrahubDatabase, dataset: TemplateDataset
) -> None:
    template = await _device_template(db=db, dataset=dataset, name="emea-leaf", owners=None)
    subtemplate = await _interface_template(
        db=db, dataset=dataset, template=template, name="eth0", owners=dataset.owners("dc-security")
    )
    create_at = Timestamp()

    await create_node(
        data={"name": "leaf-1", "object_template": {"id": template.id}},
        db=db,
        branch=dataset.branch,
        schema=registry.schema.get_node_schema(name=TestKind.DEVICE, branch=dataset.branch),
        at=create_at,
    )

    interfaces = await NodeManager.query(db=db, schema=TestKind.PHYSICAL_INTERFACE, branch=dataset.branch)
    assert await _resolve(db, dataset, interfaces[0].id) == {
        interfaces[0].id: _from_template(subtemplate, dataset.owners("dc-security"))
    }


@pytest.mark.parametrize(
    ("written", "expected_state", "expected_origin"),
    [
        pytest.param(("dc-emea",), OwnerState.OWNERS, OwnerOrigin.SELF, id="same_owners"),
        pytest.param((), OwnerState.NO_OWNER, OwnerOrigin.SELF, id="no_owner"),
        pytest.param(None, OwnerState.INHERIT, None, id="inherit"),
    ],
)
async def test_owners_set_on_the_node_replace_the_copy_from_the_template(
    db: InfrahubDatabase,
    dataset: TemplateDataset,
    written: tuple[str, ...] | None,
    expected_state: OwnerState,
    expected_origin: OwnerOrigin | None,
) -> None:
    template = await _device_template(db=db, dataset=dataset, name="emea-leaf", owners=dataset.owners("dc-emea"))
    device = await _create_device(db=db, dataset=dataset, name="leaf-1", template=template)
    owner_ids = dataset.owners(*written) if written is not None else None

    await set_owners(db=db, branch=dataset.branch, node_id=device.id, holder=NODE_HOLDER, owner_ids=owner_ids)

    assert await _stored(db, dataset, device.id) == (
        {NODE_HOLDER: StoredOwnerState(owner_ids=owner_ids)} if owner_ids is not None else {}
    )
    assert await _resolve(db, dataset, device.id) == {
        device.id: ResolvedOwnership(
            state=expected_state,
            owner_ids=owner_ids or (),
            origin=expected_origin,
            origin_node_id=device.id if expected_origin else None,
        )
    }


async def test_create_reads_the_owners_of_a_template_and_its_subtemplates_one_time(
    db: InfrahubDatabase, dataset: TemplateDataset
) -> None:
    owner_reads: dict[int, int] = {}
    copies: dict[int, int] = {}
    for nbr_components in (2, 6):
        template = await _device_template(
            db=db, dataset=dataset, name=f"leaf-{nbr_components}", owners=dataset.owners("dc-emea")
        )
        for index in range(nbr_components):
            await _interface_template(
                db=db, dataset=dataset, template=template, name=f"eth{index}", owners=dataset.owners("dc-security")
            )
        counting_db = CountingInfrahubDatabase.from_db(db=db)

        device = await create_node(
            data={"name": f"device-{nbr_components}", "object_template": {"id": template.id}},
            db=counting_db,
            branch=dataset.branch,
            schema=registry.schema.get_node_schema(name=TestKind.DEVICE, branch=dataset.branch),
        )

        owner_reads[nbr_components] = counting_db.count_for(NodeOwnerStateReadQuery.name)
        interfaces = await NodeManager.query(
            db=db, schema=TestKind.PHYSICAL_INTERFACE, branch=dataset.branch, filters={"device__ids": [device.id]}
        )
        resolved = await _resolve(db, dataset, *(interface.id for interface in interfaces))
        copies[nbr_components] = sum(1 for owners in resolved.values() if owners.origin is OwnerOrigin.TEMPLATE)

    assert owner_reads == {2: 1, 6: 1}
    assert copies == {2: 2, 6: 6}


@pytest.fixture
async def owner_dataset(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None
) -> OwnerDataset:
    return await load_owner_dataset(db=db, default_branch=default_branch)


async def test_template_deleted_on_the_default_branch_leaves_its_copies_as_own_owners(
    db: InfrahubDatabase, default_branch: Branch, owner_dataset: OwnerDataset
) -> None:
    dataset = owner_dataset
    owner_ids = dataset.owners(("dc-emea",))
    template = await site_template(db=db, default_branch=default_branch, dataset=dataset)
    site_id = await site_from(db=db, branch=default_branch, template=template, name="site-a")
    branch = await create_branch(db=db, branch_name="template-kept")
    assert await template_copies(db=db, branch=default_branch, node_id=site_id) == copies(owner_ids, template.id)

    await template.delete(db=db)

    assert await template_copies(db=db, branch=default_branch, node_id=site_id) == copies(owner_ids, None)
    assert await template_copies(db=db, branch=branch, node_id=site_id) == copies(owner_ids, template.id)
    resolved = await resolve_owners(db=db, branch=default_branch, node_id=site_id)
    assert (resolved.state, resolved.owner_ids, resolved.origin, resolved.origin_node_id) == (
        OwnerState.OWNERS,
        owner_ids,
        OwnerOrigin.SELF,
        site_id,
    )
    await verify_graph(db=db)


async def test_attribute_owner_given_at_the_create_replaces_the_copy_from_the_template(
    db: InfrahubDatabase, default_branch: Branch, owner_dataset: OwnerDataset
) -> None:
    dataset = owner_dataset
    template = await site_template(db=db, default_branch=default_branch, dataset=dataset)

    site = await create_node(
        data={
            "name": {"value": "site-b", "owner": dataset.ids["network-emea"]},
            "object_template": {"id": template.id},
        },
        db=db,
        branch=default_branch,
        schema=registry.schema.get_node_schema(name="TestSite", branch=default_branch),
    )

    assert await template_copies(db=db, branch=default_branch, node_id=site.id) == {
        **copies(dataset.owners(("dc-emea",)), template.id),
        HolderKind.ATTRIBUTE: (dataset.owners(("network-emea",)), None),
    }
    await verify_graph(db=db)


async def test_attribute_owner_field_gives_no_owner_for_a_copy_from_the_template(
    db: InfrahubDatabase, default_branch: Branch, owner_dataset: OwnerDataset
) -> None:
    dataset = owner_dataset
    name_holder = HolderKey(kind=HolderKind.ATTRIBUTE, attribute="name")
    template = await site_template(db=db, default_branch=default_branch, dataset=dataset)
    site_id = await site_from(db=db, branch=default_branch, template=template, name="site-c")

    async def name_owner_id() -> str | None:
        site = await NodeManager.get_one(
            db=db, branch=default_branch, id=site_id, include_metadata=MetadataOptions.OWNER, raise_on_error=True
        )
        return site.name.owner_id

    assert (await template_copies(db=db, branch=default_branch, node_id=site_id))[HolderKind.ATTRIBUTE] == (
        dataset.owners(("dc-emea",)),
        template.id,
    )
    assert await name_owner_id() is None

    await set_owners(
        db=db,
        branch=default_branch,
        node_id=site_id,
        owner_ids=dataset.owners(("network-emea",)),
        holder=name_holder,
    )

    assert (await template_copies(db=db, branch=default_branch, node_id=site_id))[HolderKind.ATTRIBUTE] == (
        dataset.owners(("network-emea",)),
        None,
    )
    assert await name_owner_id() == dataset.ids["network-emea"]
