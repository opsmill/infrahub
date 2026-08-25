from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.create import create_node
from infrahub.core.query.node import NodeListGetRelationshipsQuery
from infrahub.core.query.relationship import RelationshipGetPeerQuery
from infrahub.core.registry import registry
from tests.constants import TestKind
from tests.helpers.db_query_counter import CountingInfrahubDatabase
from tests.helpers.schema import DEVICE_SCHEMA, load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


@pytest.fixture
async def device_schema(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None) -> None:
    await load_schema(db=db, schema=DEVICE_SCHEMA, branch_name=default_branch.name)


async def _build_template(db: InfrahubDatabase, branch: Branch, name: str, nbr_interfaces: int) -> Node:
    template = await Node.init(db=db, schema=f"Template{TestKind.DEVICE}", branch=branch)
    await template.new(db=db, template_name=name, manufacturer="Acme", weight=1, airflow="Passive")
    await template.save(db=db)

    for idx in range(nbr_interfaces):
        interface = await Node.init(db=db, schema=f"Template{TestKind.PHYSICAL_INTERFACE}", branch=branch)
        await interface.new(
            db=db,
            template_name=f"{name}-eth{idx}",
            name=f"eth{idx}",
            phys_type="SFP+ (10GE)",
            device=template.id,
        )
        await interface.save(db=db)

    return template


async def test_create_without_a_template_does_not_look_for_one(
    db: InfrahubDatabase, default_branch: Branch, device_schema: None
) -> None:
    """A node built without a template is not asked afterwards which template it came from."""
    device_schema_obj = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)
    counting_db = CountingInfrahubDatabase.from_db(db=db)

    device = await create_node(
        data={"name": "no-template", "manufacturer": "Acme", "weight": 1, "airflow": "Passive"},
        db=counting_db,
        branch=default_branch,
        schema=device_schema_obj,
    )

    assert device.manufacturer.value == "Acme"
    assert counting_db.count_for(RelationshipGetPeerQuery.name) == 0


async def test_create_from_template_reads_it_once_with_its_relationships(
    db: InfrahubDatabase, default_branch: Branch, device_schema: None
) -> None:
    """The template is read once, with its relationships, for the preview and the node it creates."""
    template = await _build_template(db=db, branch=default_branch, name="empty-template", nbr_interfaces=0)
    device_schema_obj = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)
    counting_db = CountingInfrahubDatabase.from_db(db=db)

    device = await create_node(
        data={"name": "from-empty-template", "object_template": {"id": template.id}},
        db=counting_db,
        branch=default_branch,
        schema=device_schema_obj,
    )

    assert device.manufacturer.value == "Acme"
    assert device.weight.value == 1
    assert counting_db.count_for(RelationshipGetPeerQuery.name) == 0
    assert counting_db.count_for(NodeListGetRelationshipsQuery.name) == 1


async def test_create_from_template_does_not_read_the_relationships_of_its_components(
    db: InfrahubDatabase, default_branch: Branch, device_schema: None
) -> None:
    """The peers of a component relationship are read with their own relationships, all at once."""
    device_schema_obj = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)
    counts = {}

    for nbr_interfaces in (1, 5):
        template = await _build_template(
            db=db, branch=default_branch, name=f"template-{nbr_interfaces}", nbr_interfaces=nbr_interfaces
        )
        counting_db = CountingInfrahubDatabase.from_db(db=db)

        device = await create_node(
            data={"name": f"device-{nbr_interfaces}", "object_template": {"id": template.id}},
            db=counting_db,
            branch=default_branch,
            schema=device_schema_obj,
        )

        reloaded = await NodeManager.get_one(db=db, id=device.id, branch=default_branch, raise_on_error=True)
        interfaces = await reloaded.interfaces.get_peers(db=db)
        assert len(interfaces) == nbr_interfaces
        assert {interface.name.value for interface in interfaces.values()} == {
            f"eth{idx}" for idx in range(nbr_interfaces)
        }
        counts[nbr_interfaces] = counting_db.count_for(RelationshipGetPeerQuery.name)

    assert counts[1] == counts[5] == 0


async def test_create_from_template_does_not_read_the_objects_already_created_from_it(
    db: InfrahubDatabase, default_branch: Branch, device_schema: None
) -> None:
    """A template lists every object created from it; creating one more never reads that list."""
    template = await _build_template(db=db, branch=default_branch, name="popular", nbr_interfaces=1)
    device_schema_obj = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)

    counts = []
    rows_read = []
    for idx in range(5):
        counting_db = CountingInfrahubDatabase.from_db(db=db)
        await create_node(
            data={"name": f"device-{idx}", "object_template": {"id": template.id}},
            db=counting_db,
            branch=default_branch,
            schema=device_schema_obj,
        )
        counts.append(sum(counting_db.query_counts.values()))
        rows_read.append(sum(counting_db.row_counts.values()))

    assert len(set(counts)) == 1, f"the cost of a create grew with the objects already created: {counts}"
    assert len(set(rows_read)) == 1, f"a create read more of the database for each object created: {rows_read}"


async def test_materializing_a_component_costs_a_constant_number_of_queries(
    db: InfrahubDatabase, default_branch: Branch, device_schema: None
) -> None:
    """Each component a template carries is created at a fixed cost, and the cost does not drift."""
    device_schema_obj = registry.schema.get_node_schema(name=TestKind.DEVICE, branch=default_branch)

    counts = {}
    for nbr_interfaces in (1, 3, 5):
        template = await _build_template(
            db=db, branch=default_branch, name=f"cost-{nbr_interfaces}", nbr_interfaces=nbr_interfaces
        )
        counting_db = CountingInfrahubDatabase.from_db(db=db)
        await create_node(
            data={"name": f"cost-device-{nbr_interfaces}", "object_template": {"id": template.id}},
            db=counting_db,
            branch=default_branch,
            schema=device_schema_obj,
        )
        counts[nbr_interfaces] = sum(counting_db.query_counts.values())

    per_component = (counts[3] - counts[1]) / 2
    assert per_component == (counts[5] - counts[3]) / 2, f"the cost per component is not constant: {counts}"
    assert per_component <= 3, f"materializing a component costs {per_component} queries: {counts}"
